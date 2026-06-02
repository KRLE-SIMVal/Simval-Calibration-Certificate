from datetime import timezone

import pytest

from app.backend.imports.verification_pdf_contract import (
    VerificationPdfContract,
    VerificationPdfExtractionNotImplemented,
    VerificationPdfParseError,
    extract_irtd_reference_rows,
    parse_irtd_reference_table,
)


def test_verification_table_parser_reads_irtd_column_next_to_time():
    result = parse_irtd_reference_table(
        rows=(
            ("Time", "IRTD (deg C)", "MJT1-A"),
            ("2026-04-08T15:45:00+00:00", "-80.031", "-80.036"),
            ("2026-04-08T15:46:00+00:00", "-80.030", "-80.034"),
        ),
        uploaded_file_id="verification-pdf-001",
    )

    assert result.contract == VerificationPdfContract()
    assert result.irtd_column_name == "IRTD (deg C)"
    assert len(result.readings) == 2
    first = result.readings[0]
    assert first.timestamp.tzinfo is not None
    assert first.timestamp.utcoffset() == timezone.utc.utcoffset(first.timestamp)
    assert first.channel_id == "IRTD"
    assert first.value == pytest.approx(-80.031)
    assert first.unit == "deg C"
    assert first.source.uploaded_file_id == "verification-pdf-001"
    assert first.source.source_label == "Verification IRTD"
    assert first.source.row_number == 2
    assert first.source.column_label == "IRTD (deg C)"
    assert result.warnings == ()


def test_verification_table_parser_uses_column_immediately_after_time():
    result = parse_irtd_reference_table(
        rows=(
            ("Index", "Time", "Reference Probe", "MJT1-A"),
            ("1", "2026-04-08T15:45:00+00:00", "-80.031", "-80.036"),
        ),
        uploaded_file_id="verification-pdf-001",
    )

    assert result.irtd_column_name == "Reference Probe"
    assert result.readings[0].value == pytest.approx(-80.031)


def test_verification_table_parser_rejects_missing_time_column():
    with pytest.raises(VerificationPdfParseError):
        parse_irtd_reference_table(
            rows=(
                ("Elapsed", "IRTD (deg C)", "MJT1-A"),
                ("00:00", "-80.031", "-80.036"),
            ),
            uploaded_file_id="verification-pdf-001",
        )


def test_verification_table_parser_warns_and_skips_invalid_rows():
    result = parse_irtd_reference_table(
        rows=(
            ("Time", "IRTD (deg C)", "MJT1-A"),
            ("not-a-time", "-80.031", "-80.036"),
            ("2026-04-08T15:46:00+00:00", "not-a-number", "-80.034"),
            ("2026-04-08T15:47:00+00:00", "", "-80.033"),
        ),
        uploaded_file_id="verification-pdf-001",
    )

    assert result.readings == ()
    assert result.warnings == (
        "Skipped row 2 in Verification IRTD because timestamp is invalid.",
        "Skipped nonnumeric IRTD value at Verification IRTD!IRTD (deg C) row 3.",
        "Skipped missing IRTD value at Verification IRTD!IRTD (deg C) row 4.",
    )


def test_verification_pdf_file_extraction_remains_explicitly_deferred():
    with pytest.raises(VerificationPdfExtractionNotImplemented):
        extract_irtd_reference_rows("not-used.pdf")
