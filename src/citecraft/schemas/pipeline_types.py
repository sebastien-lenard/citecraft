# src/citecraft/schemas/pipeline_types.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Type and schema definitions for the generation pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple


@dataclass(frozen=True)
class AnomalousJournal:
    """Data carrier representing journals with no ISSN or incomplete metadata."""

    input_title: str
    status: str
    issn: str
    issns_found: str


@dataclass(frozen=True)
class BibliographyResult:
    """Metric aggregations and structural outputs of bibliography exports."""

    total_rows: int
    output_filepath: Path
    export_format: str = "CSV"
    style: str | None = None

    # Metrics
    ok_count: int = 0
    missing_count: int = 0
    duplicate_count: int = 0

    # Row examples
    sample_ok: dict[str, Any] | None = None
    sample_missing: dict[str, Any] | None = None
    samples_duplicate: list[dict[str, Any]] = field(default_factory=list)


class ProgressStep(NamedTuple):
    """Immutable data record representing the progress of a pipeline step."""

    step_name: str  # Ex: "parsing", "journals", "works", "references"
    current: int  # Count of processed elements
    total: int  # Total count of elements
    message: str  # Optional UI message
    status: str = "started"
