"""Contract for KAYE verification PDF reference data.

The production PDF table extractor is intentionally not implemented in P1.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class VerificationPdfExtractionNotImplemented(NotImplementedError):
    """Raised while P1 only defines the PDF extraction contract."""


@dataclass(frozen=True, slots=True)
class VerificationPdfContract:
    time_column_name: str = "Time"
    irtd_column_position: int = 2


def extract_irtd_reference_rows(_path: Path) -> None:
    """Placeholder for the future verification PDF table extractor."""
    raise VerificationPdfExtractionNotImplemented(
        "Verification PDF extraction is deferred until a dependency is approved."
    )

