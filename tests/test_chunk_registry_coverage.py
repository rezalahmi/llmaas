import json
from decimal import Decimal

from scripts.chunk_registry_coverage import build_coverage_report


def test_decimal_aggregates_are_json_serializable():
    report = build_coverage_report(
        {
            "total_attachments": 2,
            "complete_attachments": 1,
            "missing_registry_attachments": 1,
            "legacy_unresolved_attachments": 0,
            "incomplete_version_attachments": 0,
            "settings_unknown_attachments": 1,
            "total_chunks": Decimal("4"),
            "registered_chunks": Decimal("4"),
            "unresolved_chunks": Decimal("0"),
            "fully_versioned_chunks": Decimal("2"),
        }
    )

    assert report["total_chunks"] == 4
    assert report["attachment_coverage_percent"] == 50.0
    assert report["fully_versioned_coverage_percent"] == 50.0
    json.dumps(report)


def test_missing_registry_is_not_reported_as_fully_versioned():
    report = build_coverage_report(
        {
            "total_attachments": 1,
            "complete_attachments": 0,
            "missing_registry_attachments": 1,
            "legacy_unresolved_attachments": 0,
            "incomplete_version_attachments": 0,
            "settings_unknown_attachments": 1,
            "total_chunks": Decimal("0"),
            "registered_chunks": Decimal("0"),
            "unresolved_chunks": Decimal("0"),
            "fully_versioned_chunks": Decimal("0"),
        }
    )

    assert report["attachment_coverage_percent"] == 0.0
    assert report["fully_versioned_coverage_percent"] == 0.0
