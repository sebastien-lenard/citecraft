# src/citecraft/repositories/style_repository.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Repository for managing Citation Style Language (CSL) style files."""

import logging
from http import HTTPStatus
from typing import Any

import httpx
from defusedxml import ElementTree

from citecraft.network import (
    HTTPClientRegistry,
    HTTPClientWrapper,
    get_http_client_registry,
)
from citecraft.parsers import (
    JournalParser,
)
from citecraft.utils import AppConfig, get_config

logger = logging.getLogger(__name__)


class StyleRepository:
    """Handles downloading, matching, and validating reference styles via CSL files."""

    def __init__(
        self,
        favored_journal_title: str | None = None,
        favored_style: str | None = None,
        config: AppConfig | None = None,
        registry: HTTPClientRegistry | None = None,
    ) -> None:
        """Instantiate StyleRepository.

        Examples of styles:
        apa (AGU, Wiley), copernicus-publications (EGU), elsevier-harvard (Elsevier),
        chicago-author-date (Taylor & Francis), springer-basic-author-date (Springer),
        etc.
        """
        self.config: AppConfig = config or get_config()
        registry = registry or get_http_client_registry()
        self.http_client_wrapper: HTTPClientWrapper = registry.get_client("default")
        self.headers: dict[str, str] = {"User-Agent": "ManuscriptRefLister/1.0"}
        self.favored_journal_title: str | None = favored_journal_title
        self.favored_style: str | None = (
            "apa"
            if not favored_journal_title and not favored_style
            else favored_style
            if not favored_journal_title
            else None
        )
        self.favored_style_is_valid: bool | None = None
        self.csl_content: str | None = None

    def fetch_style_metadata(self) -> None:
        """Fetch the CSL style content for the target style from remote repository."""
        if not self.favored_style and self.favored_journal_title:
            self.favored_style = self.get_style(self.favored_journal_title)
            logger.info(
                "Style '%s' of journal '%s' will be applied for bibliography.",
                self.favored_style,
                self.favored_journal_title,
            )
        if not self.favored_style:
            logger.warning(
                "No favored style determined. Aborting metadata fetch.",
                extra={"event": "no_favored_style_for_fetch_metadata"},
            )
            return

        url = self.config.style_repo_url.replace(
            "{object_name}",
            str(self.favored_style),
        )

        try:
            response, predicted_url = self.http_client_wrapper.get(
                url,
                headers=self.headers,
            )
            if response is None:
                logger.warning(
                    "No CSL response received from URL: %s",
                    predicted_url,
                    extra={
                        "event": "no_csl_url_response",
                        "predicted_url": predicted_url,
                    },
                )
                self.csl_content = None
                return
            response.raise_for_status()
            self.csl_content = response.text
            logger.debug(
                "Successfully fetched CSL metadata for style: %s",
                self.favored_style,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                logger.warning(
                    "CSL style file not found (%d) at URL: %s",
                    HTTPStatus.NOT_FOUND,
                    url,
                    extra={
                        "status": "KO",
                        "event": "style_file_not_found",
                        "style": self.favored_style,
                        "status_code": 404,
                    },
                )
                self.csl_content = None
                return
            raise

    def get_style(self, journal_title: str) -> str | None:
        """Locate style code for a journal title.

        Fetch the style name/code for a journal (e.g. "nature" for journal "Nature"),
        and if style is dependent (=child) fetch the parent style name/code (e.g.
        "american-geophysical-union" for journal
        "Journal of Geophysical Research: Solid Earth".
        """
        # the valid namespaces are stored in the dict self.config.csl_xml_namespaces
        # the string
        # "https://raw.githubusercontent.com/citation-style-language/styles/master/{object_name}.csl" # noqa: ERA001, E501
        # is stored in self.config.style_repo_url
        # the string "https://www.zotero.org/styles-files/styles.json" is stored in
        # self.config.all_styles_repo_url
        # the string "" is stored in self.config.child_style_repo_url

        # Should warning http 404, json decode error, but bubble up all these errors as
        # fatal crashes to stop the full program (controlled by a cli.py script)

        # Should info on start and success, debug on intermediary steps if relevant.
        if not journal_title:
            return None

        logger.info("Initiating CSL style lookup for journal: '%s'", journal_title)
        normalized_target = JournalParser.normalize_title(journal_title)

        # 1. Fetch remote Zotero styles index
        url = str(self.config.all_styles_repo_url)
        try:
            response, predicted_url = self.http_client_wrapper.get(
                url,
                headers=self.headers,
            )
            if response is not None:
                response.raise_for_status()
        except (httpx.HTTPError, ValueError):
            logger.critical(
                "Failed to retrieve or decode style repository index from %s",
                url,
            )
            raise

        if response is None:
            err_msg = f"Empty index response received from URL: {predicted_url}"
            raise ValueError(err_msg)

        try:
            styles_list = response.json()
        except ValueError:
            logger.critical("Failed to decode style repository JSON payload.")
            raise

        if not isinstance(styles_list, list):
            snippet = str(styles_list)[:200]
            logger.debug("Malformed JSON root structure snippet: %s", snippet)
            logger.error(
                "Style repository index root structure is invalid",
                extra={
                    "status": "KO",
                    "event": "index_malformed_schema",
                    "expected": "list",
                    "got": type(styles_list).__name__,
                },
            )
            err_msg = (
                f"Unexpected schema format: index root is not a list. Got: "
                f"{type(styles_list).__name__}"
            )
            raise TypeError(err_msg)

        matched_style_name, is_dependent = self._fuzzy_match_style(
            styles_list,
            normalized_target,
        )

        if not matched_style_name:
            logger.warning(
                "No CSL styles matched the query: '%s'",
                journal_title,
                extra={"event": "no_csl_match_query", "journal_title": journal_title},
            )
            return None

        if is_dependent:
            logger.info(
                "Style '%s' is dependent. Resolving independent parent...",
                matched_style_name,
            )
            return self._resolve_independent_parent(matched_style_name)

        return matched_style_name

    def _fuzzy_match_style(
        self,
        styles_list: list[Any],
        normalized_target: str,
    ) -> tuple[str | None, bool]:
        """Perform fuzzy search on style list and extract match metadata."""
        for style in styles_list:
            if not isinstance(style, dict):
                continue

            title: str = style.get("title", "")
            style_name: str = style.get("name", "")

            if not title or not style_name:
                continue

            # Normalize remote values to ensure reliable matching
            norm_title = JournalParser.normalize_title(title)
            norm_name = JournalParser.normalize_title(style_name)

            if normalized_target in norm_title or normalized_target in norm_name:
                is_dependent = bool(style.get("dependent", False))
                logger.debug(
                    "Match found: '%s' maps to style code '%s' (Dependent: %s)",
                    title,
                    style_name,
                    is_dependent,
                )
                return style_name, is_dependent

        return None, False

    def _resolve_independent_parent(self, child_style_name: str) -> str | None:
        """Parse a dependent CSL file and extract its parent layout slug identifier."""
        url = self.config.child_style_repo_url.replace(
            "{object_name}",
            child_style_name,
        )

        response = None
        try:
            response_obj, predicted_url = self.http_client_wrapper.get(
                url,
                headers=self.headers,
            )
            if response_obj is not None:
                response_obj.raise_for_status()
                response = response_obj

        except httpx.HTTPStatusError as e:
            logger.exception(
                "Dependent CSL metadata endpoint returned status %d for URL: %s",
                e.response.status_code,
                url,
                extra={
                    "status": "KO",
                    "event": "dependent_style_file_error",
                    "style": child_style_name,
                    "status_code": e.response.status_code,
                },
            )
            raise

        if response is None:
            err_msg = (
                f"No response payload returned from style endpoint: {predicted_url}"
            )
            raise ValueError(err_msg)

        try:
            # Secure XML parsing: defusedxml prevents XXE/entity expansion attacks
            root = ElementTree.fromstring(response.content)

        except ElementTree.ParseError:
            snippet = (
                response.text[:200]
                if response is not None and response.text
                else "Empty content"
            )
            logger.debug("Failed XML parsing content snippet: %s", snippet)
            logger.critical(
                "Failed to parse dependent CSL XML for: %s",
                child_style_name,
                extra={
                    "status": "KO",
                    "event": "dependent_style_xml_corrupted",
                    "style": child_style_name,
                },
            )
            raise

        if not root.tag.startswith("{"):
            err_msg = f"XML root element '{root.tag}' does not define a namespace."
            raise ValueError(err_msg)

        actual_namespace = root.tag.split("}")[0].strip("{")
        matched_prefix = next(
            (
                k
                for k, v in self.config.csl_xml_namespaces.items()
                if v == actual_namespace
            ),
            None,
        )

        if not matched_prefix:
            err_msg = (
                f"Security Violation: Unrecognized CSL namespace detected:"
                f" '{actual_namespace}'"
            )
            raise ValueError(err_msg)

        # Query independent parent link node
        query = f".//{matched_prefix}:link[@rel='independent-parent']"
        parent_link_node = root.find(query, self.config.csl_xml_namespaces)

        if parent_link_node is not None:
            parent_href = parent_link_node.get("href")
            if parent_href:
                # Extract clean token slug from URI
                # (e.g., "http://www.zotero.org/styles/apa" -> "apa")
                parent_style_code = parent_href.strip("/").split("/")[-1]
                logger.info(
                    "Successfully resolved parent style: '%s'",
                    parent_style_code,
                )
                return parent_style_code

        logger.warning(
            "No 'independent-parent' link found in the XML structure for '%s'.",
            child_style_name,
            extra={
                "status": "KO",
                "event": "independent_parent_not_found",
                "style": child_style_name,
            },
        )
        return None

    def validate_favored_style(self) -> None:
        """Verify that loaded favored reference style meets CSL XML boundaries."""
        if not self.csl_content:
            self.favored_style_is_valid = False
            logger.warning(
                "Cannot validate style %s: No CSL content loaded.",
                self.favored_style,
                extra={
                    "event": "no_csl_loaded_for_favored_style",
                    "favored_style": self.favored_style,
                },
            )
            return

        content = self.csl_content.strip()

        # Standardizing strict check to match requirements precisely
        start_marker = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<style xmlns="http://purl.org/net/xbiblio/csl"'
        )
        end_marker = "</style>"

        normalized_content = content.replace("\r\n", "\n")
        if normalized_content.startswith(start_marker) and normalized_content.endswith(
            end_marker,
        ):
            self.favored_style_is_valid = True
            logger.info(
                "Favored reference style validated successfully: %s",
                self.favored_style,
                extra={
                    "status": "OK",
                    "event": "style_validation_success",
                    "style": self.favored_style,
                },
            )
        else:
            self.favored_style_is_valid = False
            logger.warning(
                "Favored reference style content layout invalid: %s",
                self.favored_style,
                extra={
                    "status": "KO",
                    "event": "style_validation_failed",
                    "style": self.favored_style,
                },
            )
