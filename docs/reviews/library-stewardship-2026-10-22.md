# Library maintenance, October 22, 2026

All 81 active catalog entries have a CI workflow and a verified README link to cpp-libraries. Every audited repository has a license file. The [commit ledger](library-stewardship-2026-10-22.json) records the metadata changes; it does not certify all libraries' latest runtime results.

## CI and repository lifecycle

| Repository | Result |
| --- | --- |
| btree | Shared CI added; [first matrix](https://github.com/Kronuz/btree/actions/runs/39769650414) and [guarded-growth matrix](https://github.com/Kronuz/btree/actions/runs/39771138527) both pass all seven active jobs. TSan is excluded for the nonconcurrent container API. |
| generation-cache | Shared compiler/platform, ASan/UBSan and TSan matrix [passes all eight jobs](https://github.com/Kronuz/generation-cache/actions/runs/39770440406). |
| server | Archived after recording reactor/http/prism as architectural successors. The README also links the catalog; history and pinned commits remain available. |

GitHub renamed cpp-btree to btree while retaining 282 stars and 50 forks. The old web URL returns HTTP 301 and both Git URLs resolve identically. Keep the old repository name unused to preserve the redirect. `btree::btree` and the compatible `cpp_btree::cpp_btree` alias share one CMake interface target; header paths are unchanged.

## Licenses and attribution

Btree retains Apache-2.0 and Google's 2013 notices. The maintained project notice now spans 2019-2026 in its headers, README and new NOTICE file. The Apache license text is unchanged.

Static-string retains BSL-1.0. Xapiand [085939b9f, December 18, 2017](https://github.com/Kronuz/Xapiand/commit/085939b9fa7581256203bcf162ab27194cc66c31) introduces `static_str.hh` with Andrzej Krzemienski's 2017 notice and the full Boost license. The [February 2018 refactor](https://github.com/Kronuz/Xapiand/commit/82efa13ef7fef62a014b60dcaa50107d384d67f8) retains that derivation. The copied 2015 start date for Dubalu is corrected to 2017-2019; a separate 2026 Germán Méndez Bravo notice covers current work. Source, LICENSE and README agree. Extraction from Xapiand does not turn the imported implementation into MIT.

Existing personal notices in base-x, constexpr-phf, ctrie and uinteger_t extend through current maintenance, with other authors' dates preserved. Older Dubalu and third-party notices elsewhere remain historical attribution; their age alone does not establish an error. HTTP-parser's customized root notice declares MIT and retains its upstream credits, although GitHub identifies it as NOASSERTION. Vendored code keeps its own notices.

## Btree issue 2

[Issue 2](https://github.com/Kronuz/btree/issues/2) remains open. The zero-storage assertion was removed in [fc4f941](https://github.com/Kronuz/btree/commit/fc4f9410fbaf6bda1c49a6e702423e1ad56aaab4), and mixed diagnostic fixtures now run in CI. The report also describes a later segfault without the application type or a minimal reproducer. That crash is unverified, so closing the complete report as fixed would overstate the evidence.

## Coordination

README and attribution commits use `[skip ci]` and change no implementation or build behavior. Other library work is preserved; local clones and uncommitted files are not reset. Consumers and maintainers should fetch/rebase when ready, using the ledger to identify the metadata-only commits. Immutable dependency pins do not change automatically. Detent's guarded-growth integration qualification remains separate.
