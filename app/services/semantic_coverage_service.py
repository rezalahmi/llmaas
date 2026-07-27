import json
from collections import defaultdict
from typing import Any, Awaitable, Callable

from app.repositories.evaluation_repository import (
    get_evaluation_run_for_worker,
    list_dataset_cases,
    mark_evaluation_completed,
    mark_evaluation_failed,
    mark_evaluation_running,
    renew_evaluation_lease,
    replace_evaluation_results,
)
from app.schemas.file_search import FileSearchQuery


EVALUATOR_VERSION = "semantic-coverage.v1"
Retriever = Callable[[FileSearchQuery], Awaitable[Any]]


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def reciprocal_rank(ranked_ids: list[str], gold_ids: set[str]) -> float:
    for index, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in gold_ids:
            return 1.0 / index
    return 0.0


def hit_at_k(ranked_ids: list[str], gold_ids: set[str], k: int) -> float:
    return float(any(chunk_id in gold_ids for chunk_id in ranked_ids[:k]))


async def evaluate_semantic_coverage_cases(
    cases: list[dict[str, Any]],
    *,
    vector_store_id: str,
    config: dict[str, Any],
    retriever: Retriever | None = None,
    progress_callback: Callable[[], Awaitable[None]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if retriever is None:
        from app.services.file_search import search_in_vector_store

        retriever = search_in_vector_store

    k_values = sorted(set(config.get("k_values") or [5, 10]) | {5, 10})
    max_k = max(k_values)
    include_paraphrases = config.get("include_paraphrases", True)
    include_language_slices = config.get("include_language_slices", True)

    totals = {k: 0.0 for k in k_values}
    reciprocal_rank_total = 0.0
    paraphrase_drop_total = 0.0
    paraphrase_count = 0
    language_totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {"count": 0.0, **{f"hits_{k}": 0.0 for k in k_values}}
    )
    results: list[dict[str, Any]] = []

    for case in cases:
        if progress_callback is not None:
            await progress_callback()
        gold_ids = set(case["gold_chunk_ids"])
        response = await retriever(
            FileSearchQuery(
                vector_store_ids=[vector_store_id],
                query=case["query"],
                max_results=max_k,
            )
        )
        ranked_ids = [item.document_id for item in response.results]
        hits = {k: hit_at_k(ranked_ids, gold_ids, k) for k in k_values}
        rr = reciprocal_rank(ranked_ids, gold_ids)

        for k, hit in hits.items():
            totals[k] += hit
        reciprocal_rank_total += rr

        language = case.get("language") or "unspecified"
        if include_language_slices:
            language_totals[language]["count"] += 1
            for k, hit in hits.items():
                language_totals[language][f"hits_{k}"] += hit

        paraphrase_details = []
        if include_paraphrases:
            for paraphrase in case.get("paraphrases") or []:
                if progress_callback is not None:
                    await progress_callback()
                paraphrase_response = await retriever(
                    FileSearchQuery(
                        vector_store_ids=[vector_store_id],
                        query=paraphrase,
                        max_results=max_k,
                    )
                )
                paraphrase_ranked_ids = [
                    item.document_id for item in paraphrase_response.results
                ]
                paraphrase_hit = hit_at_k(
                    paraphrase_ranked_ids, gold_ids, max_k
                )
                paraphrase_drop_total += max(
                    0.0, hits[max_k] - paraphrase_hit
                )
                paraphrase_count += 1
                paraphrase_details.append(
                    {
                        f"hit_at_{max_k}": bool(paraphrase_hit),
                        "ranked_chunk_ids": paraphrase_ranked_ids,
                    }
                )

        ranked_results = [
            {
                "chunk_id": item.document_id,
                "dense_score": item.dense_score,
                "dense_distance": item.dense_distance,
                "dense_rank": item.dense_rank,
                "rerank_score": item.rerank_score,
                "rerank_rank": item.rerank_rank,
                "score": item.score,
            }
            for item in response.results
        ]
        score = hits[max_k]
        severity = "info" if score else "critical"
        results.append(
            {
                "case_id": case["id"],
                "metric": "semantic_coverage",
                "score": score,
                "severity": severity,
                "details": {
                    "language": case.get("language"),
                    "intent": case.get("intent"),
                    "rarity": case.get("rarity"),
                    "gold_chunk_ids": sorted(gold_ids),
                    "hits": {f"recall_at_{k}": hits[k] for k in k_values},
                    "reciprocal_rank": rr,
                    "ranked_results": ranked_results,
                    "paraphrases": paraphrase_details,
                },
            }
        )

    case_count = len(cases)
    denominator = max(1, case_count)
    summary: dict[str, Any] = {
        "case_count": case_count,
        **{
            f"recall_at_{k}": totals[k] / denominator
            for k in k_values
        },
        "mrr": reciprocal_rank_total / denominator,
        "answerable_retrieval_rate": totals[max_k] / denominator,
        "paraphrase_robustness_drop": (
            paraphrase_drop_total / paraphrase_count
            if paraphrase_count
            else 0.0
        ),
        "paraphrase_count": paraphrase_count,
    }

    if include_language_slices:
        summary["language_slices"] = {
            language: {
                "case_count": int(values["count"]),
                **{
                    f"recall_at_{k}": (
                        values[f"hits_{k}"] / values["count"]
                        if values["count"]
                        else 0.0
                    )
                    for k in k_values
                },
            }
            for language, values in sorted(language_totals.items())
        }

    return summary, results


async def run_semantic_coverage_evaluation(pg, *, run_id: str) -> None:
    run = await get_evaluation_run_for_worker(pg, run_id=run_id)
    if not run:
        raise ValueError(f"Evaluation run {run_id} was not found")
    if run["status"] == "completed":
        return

    claimed = await mark_evaluation_running(pg, run_id=run_id)
    if not claimed:
        return

    try:
        cases = [
            dict(row)
            for row in await list_dataset_cases(
                pg, dataset_id=run["dataset_id"]
            )
        ]
        if not cases:
            raise ValueError("Evaluation dataset has no cases")

        summary, results = await evaluate_semantic_coverage_cases(
            cases,
            vector_store_id=run["vector_store_id"],
            config=_as_dict(run["config"]),
            progress_callback=lambda: renew_evaluation_lease(
                pg, run_id=run_id
            ),
        )
        await replace_evaluation_results(
            pg, run_id=run_id, results=results
        )
        await mark_evaluation_completed(
            pg, run_id=run_id, summary=summary
        )
    except Exception as exc:
        await mark_evaluation_failed(pg, run_id=run_id, error=str(exc))
        raise
