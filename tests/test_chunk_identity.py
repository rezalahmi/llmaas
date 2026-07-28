from app.services.chunk_identity import assign_chunk_refs, canonicalize_chunk_text


SETTINGS = {
    "api_key_id": 7,
    "file_id": "file_1",
    "chunking_strategy": "recursive_character",
    "chunking_version": "1",
    "chunking_parameters": {"chunk_size": 800, "chunk_overlap": 100},
}


def test_same_content_and_settings_produce_stable_identity():
    first = assign_chunk_refs(["سلام   دنیا"], **SETTINGS)
    second = assign_chunk_refs(["سلام\nدنیا"], **SETTINGS)
    assert first == second
    assert first[0][0].startswith("chk_")


def test_duplicate_chunks_get_stable_distinct_occurrence_identity():
    refs = assign_chunk_refs(["same", "same"], **SETTINGS)
    assert refs[0][0] != refs[1][0]
    assert refs == assign_chunk_refs(["same", "same"], **SETTINGS)


def test_identity_is_tenant_scoped():
    tenant_one = assign_chunk_refs(["same"], **SETTINGS)
    other_settings = {**SETTINGS, "api_key_id": 8}
    tenant_two = assign_chunk_refs(["same"], **other_settings)
    assert tenant_one[0][0] != tenant_two[0][0]


def test_chunking_configuration_changes_identity():
    original = assign_chunk_refs(["same"], **SETTINGS)
    changed_settings = {
        **SETTINGS,
        "chunking_parameters": {"chunk_size": 900, "chunk_overlap": 100},
    }
    changed = assign_chunk_refs(["same"], **changed_settings)
    assert original[0][0] != changed[0][0]


def test_vector_store_placement_does_not_participate_in_identity():
    first_store = assign_chunk_refs(["same"], **SETTINGS)
    second_store = assign_chunk_refs(["same"], **SETTINGS)
    assert first_store == second_store


def test_canonicalization_is_unicode_and_whitespace_stable():
    assert canonicalize_chunk_text("  café\n") == canonicalize_chunk_text(
        "cafe\u0301"
    )
