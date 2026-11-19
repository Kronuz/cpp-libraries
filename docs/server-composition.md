> Status: CURRENT (2026-11-19), reviewed, with the owner's Xapiand D132, D133 and D138 and Detent
> D122 and D123 folded in. Line numbers hold at task:95798a0, http:ec273dd, reactor:bf874dc,
> Detent:03eac9c5, prism:4d3c96d and Xapiand:eb3dcfa80. Nothing here is built; each daemon adopts
> it in its own quest.

# How a Kronuz server is put together

One composition for every Kronuz daemon: Xapiand, Prism, detent-authority, detent-relay and
detent-agent (Detent D122), so their mains read alike. The name detent-authority, formerly
detentd, follows Detent D123; its cited paths follow the rename, as at the pinned commit. It extends
[service-shape](https://github.com/Kronuz/task/blob/95798a0/docs/design/service-shape.md) (one
control loop, one shutdown) with what comes before the lifecycle: the process, the options, the
limits and TLS. Xapiand D132 renames service-shape's driver: `serve` becomes `task::lifecycle`, the
`service` concept becomes `component`, and the driver takes a stop source instead of
`stop_signals` (C10). Detent D76, D79-D82, D122 and D123 and Xapiand D62, D71-D77, D132, D133
and D138 set the rules; each decision ID below names its ledger.

## Summary

A `main` has eight steps, in this order: options, process, signals, limits and descriptors, TLS and
privileges, loop and components, `lifecycle`, housekeeping. Libraries own the steps (reactor:
loops, accept, admission, the connection bound, the descriptor limit, the TLS context; http: idle
close and one `Limits` struct; task: the lifecycle and the process step; no new library, Xapiand
D73). Apps own only values. A difference in a value is not a deviation; a different code path is,
and stays only with a reason (Detent D82), and a reason of cost needs Xapiand D62: the unified
shape costs over 5% CPU or 10% p99 after optimizing it, with before and after numbers. No
deviation below has that case.

## Composition

1. **Options.** Every limit has one name, spelled `--max-clients` as a flag and `max_clients` as a
   config key; durations are milliseconds, suffixed `_ms`. The table under "Options" fixes names
   and defaults. The parser is the app's. A bad value exits `EX_USAGE`.
2. **Process.** Detaching, the pid file and the log, before any thread exists:
   - `run_daemon(detach, log_path, run)` forks, sends stdout and stderr to the log, and runs the
     rest of `main` in the child. The parent returns only after the child's `ready()` or its error,
     which it reports, or after the startup timeout (Detent `src/detent_cli/daemon.cc:75-143`). In
     the foreground, `run` is called directly.
   - `ProcessLock` writes the pid file under an exclusive advisory `flock` held for the process's
     life, and `locked_pid` reports a pid only while that lock is held, so a stale file names no
     process (`daemon.cc:34-72`). A second instance finds the lock taken and exits.
   - The log session (the app's logger) opens inside `run`, after the fork.

   This is Detent's code (`detent_authority/main.cc:154-158`, `detent_relay/main.cc:62-68`). It is one
   implementation, and it moves to task beside `stop_signals`, so a process starts and stops
   through one library (C7).
3. **Signals.** `task::stop_signals` is the first object after the fork, since its thread must not
   cross one. It is a daemon's stop source, one of several (step 7). SIGINT and SIGTERM mean stop,
   hurry, flush-then-die (Detent D80). A diagnostic dump
   (Xapiand's SIGUSR1 and SIGINFO) runs from the signal thread, not the loop, so a wedged loop still
   dumps (service-shape D6's reason).
4. **Limits and descriptors.** Options map onto one struct that http takes whole, so no setter can
   be forgotten (C1):

   ```cpp
   struct http::Limits {                                   // contract for the http quest (Detent D81)
   	std::size_t max_clients = 1024;      // open connections, plain and TLS, idle ones counted
   	std::size_t max_in_flight = 1024;    // requests admitted per loop; 0 = no cap
   	std::chrono::milliseconds idle_timeout{75'000}, header_timeout{30'000}, inactivity_timeout{60'000};
   	std::chrono::milliseconds request_timeout{0};   // absolute per request; 0 = off
   	std::chrono::milliseconds shutdown_grace{5'000};
   	std::size_t max_body = 16u << 20;
   	std::chrono::milliseconds tls_handshake{5'000};
   	std::size_t tls_handshakes = 64;
   };
   struct http::Tls { std::shared_ptr<asio::ssl::context> context; TlsFailureHook failed; };  // no context: plain
   HttpAsioService(HttpHandler&, std::size_t reactors, const Limits&, Tls = {});
   ```

   Every bound lives in `Limits` and nowhere else. It replaces the constructor's `in_flight_limit`,
   `ConnectionFactory` and `maximum_connections` (`http_asio.h:1175-1182`), the setters
   `set_connection_limit`, `set_request_timeout`, `set_idle_timeout`, `set_header_timeout`,
   `set_inactivity_timeout`, `set_max_body` and `set_shutdown_grace` (`:1188-1217`), and the five
   limit fields of `AsioResponseOptions` (`:97-106`), which keeps only the response transforms.
   The http component builds its TLS session from `Tls` and `Limits`, so the handshake bounds are
   set in one place; `tls_connection_factory` (`http_asio_tls.h:362-376`) leaves the public
   surface, and with it the TLS path's own connection count (`TlsAdmission`, `:299-304`).
   `max_clients` reaches `reactor::TcpServer::set_connection_limit` (`reactor.h:712-715`), one
   bound for plain and TLS.

   Then the descriptor check, its own step for plain and TLS alike (C5). Each connection holds one
   descriptor. `main` asks reactor for `max_clients` plus the app's reserve; reactor raises the
   soft `RLIMIT_NOFILE` toward the hard limit and returns the limit in force:

   ```cpp
   std::size_t reactor::raise_open_files(std::size_t wanted);   // contract for the reactor quest
   ```

   The reserve is an app value, stated in its `main`: 64 for what is open besides connections
   (today's TLS check, Xapiand `tls.cc:56`), plus the app's own pools (Xapiand: 50 reserved plus
   7 per pooled index, `main.cc:85-87,443-449`). When the limit cannot hold the budget, an explicit
   `--max-clients` or `max_clients` exits `EX_CONFIG`, and the default shrinks to fit with a
   warning (Xapiand D133). The check runs before privileges drop, while the process can still raise
   its hard limit, and before any component starts.
5. **TLS and privileges.** One reactor function builds the server context: Xapiand's `tls_setup`
   (`tls.cc:51-76`) moved to `reactor::tls::server_context(options)`, which returns it to `main`.
   Over `reactor::tls::configure`, which already refuses an incomplete configuration and a key that
   does not match its certificate (`reactor_tls.h:56-86`), it refuses a key readable by group or
   others (Xapiand D77) and a certificate not yet valid or expired, warns within 14 days of
   expiry, and sets `strict` (C2). It throws; `main` logs and exits `EX_CONFIG`. It reads the key
   before privileges drop. Then the process drops privileges where the app offers it (Xapiand's
   `--uid` and `--gid`, `main.cc:492,1118`).
6. **Loop and components.** The process has one control loop, which `main` runs on the main thread
   (service-shape's `main`). Components (service-shape's `start`, `stop`, `drain` and `flush`) are
   constructed in dependency order: state (registry, authority), housekeeping owners, then the http
   component built from `Limits` and `Tls`. State is passed by reference to the components and the
   handler that use it; nothing reaches state through a process global (C6). A state component
   that writes a directory holds that directory's exclusion for its life (Detent: per-generation
   shared leases, `detent_local/generation.cc:182-187`).
7. **`lifecycle`.** `task::lifecycle(loop, stop, {}, ready, state..., http)` starts the components
   in order, calls `ready`, and when `stop` fires stops and drains them in reverse, then `flush()`.
   `stop` is a stop source: `stop_signals` in a daemon; a test, an admin QUIT, a parent component
   or a tool's end are others (Xapiand D132). A set of components is itself a component, so the
   call nests: a parent's stop is its children's stop source. `ready` is the same callback
   everywhere: when detached it reports readiness to the waiting parent, then it logs one line. See
   service-shape's "Stop and drain order".
8. **Housekeeping.** Periodic work is `task::periodic`, and a debounce is `task::debounce`, each
   owned by the component whose state it serves, each a task awaiting the wheel through
   `scheduler_ref::arm` (Detent D76, D79). No loop polls on a fixed interval: an idle loop waits on
   work or on a wheel deadline (C8). A `drain` joins the component's `group`.

## Options

Shared names and defaults. "Today" cells cite each app's current spelling. detent-agent has no
listener, so none of these apply to it.

| Shared (flag, key) | Default | detent-authority | detent-relay | Prism | Xapiand |
| :---- | :---- | :---- | :---- | :---- | :---- |
| `--max-clients`, `max_clients` | 1024 | constant 1024, no option (`detent_authority/main.cc:34,176-177`) | `connections`, 1024 (`configuration.cc:119`, `configuration.hh:30`) | none on plain; TLS constant 1024 (`main.cc:323-324`) | `--max-clients`, 1000, feeds the descriptor budget only (`opts.cc:50,184-185`, `main.cc:450-454`); `--tls-max-connections`, 1024, TLS only (`opts.cc:197,201`, `manager.cc:942-944`) |
| `--max-in-flight`, `max_in_flight` (per loop) | 1024; Xapiand sets 1000 | 1024, the same constant (`main.cc:176`) | `connections` again (`host.cc:290`) | 256 (`main.cc:323,331`) | 1000 constant (`manager.cc:943,950`) |
| `--idle-timeout-ms`, `idle_timeout_ms` | 75000 | none | none; `idle_ms`, 60 s, is the session lifetime (`configuration.cc:138`) | none | 75 s constant, TLS only (`manager.cc:945`) |
| `--shutdown-timeout-ms`, `shutdown_timeout_ms` | 35000 | none: drain unbounded (`main.cc:214-222`) | none (`host.cc:431-437`) | none; reactor's 5 s grace (`reactor.h:844`) | not an option: 35 s bound (`manager.cc:155-158`), 5 s grace (`:145,955`) |
| `--tls-cert`, `--tls-key` | unset: plain | `publisher_tls.{certificate,key}` (`service.cc:474-480,535-539`) | `certificate`, `private_key`, required (`configuration.cc:269-273`) | `--tls-cert=F`, `--tls-key=F` (`main.cc:258-259`) | `--tls-cert`, `--tls-key` (`opts.cc:199-200`) |
| `--upstream-ca`, `upstream_ca` | unset | `publisher_tls.ca`, read by the `--status` probe (`main.cc:80-82`) | `ca`: the mirror's upstream and the `--status` probe (`configuration.cc:101-103,151,157`, `main.cc:54`) | none | none |
| `--port`, `port` | per app: 8317, 8318, 8880, `XAPIAND_HTTP_SERVERPORT` | `--port` (`main.cc:131-132`) | `port` (`configuration.cc:147`) | positional (`main.cc:263`) | `--port` (`opts.cc:191`) |
| `--bind-address`, `bind_address` | loopback, except Prism and Xapiand: all | `publisher_bind` (`service.cc:541-544`, `service.hh:42`) | `address` (`configuration.cc:145-146`, `configuration.hh:21`) | none (`main.cc:341`, `reactor.h:90`) | `--bind-address` (`opts.cc:194`, `opts.h:51`) |
| `--reactors`, `reactors` | hardware threads | `--reactors`, 4 (`main.cc:133`) | constant 2 (`host.cc:290`) | hardware threads (`main.cc:265`) | `--processors` (`opts.cc:187-188,379`) |

`--upstream-ca` names the authority a server trusts for the connections it dials, not for its
clients (C9). No Kronuz server authenticates clients by TLS: the server role runs `verify_none`
whatever CA it is given (`reactor_tls.h:83-85`), detent-relay authenticates clients by bearer
token (`configuration.cc:204-213`), and detent-authority uses its CA to verify its own publisher
from `--status`. Mutual TLS between detent-authority's voters is its own configuration
(`peer_tls`, `service.cc:487`), not this option. Xapiand adds `--reactors`, defaulting from
`--processors`, which keeps sizing the WAL writers and fsynchers (`opts.cc:373-379`).

## Mains

By step, with the code each daemon calls today. detent-agent has no listener: its column fills
the signal, housekeeping and stop steps (Xapiand D138), and the process step, whose code it shares
with detent-authority.

| Step | detent-authority | detent-relay | detent-agent | Prism | Xapiand |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Options | `load_config`, env, flags (`detent_authority/main.cc:87-130`) | JSON, plus flags for the config path, runtime directory, daemonizing, status and system mode (`relay/main.cc:15-35`, `configuration.cc:116-117`) | no listener | hand loop, `--x=y`, positional port (`main.cc:242-264`) | CLI11 (`opts.cc:184-265`) |
| Process | `run_daemon`, `ProcessLock`, log `Session` (`main.cc:154-158`) | the same (`relay/main.cc:62-68`) | the same, 180 s startup timeout (`detent_agent/main.cc:105-116`, `config.hh:9`) | none: foreground | `detach()` forks and the parent exits at once; `writepid` takes no lock (`main.cc:623-649,1014-1019`) |
| Signals | `std::signal` flag (`main.cc:183-184`) | `asio::signal_set` on the owner loop (`host.cc:313-317`) | `asio::signal_set` on its loop; the first signal closes the coordinator (`managed_host.cc:186-190`) | `std::signal` flag (`main.cc:338-339`) | `sigaction`, self-pipe, a task (`main.cc:288-300`, `manager.cc:176-215,579-603`) |
| Limits and descriptors | constructor 1024 and 1024, request timeout 5 s (`service.hh:53`), body cap (`main.cc:176-180`); no descriptor check | `connections` twice, 2 loops, request timeout 65 s (`host.cc:290-295`); no descriptor check | no listener | constructor 256; bound on TLS only (`main.cc:323-331`); no descriptor check | timeouts on TLS only, grace, body cap (`manager.cc:942-958`); the budget raises and shrinks, after `demote` (`main.cc:338-490,801,814,1118`) |
| TLS and privileges | `configure`, `tls_connection_factory` (`main.cc:166-171`) | `configure` in the loader (`configuration.cc:269-273`); always on | no listener | `configure`, `tls_connection_factory_timed`; `PRISM_TLS` build flag (`main.cc:43-46,319-329`) | `tls_setup`, then `demote` (`main.cc:1105-1118`) |
| Loop and components | `OwnerLoop` on its own thread (`owner_loop.hh:24-26`), authority, then http (`main.cc:173-181`) | `OwnerLoop`, registry, coordinators, mirror, listener (`host.cc:155-296`) | no listener | no state, no loop; app, `AccessLog`, listener (`main.cc:293-333`) | the manager's reactor, run on the main thread (`manager.cc:176-215,540-567`) |
| `lifecycle`, ready | `start(port)`, lone-quorum 5 ms poll, `ready()` (`main.cc:191-206`) | `ready()` from the `turn` loop (`host.cc:367-377`) | no listener | `start`, banner, a log line; no ready (`main.cc:341-343`) | `start` in `set_ready_impl` (`manager.cc:988-1003`) |
| Housekeeping | the authority waits 1 ms when idle (`service.cc:2030,2046,3182,3317`) | `turn`: post while progress, else 1 ms (`host.cc:394-410`) | `monitor` polls the coordinator every 20 ms, logs what changed and calls `ready()` (`managed_host.cc:28-112`); the coordinator waits on its worker 1 ms at a time (`detent_delivery/coordinator.cc:253,316,446`) | none | `control::Periodic` 1 min, `control::Debounce` autocommit, `control::Periodic` 5 s shutdown retry (`manager.cc:826,300,184,706-709`) |
| Stop | 200 ms poll, then ordered calls, no bound (`main.cc:208-222`) | main blocks on a promise, no bound (`host.cc:431-440`) | a 20 ms poll until the coordinator drains, then ordered teardown, no bound (`managed_host.cc:198-228`) | 100 ms poll, `service.stop()` (`main.cc:345-348`) | `join()`, one 35 s deadline (`manager.cc:1032-1220`) |

## Deviations

Each difference in code path between the apps, its reason, and whether it stays.

| Deviation | Reason | Status |
| :---- | :---- | :---- |
| Bounds set by setters, on TLS only (Xapiand, Prism) or not at all (Detent) | None | Removed by `Limits` (C1) |
| No descriptor check (Detent, Prism); a TLS-only check plus a budget after `demote` (Xapiand) | None | Removed by the descriptor step (C5) |
| Fixed-interval polls: 1 ms (detent-authority's authority service, the relay's `turn`, detent-agent's coordinator), 20 ms (detent-agent's monitor and stop watch), 5 and 200 ms (detent-authority's main), 100 ms (Prism), a 10 ms drain and a 5 s shutdown retry (Xapiand, `manager.cc:1006-1029,706-709`) | None; no Xapiand D62 case | Removed (C8): Detent quest loop-idle-waits for the 1 ms loops, `lifecycle` for the rest |
| A stop with no bound (detent-authority, relay, detent-agent) | None | Removed: `--shutdown-timeout-ms` bounds every stop (Settled 3) |
| Loop on its own thread (`OwnerLoop`, detent-authority and relay) | Today's code, not a design | Removed: Settled 4 |
| Signals as a flag polled by `main` (detent-authority, Prism); `signal_set` (relay, detent-agent) | Neither tells a second or third signal apart (service-shape D6, Detent D80) | Removed by `stop_signals` as the stop source |
| A daemon with no readiness and a pid file with no lock (Xapiand) | None | Removed by the process step (C7) |
| No data-directory exclusion (Xapiand) | None | Removed: Xapiand's registry holds an exclusive `flock` in its data directory |
| State reached through a process global (Xapiand's `XapiandManager::manager()` and `tls_context`) | None | Removed (C6) |
| `--processors` instead of `--reactors` (Xapiand) | `--processors` also sizes the WAL writers and fsynchers | Removed: Xapiand adds `--reactors` (Options) |
| No daemon mode (Prism) | A foreground demo with no `--daemonize` | Stays: a missing option, not another path; its `ready` is the log line |
| Privilege drop (Xapiand only) | Only Xapiand offers `--uid` and `--gid` (`opts.cc:221-224`); Detent and Prism run as the user that starts them | Stays: the step runs only where the option exists |
| Limits as config keys only (relay); as flags only (Prism, Xapiand) | The relay's configuration holds credentials and per-bundle sources, which flags do not carry; Prism and Xapiand have no configuration file | Stays: one spelling per limit either way (C3) |
| Bind default loopback (Detent) or all interfaces (Prism, Xapiand) | detent-authority refuses a non-loopback publisher without TLS (`service.cc:543-544`); Prism and Xapiand serve the network by default (`reactor.h:90`) | Stays: a value (C4) |
| TLS compiled out (Prism, Xapiand) | OpenSSL is optional | Stays: a build option |
| TLS required (relay) | Its clients send bearer tokens | Stays: a value (`tls_cert` set) |
| Absolute request timeout (detent-authority 5 s, relay 65 s) | A trickled request must not renew admission (`http_asio.h:97-98`) | Stays: a `Limits` value |
| Diagnostic dump on SIGUSR1 and SIGINFO (Xapiand) | Thread, manager, pool and schema state for a wedged node (`manager.cc:595-600`) | Stays: an app feature, run from the signal thread (step 3) |

## Decisions

| # | Decision | Lost, and why |
| :---- | :---- | :---- |
| C1 | One `http::Limits` holds every bound, taken whole by the constructor with the TLS context | The setters: three mains set different subsets, and an unset limit is silently off. `AsioResponseOptions`' limit fields and the TLS factory's arguments: two places for one bound |
| C2 | `server_context` lives in reactor, beside `configure`, and sets `strict` for every app | Each app calling `configure` raw, with the key mode, validity and expiry checked by Xapiand alone; a new library (Xapiand D73). One TLS policy: TLS 1.3 suites are AEAD already, so `strict` narrows TLS 1.2 to forward-secret AEAD and turns session resumption off |
| C3 | One name per option, flag and key alike; `_ms` durations | Unitless durations; Xapiand's unitless milliseconds (`opts.h:96-107`) are internal constants, not flags, so no Xapiand flag is renamed |
| C4 | A value that differs is an input, not a deviation | Listing every constant as a deviation: it hides the code paths that differ |
| C5 | The descriptor check is its own step, in reactor, for plain and TLS: it raises the soft limit first, adds the app's stated reserve, exits `EX_CONFIG` on an explicit `--max-clients` that does not fit and shrinks a default with a warning (Xapiand D133) | A check inside `server_context`: it vanishes with TLS compiled out and never runs for plain servers. Refusing a default: stock soft limits (systemd 1024, launchd 256) would stop the apps out of the box. Shrinking an explicit value (Xapiand, `main.cc:457-465`): the operator gets a bound they did not set |
| C6 | State components are constructed in `main` and passed by reference to the components and handler that use them | A process global: every caller depends on a construction order it cannot see, and tests share one instance. A global that stays is a deviation with a reason |
| C7 | The process step is Detent's `run_daemon`, `ProcessLock` and `locked_pid`, moved to task beside `stop_signals` | Each app keeping its own: Xapiand's `detach()` would stay a second implementation with no readiness. A process library: the step is three functions, and task already owns the process's signals (Xapiand D73, revisited for this step only) |
| C8 | No fixed-interval polling: an idle loop waits on work or on a wheel deadline | The 1 ms loops: no Xapiand D62 case keeps them, and a 1 ms timer wakes an idle process a thousand times a second |
| C9 | `--upstream-ca` is the trust root for the connections a server dials | `--tls-ca` read as client authentication: no app does that, and adopting it would either turn on mutual TLS and break token clients or add a flag that does nothing. Mutual TLS for clients, if wanted, is its own option and a reactor `Role` change, decided by the owner |
| C10 | The driver is `task::lifecycle` over `component`s, it takes a stop source, and a set of components is a component (Xapiand D132) | `serve(loop, stop_signals&, ...)` over `service`s: the stop came only from the process's one `stop_signals`, which owns the signal handlers, so a test, a tool or a parent component had to hold the process's signals to stop a set, and a set could not nest inside another |

## Settled

1. **Header and inactivity timeouts on every connection**, plain and TLS (Xapiand sets 30 s and 60 s
   for TLS only, `manager.cc:946-947`). The http `Limits` quest carries an acceptance test: a
   detent-authority held poll with its headers complete and no body read trips neither (Xapiand
   lead agrees).
2. **A key readable by group or others is refused in all three** (owner, Xapiand D77).
3. **`--shutdown-timeout-ms`, `shutdown_timeout_ms`, default 35000**, mapped onto
   `stop_timing::bound`; the 5 s grace is fixed (owner, Xapiand D77).
4. **The loop runs on the main thread**, as service-shape's `main` and Xapiand do; Detent's
   `OwnerLoop` (`detent_authority/main.cc:218-222`; `host.cc:438-440`) gains a `run()` (Xapiand lead
   agrees).
5. **Defaults `max_clients` 1024 and `max_in_flight` 1024**, the largest present value, so no app
   is limited below today (Xapiand lead agrees). Xapiand's `--max-clients` default moves from 1000
   to 1024; its per-loop in-flight cap stays 1000, a value it sets (Xapiand D72).
6. **http gains a close-idle-now call** beside the idle timeout, so Xapiand's `FLUSH?clients`
   closes idle connections (Xapiand D76); the http quest names it in its contract.

## Sizing

An idle connection costs about 8.6 KB plain and 40 KB with TLS, measured at 10K connections on
macOS 15.8.1 x86_64 with OpenSSL 3.6.5 and Asio 1.36 (http `docs/perf/idle.md:56,75-82`, at
http:76f698d plain and http:ad6771f TLS). So `max_clients` 1024 over TLS is about 41 MB.

## Limits

- A note, not a build: the `Limits` and `Tls` field names, `server_context` and
  `raise_open_files` are proposals the http and reactor quests may rename. The stop source's type
  is task's to name.
- service-shape is a DRAFT at task:95798a0. It still spells Xapiand D132's names as `serve`, the
  `service` concept and a `stop_signals&` parameter (`service-shape.md:94-120`), and its signals
  row keeps the dump on a `signal_set` (`:207`); this note uses the new names and runs the dump on
  the signal thread, and task's rename quest takes both.
- Xapiand's `--max-clients` today bounds no connection (`manager.cc:950`); Xapiand D72 makes it a
  bound, so a deployment passing 10 refuses its eleventh connection.
- Prism pins http:d76c5ef (prism `CMakeLists.txt:22`); http's head has no
  `tls_connection_factory_timed` (http `CHANGELOG.md:152`), so Prism moves with `Limits`.
- Not checked here: the one-descriptor-per-connection measurement (job 261112-101615-0bdb50, not
  in today's job store; the reactor quest measures it again), Detent's reserve, the reconnect cost
  of `strict` for Detent's clients (Detent's adoption measures it; an Xapiand D62 case keeps
  resumption), and the stock soft limits, which are the documented defaults.
- Silent today: Detent and Prism hold idle connections forever (no idle timeout); Xapiand plain HTTP
  has no idle close and no bound at all.

## Adoption order

1. http: `Limits`, `Tls` and the constructor; the response options keep only transforms; the
   close-idle call; the held-poll test of Settled 1. Xapiand takes it after Phase 7c (Detent D81).
2. reactor: `tls::server_context` with Xapiand's tests moved over, and `raise_open_files`, tested
   with a soft limit of 1024 under a higher hard limit.
3. task: service-shape's `group`, `periodic`, `debounce`, `lifecycle` and `component`, with
   `stop_signals` as one stop source (with the dump signals), and the process step moved from
   `detent_cli`.
4. Xapiand adopts first, as the appendix maps. Then the Detent campaign adopts detent-authority,
   the relay and detent-agent (quest server-composition-adoption, with loop-idle-waits) and Prism
   (quest prism-server-composition, repo prism), in step (Detent D122, Xapiand D138).

## Appendix: Xapiand's adoption

`src/manager.cc` (1,409 lines), `src/manager.h` and `src/main.cc` at Xapiand:eb3dcfa80, by
responsibility. "Library" means it moves to task, http or reactor; "component" means a
`task::component` under `lifecycle`; "app" means it stays Xapiand's as values or code.

| Responsibility | manager.cc (and main.cc) | Step | Destination |
|---|---|---|---|
| Shutdown timing: grace 5 s, reserve 5 s, grace minimum 250 ms, `default_shutdown_write_bound` (35 s), `http_shutdown_grace(left)` | 143-168; tests `test_node.cc:862,1061` | 4 | Library. `--shutdown-timeout-ms` maps onto `stop_timing::bound`; the grace is `Limits`' fixed 5 s (Xapiand D77). The reserve and the adaptive grace are deleted (service-shape D7). |
| Control loop: `Reactors` (reactor, `AsioHost`, `control::Tasks`), `run_loop`, `break_loop`, `run_control`, `drain_control`'s 10 ms poll | 176-215, 540-567, 1006-1029 | 6 | Library: `asio_scheduler` on the main thread and `task::group`, whose join wakes at zero (service-shape D5). `control_plane.h` retires into task. Binding `engine::AsioHost` to the loop stays app code. |
| Signals: self-pipe, `signal_sig`, `signal_loop`, `signal_sig_impl`, "you insisted", `sig_exit` | 186-214, 459-499, 579-697; `main.cc:203-300` | 3 | Library: `task::stop_signals`. The SIGUSR1 and SIGINFO dump stays app code, run from the signal thread. |
| Shutdown driver: `shutdown`, `shutdown_impl`, `shutdown_async`, `shutdown_retry`, `shutdown_checks`, `try_shutdown`, `ready_to_end*`, `control_task_failed` | 184, 570-758, 1243-1256 | 7 | Deleted: `lifecycle` plus `signals.fail()`. The 5 s retry goes (C8). |
| Ordered stop: `join()` stops 1-5, abandon `_Exit(EX_TEMPFAIL)`, teardown order; `unfinished_work` | 1032-1240; `main.cc:908-926` `cleanup_manager` | 7 | Components: Http's drain (stop 1: `IndexChores::cancel_all`, `close`, `destroy_roots`), Autocommit's drain (stop 2), Registry's drain (stop 3) and its `flush()` (WAL and fsync, stops 4-5). `main` logs what the lifecycle reports unfinished and exits `EX_TEMPFAIL`. `atexit(cleanup_manager)` is deleted. |
| State: `schemas`, `database_pool`, `wal_writer`, `index_settings_resolver`; `readers_per_index` | 265-310 | 6 | Components: Registry (pool, WAL writer, fsyncher, the data-directory `flock`) and SchemaCache. The resolver is plain state with no lifecycle, passed by reference. `readers_per_index` is an app value. |
| Housekeeping: `control::Periodic` 1 min, `housekeeping_tick`, `housekeeping_ticks`, `housekeeping_period` | 182, 500-516, 826, 981 | 8 | Library `task::periodic`, owned by SchemaCache. The tick is app code; tests read its count (`test_node.cc:454,683-686`). |
| Autocommit: `control::Debounce<Endpoint>`, `schedule_autocommit` | 183, 300-307, 533-537 | 8 | Library `task::debounce`, in an Autocommit component, reached by reference from its callers (`shard.cc:1594`, `handler.cc:3331`). |
| HTTP wiring: `make_servers` | 894-985 | 4, 5, 6 | Limits (942-958) map to `http::Limits`, with `max_in_flight` 1000. The TLS factory (926-947) becomes `Tls`; its failure-log hook stays app code. Bind options and `reuse_port` (901-908, 951-954), compression, `AccessLog` and the lag probe (956-957) are app values. `http_hosts`, one `AsioHost` per reactor (960-966), stays app code. The housekeeping start (981) moves to SchemaCache's `start()`, the fsyncher start (984) to Registry's. `http_tries` (912) is dead. |
| Ready: `setup_node*`, `set_ready_impl`, `State::READY`, metric labels, "Ready to Rock" | 852-1003, 1382-1397 | 7 | The `ready` callback plus Http's `start()`. `State::READY` stays app (the tests wait on it, `test_node.cc:463`). |
| Descriptor budget and TLS check | `main.cc:338-490,1105-1118`; `tls.cc:51-76` | 4, 5 | Library: `raise_open_files` and `server_context`. Sizing the database pool against the limit stays app code, and its 7 per index is in the reserve. |
| Node identity: node name file, `host_address`, `init` (preloads stopwords and MIME types, the local `Node`), the name check | 337-456, 761-805 | before 6 | App: a node module `main` calls before `lifecycle`, with the preloads before any listener. |
| Resolver forwarding: `resolve_index_settings`, `resolve_index_endpoints`, `invalidate_settings` | 330-335, 1259-1283 | 6 | Deleted: callers use `IndexResolverLRU` by reference (C6). |
| Metrics: `server_metrics_impl`, `reactor_lag_metrics`, the `http_clients` counter (it counts requests, not connections: `search_views.cc:2755-2776`) | 1286-1380 | - | App: a function over the components' counters; the lag histograms come from reactor. |
| Global accessor: `_manager`, `make`, `manager`, `reset`, `get_state`, `spawn_control`, `control_lag` | 141, 519-530; `manager.h:235-303` | 6 | Deleted (C6). 71 `XapiandManager::` uses outside manager.cc and manager.h, and 214 lines naming the manager, 96 of them in `test_node.cc` (`git grep -w`). The global `tls_context` (`tls.h:40`) goes with it. |
| Process: `detach`, `writepid`, `demote`, `usedir`, logging, banner, dump and restore modes (which run `setup()` without a server) | `main.cc:492-760,840-905,992-1166` | 2, 5 | Library: the process step (C7) replaces `detach` and `writepid`. `demote` stays app code after the TLS step. Dump and restore run the Registry under `lifecycle`, with the tool's end as its stop source (Xapiand D132). |

About 1,700 lines of manager.cc and manager.h dissolve, with about 350 lines of main.cc (signals,
descriptor budget) and `control_plane.h`; `test_node.cc`'s harness is rewritten. The order:

1. Move `control::*` onto task's `group`, `periodic` and `debounce`, with no behavior change.
2. Options, `Limits`, TLS and the descriptor step: `--max-clients` becomes a bound (Xapiand D72);
   add `--idle-timeout-ms`, `--shutdown-timeout-ms` and `--reactors`; delete
   `--tls-max-connections`. Plain HTTP gains the bound and the idle close.
3. Pass state by reference (C6): components take their state from `main`, and the global accessor
   and the test harness move with it. No behavior changes, so it can precede step 4.
4. Components, `lifecycle` and `stop_signals` as its stop source: Registry, SchemaCache,
   Autocommit and Http. Delete `join` and the shutdown machinery. QUIT is a stop source: it calls
   `request_stop`, and FLUSH?clients calls close-idle (Xapiand D76, D132).
5. The process step (readiness, the locked pid file, the data-directory `flock`), node identity
   and metrics.

Steps 3 and 4 are the large ones.
