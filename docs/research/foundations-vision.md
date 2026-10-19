# Research brief: the best infrastructure, built on foundations

Status: brief for a researcher, then an architect (owner, 2026-10-18). Nothing here is decided
beyond what the owner said; names are working names.

## The owner's vision

"Implement all the best infra technologies we've seen using our foundations." The Kronuz C++
libraries (this catalog, which may be renamed *foundations*) are the base; strata is the
storage core on top; the systems below are built from them. "Our solutions should let the
user choose their side (availability vs consistency)." "Maybe we don't have to force all
this into strata; we can have other libraries in foundations that could be shaped better,
maybe reusing bits from strata (maybe strata itself has to be abstracted or split, maybe
not)."

## The systems, with the best-known version of each

| System | Best known | Working name or home |
|---|---|---|
| Embedded storage engine | RocksDB | strata (in progress; must beat RocksDB without its write stalls) |
| Search engine and server | Lucene, Tantivy, PISA; Elasticsearch, Unicorn | on strata: the search library (tropo, quarry or seam) and its server (strato; today's Xapiand) |
| Sharded replicated KV | ZippyDB | shale |
| Wide-column store | Cassandra, ScyllaDB (Discord), Bigtable | a shale data model (partition + clustering keys) |
| Social graph | TAO | shale plus a cache tier; strata's `graph` profile |
| Distributed log / streams | Kafka, LogDevice | on journal + consensus |
| Ordered queue | FOQS | on shale |
| Real-time analytics | Scuba, Druid | memory-resident, replicated, time-windowed; columns and sketches |
| Time series | Gorilla, Monarch | strata's `log` profile and codecs |
| Cache | CacheLib, memcache + mcrouter | a hybrid DRAM + flash cache library |
| Blob store | Haystack, f4, Tectonic | on storage + completion + the shard manager |
| Vector search | FAISS | inside the search library |
| Runtime configuration | Configerator, JustKnobs | Detent (exists) |
| Coordination | ZooKeeper, Chubby, etcd | a small store on consensus |
| Shard management | Shard Manager, Slicer | one shared service (strata Track D) |
| Discovery and routing | ServiceRouter | cluster gossip + shard maps |

## Cross-cutting requirements

1. **One mechanism per concern.** One storage core, one replication mechanism (consensus per
   shard), one shard manager, one transport. A second replication mechanism (leaderless,
   Dynamo-style) is rejected; say if the research finds that wrong, with evidence.
2. **Choose your side.** Availability or consistency per index or table, with per-request
   overrides, on a spectrum like Cosmos DB's five levels on one protocol. A later opt-in preset
   accepts minority-side writes during partitions and merges deterministically on healing (LWW
   on a hybrid logical clock, or CRDTs). Exact guarantees and loss windows per level.
3. **Memory first where it pays.** A memory-resident preset: replicated in memory, segments
   built in RAM and searchable at once, a background tier to disk for persistence and longer
   retention; restarts recover from peers, the disk tier, or shared memory.
4. **Retention as a first-class model.** Scuba drops data past a limit; ScyllaDB drops by TTL,
   often by time window. Candidates: time-windowed segments in strata (merges never cross
   windows; dropping is deleting whole segments) and time-based shards above it (rollover).
5. **No stalls.** Background work (merges, renumbering, checkpoints, compaction) never turns
   into latency cliffs under sustained load (see docs/research/no-stalls in strata when done).
6. **The workload.** Millions of indexes or shards per host, tens of thousands open per
   process; per-shard efficiency on one thread; parallelism adapts through one shared pool.

## Foundations the vision is missing (today's catalog has 77 libraries)

Typed RPC with deadlines, cancellation and backpressure; distributed tracing; hybrid logical
clocks; admission and backpressure controllers; the shard manager as a library; CRDTs; a
hybrid DRAM + flash cache with frequency-aware admission; deterministic simulation as a
library (FoundationDB-style); schema evolution; columnar vectorized execution; approximate
sketches (HyperLogLog, t-digest or KLL, Count-Min); encryption at rest.

## What the researcher delivers

A research note: for each system, the essential mechanisms that made the best version win
(with sources), which of them are shared across systems, and the smallest set of foundations
libraries and strata pieces that covers them all without duplication. Where strata should be
split or abstracted, and where a separate library fits better. At least three architectural
options for the whole stack, including one that breaks a common assumption, with their costs.
The order to build in, each step making the next cheaper. Prototype only where a choice hinges
on a number.

## What the architect then does

Turns the chosen option into a stack architecture: the libraries and their boundaries, the
shared spine (storage core, replication groups, shard manager, transport), each system's
design brief, and the order of phases, reviewed against strata's PLAN and the catalog's rules.
