# src/citecraft/adapters/citeproc_adapter.py
"""Adapter for interfacing with the citeproc-py bibliography engine."""

import io
import logging
import warnings
from typing import Any

import citeproc.formatter
from citeproc import (
    Citation,
    CitationItem,
    CitationStylesBibliography,
    CitationStylesStyle,
)
from citeproc.source.json import CiteProcJSON

logger = logging.getLogger(__name__)


class CiteprocAdapter:
    """Encapsulates citeproc-py use, filtering logs and standardizing failures."""

    @staticmethod
    def create_json_source(
        csl_dict: dict[str, Any],
        *,
        doi: str,
    ) -> tuple[CiteProcJSON | None, str | None]:
        """Instantiate CiteProcJSON source and handle unsupported field warnings."""
        try:
            with warnings.catch_warnings(record=True) as captured_warnings:
                warnings.simplefilter("always", UserWarning)
                source = CiteProcJSON([csl_dict])
                for w in captured_warnings:
                    msg = str(w.message)
                    if "unsupported" in msg:
                        logger.debug(
                            (
                                "Citeproc-py stripped unsupported fields for DOI: %s. "
                                "Details: %s"
                            ),
                            doi,
                            msg,
                            extra={
                                "status": "WARN",
                                "event": "citeproc_unsupported_fields_filtered",
                                "doi": doi,
                                "citeproc_message": msg,
                            },
                        )
                    else:
                        logger.warning(
                            "Unexpected citeproc-py warning for DOI: %s. Details: %s",
                            doi,
                            msg,
                            extra={
                                "status": "WARN",
                                "event": "citeproc_unexpected_warning_captured",
                                "doi": doi,
                                "warning_category": w.category.__name__
                                if w.category
                                else "Unknown",
                            },
                        )
                return source, None

        except (TypeError, ValueError, KeyError, UnboundLocalError) as e:
            error_msg = str(e)
            hint = ""
            if isinstance(e, UnboundLocalError):
                hint = (
                    " (Check presence/validity of type/DOI fields or potential "
                    "citeproc-py package update issue)"
                )

            full_error_context = f"{error_msg}{hint}" if error_msg else hint.strip()

            logger.warning(
                "CiteProcJSON structural translation failed for DOI: %s. Reason: %s",
                doi,
                full_error_context,
                extra={
                    "status": "KO",
                    "event": "citeproc_source_generation_failed",
                    "doi": doi,
                },
            )
            return None, full_error_context

    @staticmethod
    def parse_csl_style(
        style_content: str,
        *,
        doi: str,
    ) -> tuple[CitationStylesStyle | None, str | None]:
        """Parse XML CSL style sheet definitions safely without external XSD checks."""
        try:
            style_bytes = style_content.encode("utf-8")
            style_file = io.BytesIO(style_bytes)
            bib_style = CitationStylesStyle(style_file, validate=False)

        except Exception as e:
            error_msg = str(e)
            logger.warning(
                "Failed to parse CSL style definitions for DOI: %s. Details: %s",
                doi,
                error_msg,
                extra={
                    "status": "KO",
                    "event": "citeproc_style_parsing_failed",
                    "doi": doi,
                },
            )
            return None, error_msg
        else:
            return bib_style, None

    @staticmethod
    def render_bibliography(
        bib_style: CitationStylesStyle,
        bib_source: CiteProcJSON,
        *,
        item_id: str,
        doi: str,
    ) -> tuple[str | None, str | None]:
        """Produce final text bibliography strings."""
        try:
            bibliography = CitationStylesBibliography(
                bib_style,
                bib_source,
                citeproc.formatter.plain,
            )
            citation = Citation([CitationItem(item_id)])
            bibliography.register(citation)

            # Execution triggers internal rendering pipeline
            render_outputs = bibliography.bibliography()
            if render_outputs and len(render_outputs) > 0:
                rendered_text = str(render_outputs[0])
                logger.debug(
                    (
                        "Successfully resolved bibliography reference generation for "
                        "DOI: %s"
                    ),
                    doi,
                    extra={
                        "status": "OK",
                        "event": "doi_local_resolution_success",
                        "doi": doi,
                    },
                )
                return rendered_text, None

        except AttributeError as e:
            if "'NoneType' object has no attribute 'render'" in str(e):
                error_msg = (
                    "The CSL style file hosted on GitHub appears to be corrupted "
                    "or structurally incompatible with citeproc-py."
                )
                logger.warning(
                    "CSL parsing failure for DOI: %s. Technical detail: %s",
                    doi,
                    error_msg,
                    extra={
                        "status": "KO",
                        "event": "citeproc_github_style_file_corrupted",
                        "doi": doi,
                        "exception_details": str(e),
                    },
                )
                return None, error_msg

            # Re-raise if it's an unrelated AttributeError
            raise

        except Exception as e:
            error_msg = str(e)
            logger.warning(
                (
                    "Bibliography rendering pipeline crashed for DOI: %s. "
                    "Technical error: %s. Please create a github issue if recurrent."
                ),
                doi,
                error_msg,
                extra={
                    "status": "KO",
                    "event": "citeproc_rendering_pipeline_crashed",
                    "doi": doi,
                },
            )
            return None, error_msg
        else:
            return None, "Empty layout produced by bibliography generator."
