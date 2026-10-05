# Concurrent property assessments

The user asked to stop the long sequential assessment, add the proposed eight-worker pool and live
completion counts, then resume it. Completed readings must remain durable and current readings must
be skipped. This is an approved behavior change, not a fidelity defect.

Scope: the assessment pass and its configuration (AC-23, AC-24), building on the existing
fingerprint, cost, failure-isolation and pacing requirements (AC-9, AC-11, AC-13, AC-20). No model,
reasoning effort, dossier content, criteria or assessment fingerprint changes. The shared network
implementation needs thread-safe pacing and connection ownership, with traced source-layer tests.
Existing screens already poll persisted progress, so new core progress is visible on both surfaces.
