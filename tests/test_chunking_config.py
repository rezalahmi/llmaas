import pytest
from pydantic import ValidationError

from app.schemas.vector_store_batch_files import ChunkingConfig
from app.schemas.vector_store_files import VectorStoreFileCreate


@pytest.mark.parametrize(
    "model,payload",
    [
        (
            VectorStoreFileCreate,
            {"file_id": "file_1", "chunk_size": 100, "chunk_overlap": 100},
        ),
        (
            ChunkingConfig,
            {"chunk_size": 100, "chunk_overlap": 101},
        ),
    ],
)
def test_chunk_overlap_must_be_smaller_than_chunk_size(model, payload):
    with pytest.raises(ValidationError, match="chunk_overlap"):
        model.model_validate(payload)
