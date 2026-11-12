> Status: DRAFT (2026-11-12), for review by the Xapiand lead. Reads task:0e71a38, http:473bbc3,
> reactor:4de16f2, Detent:11f793c5, prism:e0aea0e and Xapiand:9afebe6c5. Line numbers are at those
> commits. Nothing here is built.

# How a Kronuz server is put together

One composition for Prism, Detent (detentd and detent-relay) and Xapiand, so the three mains read
alike. It extends [service-shape](https://github.com/Kronuz/task/blob/0e71a38/docs/design/service-shape.md)
(`serve`, `stop_signals`, the `service` concept, one shutdown) with what comes before `serve`: the
options, the limits and TLS. Decisions D76, D79-D82 (Detent) and D62, D72-D74 (Xapiand) set the rules.
No code changes here; each app adopts the note in its own quest.

## Summary

A `main` has seven steps, in this order: options, limits, TLS, loop and services, `serve`, signals,
housekeeping. Libraries own the steps (reactor: loops, accept, admission, the connection bound; http:
idle close and one `Limits` struct; task: the service shape; no new library, D73). Apps own only
values. A difference in a value is not a deviation; a different code path is, and stays only with a
reason (D82), and a reason of cost needs Xapiand D62: the unified shape costs over 5% CPU or 10% p99
after optimizing it, with before and after numbers. No deviation below has that case today.

## Composition

1. **Options.** Every limit is a flag and a config key spelled alike (`--max-clients`, `max_clients`);
   durations are milliseconds, suffixed `_ms`. The table under "Options" fixes names and defaults. The
   parser is the app's.
2. **Limits.** Options map onto one struct that http takes whole, so no setter can be forgotten:

   ```cpp
   struct http::Limits {                                   // contract for the http quest (D81)
   	std::size_t max_clients = 1024;      // open connections, plain and TLS, idle ones counted
   	std::size_t max_in_flight = 1024;    // requests admitted per loop; 0 = no cap
   	std::chrono::milliseconds idle_timeout{75'000}, header_timeout{30'000}, inactivity_timeout{60'000};
   	std::chrono::milliseconds request_timeout{0};   // absolute per request; off unless the app sets it
   	std::chrono::milliseconds shutdown_grace{5'000};
   	std::size_t max_body = 16u << 20;
   	std::chrono::milliseconds tls_handshake{5'000};  std::size_t tls_handshakes = 64;
   };
   HttpAsioService(HttpHandler&, std::size_t reactors, const Limits&, ConnectionFactory = {});
   ```

   It replaces the constructor's bare `in_flight_limit` and `maximum_connections`
   (`http_asio.h:1134`) and the setters `set_idle_timeout`, `set_header_timeout`, `set_inactivity_timeout`,
   `set_request_timeout`, `set_max_body` and `set_shutdown_grace` (`:1157-1176`); `max_clients` reaches
   `reactor::TcpServer::set_connection_limit` (`reactor.h:629`). The TLS factory drops its own
   connection count (`http_asio_tls.h:66-70`), which today duplicates the reactor's bound: one bound
   covers plain and TLS.
3. **TLS.** One reactor function builds the server context: Xapiand's `tls_setup` (`tls.cc:51-76`)
   moved to `reactor::tls::server_context(options, max_clients)`. It refuses a key readable by group
   or others (all three apps, Xapiand D77), a key that does not match the certificate, and a
   certificate not yet valid or expired. It throws; `main` logs and exits `EX_CONFIG`. The descriptor
   budget is one check at server start, plain and TLS alike: `max_clients` connections at one
   descriptor each (measured 1.000 per idle connection, plain and TLS, job 261112-101615-0bdb50) plus
   a stated reserve must fit `RLIMIT_NOFILE`. It replaces Xapiand's `FDS_PER_CLIENT = 2`
   (`main.cc:86,441-488`, a kqueue-era constant) and the TLS-only `max + 64` (`tls.cc:56`).
   It runs before privileges drop and before any service starts (`main.cc:1105-1118`).
4. **Loop and services.** The process has one control loop, which `main` runs on the main thread
   (service-shape's `main`). Services are constructed in dependency order: state (registry,
   authority), housekeeping owners, then the http service built from `Limits` and the TLS factory.
5. **`serve`.** `serve(loop, signals, {}, ready, state..., http)` starts them in order, calls `ready`,
   and on a stop stops and drains in reverse, then `flush()`. `ready` is the same callback everywhere:
   daemon readiness, then one log line. See service-shape's "Stop and drain order".
6. **Signals.** `task::stop_signals` is the first object in `main`. SIGINT and SIGTERM mean stop,
   hurry, flush-then-die (D80). Xapiand's SIGUSR1 and SIGINFO dumps stay on their own `signal_set`.
7. **Housekeeping.** Periodic work is `task::periodic`, and a debounce is `task::debounce`, each owned
   by the service whose state it serves, each a task awaiting the wheel through `scheduler_ref::arm`
   (D76, D79). Nothing polls at shutdown; a `drain` joins the service's `group`.

## Options

Shared names and defaults. "Today" cells cite each app's current spelling.

| Shared (flag, key) | Default | detentd | detent-relay | Prism | Xapiand |
| :---- | :---- | :---- | :---- | :---- | :---- |
| `--max-clients`, `max_clients` | 1024 | constant 1024, no option (`detentd/main.cc:34,176-177`) | `connections`, 1024 (`configuration.cc:62`, `configuration.hh:21`) | none on plain; TLS constant 1024 (`main.cc:323-324,331`) | `--max-clients`, 1000, feeds the descriptor budget only (`opts.cc:51,186`, `main.cc:365`); `--tls-max-connections`, 1024, TLS only (`opts.cc:202`, `manager.cc:942-944`) |
| `--max-in-flight`, `max_in_flight` (per loop) | 1024 | 1024, the same constant (`main.cc:176`) | `connections` again (`host.cc:264-265`) | 256 (`main.cc:323,331`) | 1000 constant (`manager.cc:943,950`) |
| `--idle-timeout-ms`, `idle_timeout_ms` | 75000 | none | none; `idle_ms`, 60 s, is the session lifetime (`configuration.cc:80-81`) | none | 75 s constant, TLS only (`manager.cc:945`) |
| `--shutdown-timeout-ms`, `shutdown_timeout_ms` | 35000 | none: drain unbounded (`main.cc:214-222`) | none (`host.cc:397-408`) | none; reactor's 5 s grace (`reactor.h:759`) | not an option: 35 s bound (`manager.cc:155-158`), 5 s grace (`:145,955`) |
| `--tls-cert`, `--tls-key`, `--tls-ca` | unset: plain | `publisher_tls.{certificate,key,ca}`, all three (`service.cc:395-401,454-458`) | `certificate`, `private_key`, `ca`, required (`configuration.cc:59,94,187-192`) | `--tls-cert=F`, `--tls-key=F`; no CA (`main.cc:258-259`) | `--tls-cert`, `--tls-key`; no CA (`opts.cc:200-201`) |
| `--port`, `port` | per app: 8317, 8318, 8880, `XAPIAND_HTTP_SERVERPORT` | `--port` (`main.cc:131`) | `port` (`configuration.cc:90`) | positional (`main.cc:263`) | `--port` (`opts.cc:192`) |
| `--bind-address`, `bind_address` | loopback, except Prism and Xapiand: all | `publisher_bind` (`service.cc:460`) | `address` (`configuration.cc:88`) | none (`main.cc:341`) | `--bind-address` (`opts.cc:195`) |
| `--reactors`, `reactors` | hardware threads | `--reactors`, 4 (`main.cc:133`) | constant 2 (`host.cc:264`) | hardware threads (`main.cc:265`) | `--processors` (`opts.cc:189,380`) |

`--tls-ca` turns on client authentication; the relay and the authority require it. Xapiand keeps
`--processors`: it also sizes the WAL writers and fsynchers (`opts.cc:374-376`).

## Mains

By step, with the code each app calls today. detent-agent has no listener, so it shares only the signal, housekeeping and stop steps; its code is in
service-shape's table (`managed_host.cc:186-212`).

| Step | detentd | detent-relay | Prism | Xapiand |
| :---- | :---- | :---- | :---- | :---- |
| Options | `load_config`, env, flags (`detentd/main.cc:91-130`) | JSON only; four flags (`relay/main.cc:15-35`, `configuration.cc:50-60`) | hand loop, `--x=y`, positional port (`main.cc:247-264`) | CLI11 (`opts.cc:185-202`) |
| Limits | constructor 1024 and 1024, `set_request_timeout` 5 s (`service.hh:48`), `set_max_body` (`main.cc:176-181`) | `connections` twice, 2 loops, request timeout 65 s (`host.cc:264-269`) | constructor 256; bound on TLS only (`main.cc:323-331`) | idle, header, inactivity timeouts on TLS only; grace; body cap (`manager.cc:943-958`) |
| TLS | `reactor::tls::configure`, `tls_connection_factory` (`main.cc:166-171`) | `configure` in the loader (`configuration.cc:187-192`); always on | `configure`, `tls_connection_factory_timed`; `PRISM_TLS` build flag (`main.cc:43-46,320-324`) | `tls_setup`, before `demote` (`main.cc:1105-1118`) |
| Loop and services | `OwnerLoop` on its own thread (`owner_loop.hh:24-26`), authority, then http (`main.cc:173-176`) | `OwnerLoop`, registry, coordinators, listener (`host.cc:145,215-265`) | no state, no loop; app, `AccessLog`, listener (`main.cc:293-333`) | the manager's reactor, run on the main thread (`manager.cc:178-200,543-559`) |
| Start, ready | `start(port)`, lone-quorum poll, `ready()` (`main.cc:191-206`) | `ready()` from the `turn` loop (`host.cc:333-343`) | `start`, banner; no ready (`main.cc:341-343`) | `start` in `set_ready_impl` (`manager.cc:999`) |
| Signals | `std::signal` flag (`main.cc:183-184`) | `asio::signal_set` on the owner loop (`host.cc:285-289`) | `std::signal` flag (`main.cc:338-339`) | `sigaction`, self-pipe, a task (`main.cc:288-300`, `manager.cc:462-500`) |
| Housekeeping | runtime loop: yield while busy, else a 1 ms timer (`service.cc:1288,2780-2785`) | `turn`: post while progress, else a 1 ms timer (`host.cc:290-369`) | none | `control::Periodic` 1 min, `control::Debounce` autocommit, `PeriodicTimer` retry (`manager.cc:826,301-307,184`) |
| Stop | poll 5 and 200 ms, then ordered calls, no bound (`main.cc:198-222`) | main blocks on a promise, no bound (`host.cc:397-408`) | poll 100 ms, `service.stop()` (`main.cc:345-349`) | `join()`, one 35 s deadline (`manager.cc:1033-1135`) |

Deviations, each with its reason and whether a D62 case exists:

| Deviation | Reason | D62 case |
| :---- | :---- | :---- |
| Limits applied by setters and only on TLS (Xapiand), not at all (Detent, Prism) | History | None; `Limits` removes it |
| Relay and detentd drive 1 ms loops (yield or post while busy), not `periodic` | These drive the authority and coordinators; service-shape keeps a throughput check before and after (D1's escape) | None measured; the one deviation that can earn one |
| Loop on its own thread (`OwnerLoop`) | Today's code, not a design | None; Q4 |
| Signals as a flag polled by `main` (detentd, Prism); `signal_set` (relay) | History: neither tells a second or third signal apart (D6, D80) | None; `stop_signals` replaces both |
| TLS compiled out (Prism, Xapiand) | OpenSSL is optional | Not a shape: a build option |
| Absolute request timeout (detentd 5 s, relay 65 s) | A trickled request must not renew admission (`http_asio.h:97-99`) | Not a deviation: a `Limits` value |
| Relay TLS only, with client CA | The relay's protocol requires credentials | Not a deviation: it sets `tls_ca` |

## Decisions

| # | Decision | Lost, and why |
| :---- | :---- | :---- |
| C1 | One `http::Limits`, taken by the constructor | The setters: three mains set different subsets, and an unset limit is silently off |
| C2 | `server_context` lives in reactor, beside `configure` | Each app calling `configure` raw (only Xapiand checks the key and certificate); a new library (D73) |
| C3 | One name per option, flag and key alike; `_ms` durations | Unitless durations; Xapiand's unitless milliseconds (`opts.h:96-107`) are internal constants, not flags, so no Xapiand flag is renamed |
| C4 | A value that differs is an input, not a deviation | Listing every constant as a deviation: it hides the three that are not values |

## Settled

1. **Header and inactivity timeouts on every connection**, plain and TLS (Xapiand sets 30 s and 60 s
   for TLS only, `manager.cc:946-947`), after a detentd test that a held poll with its headers
   complete and no body read does not trip them (Xapiand lead agrees).
2. **A key readable by group or others is refused in all three** (owner, Xapiand D77).
3. **`--shutdown-timeout-ms`, `shutdown_timeout_ms`, default 35000**, mapped onto
   `stop_timing::bound`; the 5 s grace is fixed (owner, Xapiand D77).
4. **The loop runs on the main thread**, as service-shape's `main` and Xapiand do; Detent's
   `OwnerLoop` (`main.cc:208-210`; `host.cc:397`) gains a `run()` (Xapiand lead agrees).
5. **Defaults `max_clients` 1024 and `max_in_flight` 1024**, the largest present value, so no app
   is limited below today (Xapiand lead agrees).
6. **http gains a close-idle-now call** beside the idle timeout, so Xapiand's `FLUSH?clients`
   closes idle connections (Xapiand D76); the http quest names it in its contract.

## Sizing

An idle connection costs 14.4 KB plain and 97.7 KB with TLS (73.6 KB with asio's record buffers
allocated lazily), measured on macOS x86_64 with OpenSSL 4.1 and asio 1.36 (Xapiand lead). So
`max_clients` 1024 over TLS is about 100 MB.

## Limits

- A note, not a build: the `Limits` field names, `server_context` and the `Limits` constructor are
  proposals the http and reactor quests may rename. Xapiand's `--max-clients` today bounds no connection
  (`manager.cc:950`); D72 makes it a bound, so a deployment passing 10 would start refusing.
- Line numbers drift; the Detent cites differ from service-shape's by hundreds of lines
  (`service.cc:640-655` there, `:1288` here).
- Prism's pin of http (d76c5ef, 50 commits behind) has `tls_connection_factory_timed`; adopting
  `Limits` moves it onto the unified factory.
- Silent today: Detent and Prism hold idle connections forever (no idle timeout); Xapiand plain HTTP
  has no idle close and no bound at all.

## Checks

- A1: `sed -n '/^## Composition/,/^## Options/p' docs/server-composition.md | rg -c '^[0-9]\. \*\*'` prints 7.
- A2: `rg -n '^\| `--' docs/server-composition.md` finds eight rows, five shared with the quest's list
  plus port, bind address and reactors.
- A3: "Mains" has one row per step and one column per main; every deviation row names its D62 case.
- A4: the Xapiand lead's agreement, recorded in the journal.

## First steps

1. http: `Limits` and its constructor; the TLS factory drops its connection count (Xapiand takes it
   after Phase 7c, D81).
2. reactor: `tls::server_context`, with Xapiand's tests moved over.
3. Prism adopts the composition first (smallest main, no durable state), then detentd and relay, then
   Xapiand with its Phase 7c gate.
