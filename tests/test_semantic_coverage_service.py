import asyncio
import unittest
from types import SimpleNamespace

from app.services.semantic_coverage_service import (
    evaluate_semantic_coverage_cases,
    hit_at_k,
    reciprocal_rank,
)
from app.schemas.file_search import FileSearchResultChunk
from app.schemas.evaluations import (
    EvaluationDatasetCreate,
    SemanticCoverageConfig,
)
from pydantic import ValidationError


def result(chunk_id, dense_score, rerank_score):
    return SimpleNamespace(
        document_id=chunk_id,
        dense_score=dense_score,
        rerank_score=rerank_score,
        dense_rank=None,
        rerank_rank=None,
        dense_distance=1.0 - dense_score,
        score=rerank_score if rerank_score is not None else dense_score,
    )


class SemanticCoverageMetricsTests(unittest.TestCase):
    def test_coverage_config_always_includes_required_cutoffs(self):
        config = SemanticCoverageConfig(k_values=[3])
        self.assertEqual(config.k_values, [3, 5, 10])

    def test_dataset_requires_at_least_one_case(self):
        with self.assertRaises(ValidationError):
            EvaluationDatasetCreate(name="empty", cases=[])

    def test_internal_stage_scores_do_not_change_public_search_payload(self):
        chunk = FileSearchResultChunk(
            file_id="file_1",
            vector_store_id="vs_1",
            document_id="chunk_1",
            text="example",
            score=0.9,
            dense_score=0.8,
            rerank_score=0.9,
            dense_rank=2,
            rerank_rank=1,
            dense_distance=0.2,
        )

        payload = chunk.model_dump()

        self.assertNotIn("dense_score", payload)
        self.assertNotIn("rerank_score", payload)
        self.assertNotIn("dense_rank", payload)
        self.assertNotIn("rerank_rank", payload)
        self.assertNotIn("dense_distance", payload)

    def test_reciprocal_rank_uses_first_gold_chunk(self):
        self.assertEqual(
            reciprocal_rank(["chunk_a", "chunk_b", "chunk_c"], {"chunk_b"}),
            0.5,
        )

    def test_hit_at_k_respects_cutoff(self):
        ranked = ["chunk_a", "chunk_b", "chunk_c"]
        self.assertEqual(hit_at_k(ranked, {"chunk_c"}, 2), 0.0)
        self.assertEqual(hit_at_k(ranked, {"chunk_c"}, 3), 1.0)

    def test_summary_includes_recall_mrr_paraphrase_and_language_slices(self):
        ranked_by_query = {
            "اصل اول": [
                result("gold_1", 0.7, 0.9),
                result("other", 0.8, 0.2),
            ],
            "بازنویسی اول": [result("gold_1", 0.6, 0.8)],
            "اصل دوم": [
                result("other_1", 0.9, 0.9),
                result("other_2", 0.8, 0.8),
            ],
            "بازنویسی دوم": [result("gold_2", 0.5, 0.7)],
        }

        async def retriever(query):
            return SimpleNamespace(results=ranked_by_query[query.query])

        cases = [
            {
                "id": "case_1",
                "query": "اصل اول",
                "gold_chunk_ids": ["gold_1"],
                "paraphrases": ["بازنویسی اول"],
                "language": "fa",
                "intent": "policy",
                "rarity": "head",
            },
            {
                "id": "case_2",
                "query": "اصل دوم",
                "gold_chunk_ids": ["gold_2"],
                "paraphrases": ["بازنویسی دوم"],
                "language": "fa",
                "intent": "policy",
                "rarity": "tail",
            },
        ]

        summary, results = asyncio.run(
            evaluate_semantic_coverage_cases(
                cases,
                vector_store_id="vs_1",
                config={
                    "k_values": [1, 5, 10],
                    "include_paraphrases": True,
                    "include_language_slices": True,
                },
                retriever=retriever,
            )
        )

        self.assertEqual(summary["case_count"], 2)
        self.assertEqual(summary["recall_at_5"], 0.5)
        self.assertEqual(summary["recall_at_10"], 0.5)
        self.assertEqual(summary["mrr"], 0.5)
        self.assertEqual(summary["paraphrase_count"], 2)
        self.assertEqual(summary["paraphrase_robustness_drop"], 0.0)
        self.assertEqual(summary["language_slices"]["fa"]["recall_at_10"], 0.5)
        self.assertEqual(len(results), 2)
        self.assertNotIn("query", results[0]["details"])
        self.assertEqual(
            results[0]["details"]["ranked_results"][0]["dense_score"],
            0.7,
        )


if __name__ == "__main__":
    unittest.main()
