# Retrieval Trace Contract v1

This document records the executable Phase 0 contract. The authoritative
machine-readable schema is `retrieval-trace-event-v1.schema.json`; the runtime
does not emit this event until Phase 2.

## Envelope

- SSE event name: `response.retrieval_trace`
- Payload discriminator: `type = retrieval_trace`
- Schema version: `1.0`
- `trace_id` identifies the whole retrieval session, not one attempt. Retries
  and query rewrites keep the same `trace_id`; they are summarized by
  `attempt_count` and `query_rewrite_count`.
- Unknown fields are rejected by the producer model. Consumers must ignore
  unknown additive fields and unknown events for forward compatibility.
- A new optional field or enum member requires a minor version. Removing or
  changing the meaning/type of a field requires a major version and a migration
  period.

## Score and rank semantics

| Field | Meaning |
|---|---|
| `dense_distance` | Raw dense-provider distance; lower is better. It is never converted to confidence. |
| `dense_rank` | One-based position in dense retrieval results. |
| `dense_relevance_score` | Calibrated relevance only; `null` in v1 because no named calibration exists. |
| `rerank_score` | Raw reranker-provider score with provider semantics; not a probability or answer confidence. |
| `rerank_rank` | One-based position after reranking; `null` if reranking was not applied. |
| `selected` | Whether the chunk actually entered generation context. |

`candidate_count` equals the number of source records in the event and
`selected_count` equals the number whose `selected` flag is true.
Every `(source_id, chunk_ref)` pair is unique. `selected=true` is the explicit
attribution that the source/chunk entered the generation context.

## Session and stage facts

`attempt_count` counts all retrieval attempts in the session and
`query_rewrite_count` counts rewrites. Both are non-negative counters; neither
the original query nor rewritten query text is permitted in the contract.

Each stage has its own `status` and `failure`. The closed stage taxonomy is:

`query_rewrite`, `dense_retrieval`, `filtering`, `reranking`, and
`context_selection`.

A stage appears at most once in the final event and summarizes its terminal
state across the session. A failed overall event identifies at least one failed
stage; a degraded event identifies at least one degraded or failed stage.

## Failure taxonomy

The closed v1 taxonomy is:

`no_candidates`, `below_relevance_threshold`, `filter_eliminated_all`,
`reranker_eliminated_all`, `source_unavailable`, `index_unavailable`,
`timeout`, `provider_error`, and `unknown`.

Only calibrated thresholds may produce `below_relevance_threshold`. Unknown
exceptions map to `unknown`; raw exception or provider text is prohibited.

## Confidence capability

Answer confidence is not supported in v1. The four fields are locked to:

```json
{
  "answer_confidence": null,
  "confidence_status": "not_supported",
  "confidence_method": null,
  "calibration_version": null
}
```

Dense distance, dense relevance, reranker score, answer confidence, and
classifier confidence are distinct concepts.

## Version contract

The contract captures all retrieval dependencies: retrieval pipeline version,
vector-index provider/version, at least one of `index_version` or
`corpus_revision`, embedding model/version, query-rewriter model/version,
reranker model/version, and chunking strategy/version. Generation model/version
remain recorded for end-to-end reproducibility.

Optional component identities are atomic: query-rewriter model/version and
reranker model/version are each both present or both `null` when that component
was not configured. Required values are non-empty. Production values must not
use placeholders such as `unversioned`.

## Privacy and retention baseline

The event contains opaque tenant-scoped identifiers, scores, ranks, attempt and
rewrite counts, latency, stage/overall status and failure, and component
versions only. It must not contain original or rewritten query text,
chunk/context text, prompts, model answers, API keys, raw exceptions, provider
responses, or data from another tenant.

Phase 0 and the MVP require event delivery, not persistence. If metadata and
metrics are persisted later, retention is at most 90 days and is
tenant-configurable. Opt-in encrypted content, if ever introduced through
change control, is retained for 7–30 days. Expiry/deletion must be auditable;
raw API keys are never stored.

## Ownership boundary

LLMaaS owns stable chunk identity, retrieval/generation technical facts,
technical failure evidence, component versions, latency/usage, and offline
retrieval evaluation. The consuming Advisor owns conversation outcomes, topic
attribution, business KPIs, final RCA, recommendations, decisions, and product
retention policy. Correlation uses `trace_id` and opaque identifiers; LLMaaS
does not issue final product RCA or recommendations.

## Fixtures and current status

Contract fixtures under `tests/fixtures/retrieval_trace/v1` cover English and
Persian success/empty/degraded/failed scenarios without carrying query or
content. As of Phase 0, the schema, taxonomy, confidence/version/privacy
contracts and contract tests exist. Runtime trace emission, stable identity
completion, persistence, and consumer integration remain outside Phase 0.
