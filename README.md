<!-- README.md -->
# CiteCraft — Automated Manuscript Bibliography Generator

 <img src="citecraft_logo_64.png" alt="CiteCraft automated bibliography generator logo" align="left" width="64" height="72" style="margin-right: 15px; margin-bottom: 10px;"> CiteCraft is a lightweight Python bibliography generator and CLI tool designed for scientists and other users to automatically extract in-text citations from a `.docx` manuscript and format a complete bibliography to a target journal style. By matching cited works against a user-provided list of journals, the tool automates lookups of DOIs using remote academic APIs (OpenAlex or Crossref) and compiles the reference list through a local citation engine.

Unlike complex reference managers, this project focuses on a streamlined, manuscript-centric workflow that converts raw in-text citations directly into plain-text bibliographic outputs without requiring manual data entry.

---


## 🚀 The Concept

The application executes a highly targeted data pipeline based on three primary inputs found directly within or alongside your working text:

1. **The Manuscript:** A standard `.docx` file containing your narrative text and APA-style in-text citations.

2. **The Publication Journal List:** A designated section at the end of your `.docx` manuscript under the heading `Journals`. This block must list one exact cited journal title per line (e.g., *Nature Geoscience*):
```

Journals
Nature Geoscience
Geomorphology

```
The tool extracts these titles, resolves them to their official ISSNs, and uses these ISSNs as a strict search filter for published work lookup. **Note:** The tool cannot discover or resolve a work if its parent journal is omitted from this section.

3. **The Result:** The application processes the in-text citations and the cited journal list, executes an automated DOI lookup via API calls filtered by the resolved ISSNs and first-author surnames, and builds a clean bibliography formatted precisely to the CSL style of your target submission journal.

---

## 🛠 Installation & Setup

This project uses `uv` for modern Python package and project management.

### 1. Install uv

* **Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh | iex"

```


* **macOS & Linux:**
```bash
curl -LsSf https://astral.sh | sh

```



### 2. Setup the Project

Clone the repository and sync the virtual environment:

```bash
git clone https://github.com/sebastien-lenard/citecraft
cd citecraft
uv sync

```

---

## ⚙️ Configuration

The application relies on environment variables for file paths, local caches, and API credentials.

1. Copy the environment template file:

* **Windows:** `copy .env.example .env`
* **macOS & Linux:** `cp .env.example .env`


2. Edit the `.env` file with your local environment settings:

* `WORK_DIR_PATH`: Local directory for processing and the SQLite database cache used for cited journal and work metadata.
* `OUTPUT_DIR_PATH`: Default directory for your final bibliography output CSV files.
* `LOG_DIR_PATH`: Directory for system log files.
* `JOURNAL_UPDATE_DAYS`: Integer setting the metadata cache expiration window (Default: `30` days).
* `USER_EMAIL`: Your email address, required to access the polite API usage pools.
* `OPENALEX_API_KEY`: Your personal OpenAlex API key (request one at [openalex.org/settings/api-key](https://openalex.org/settings/api-key)).



---

## 📖 Usage

Run the tool using the `uv run` prefix.

### Processing a Manuscript

The tool accepts text data via two input modes: passing a local path to a `.docx` file using the `-f` flag, or piping raw text directly into standard input (`stdin`). Whichever mode is used, the input text must always conclude with the trailing `Journals` section block.

* **Auto-detect style based on a submission journal:**

```bash
uv run citecraft -f "C:\Documents\manuscript.docx" -o "C:\Documents\bibliography.csv" -j "Geomorphology"

```


* **Force a specific CSL style identifier:**
```bash
uv run citecraft -f "C:\Documents\manuscript.docx" -o "C:\Documents\bibliography.csv" -s "copernicus-publications"

```


* **Piping Raw Text Directly:**
```bash
echo "Text (Lenard et al., 2020)\r\nJournals\r\nNature Geoscience" | uv run citecraft

```



### Advanced Controls

* **Bypassing Remote API Updates (Speed Runs):**

```bash
uv run citecraft -f "C:\Documents\manuscript.docx" --skip-journal-update --skip-work-update

```


* **Cache Management:**

```bash
uv run citecraft --clear-cache

```


* **Log Verbosity:**

```bash
uv run citecraft -f "C:\Documents\manuscript.docx" -v   # For INFO logs
uv run citecraft -f "C:\Documents\manuscript.docx" -vv  # For DEBUG logs

```



### CLI Arguments Summary

* `-f` : Path to the `.docx` manuscript file.
* `-o` : Path to the output CSV file. *(Defaults to `OUTPUT_DIR_PATH / "manuscript_references.csv"` if omitted)*
* `-j` : Target journal title for submission (e.g., "Geomorphology"). Title matching is case-insensitive and ignores punctuation. This option triggers an automated lookup against the official CSL repository to fetch the matching journal style XML file, overriding any value provided via `-s`.
* `-s` : Style identifier recognized by [citation.doi.org](https://citation.doi.org/). If omitted, and no target journal title is passed via `-j`, this defaults to `apa`.
* `-a` : Favored REST API backend for work DOI matching. Choice of `Crossref` or `OpenAlex`. *(Default: `OpenAlex`)*
* `--skip-journal-update` : Skips remote API lookups for cited journal metadata and ISSNs. New cited journal titles from the manuscript are registered locally but without fetching remote records. Useful to bypass API latency when no new journals have been added to the trailing `Journals` section.
* `--skip-work-update` : Skips remote API lookups for missing work DOIs. Existing local records are processed normally, but no network calls are made to fetch missing work DOIs and metadata.
* `--clear-cache` : Deletes all locally cached cited journal and work records. Use only if the tool presents unexpected behavior.

---

## 🔄 Technical Architecture & Data Pipeline

The application relies on a unified internal rendering pipeline to ensure consistent bibliographic output, regardless of the selected upstream remote metadata engine.

```
[Manuscript Input (.docx or stdin)] 
               │
               ▼
         [Regex Parser] ──► (Extracted In-text Citations & Manuscript Cited Journal Titles)
               │
               ▼
  [Data Pipeline Routing]
   ├── Target Journal for Submission (-j)  ──► [CSL Styles GitHub Repo Lookup] ──► [Target Style Definition File]
   ├── Manuscript Cited Journals List    ──► [Crossref /journals API]        ──► [Validated ISSN Filters]
   └── In-Text Citation Matches        ──► [Selected API /works Endpoint]  ──► [Unified Translator Class]
                                                                                      │
                                                                                      ▼
                                                                                [citeproc-py]
                                                                                      │
                                                                                      ▼
                                                                          [Final Bibliography CSV Output formatted to Target Journal Style]

```

### 1. In-Text Citation Extraction

The extraction engine scans the manuscript content or standard input using multiple sequential regular expressions. It extracts APA-formatted citations supporting suffixes (e.g., *a* or *b* works) under two valid syntax patterns:

* **Parenthetical Citations:** `(Lenard et al., 2020; Gus, 2014; Guns and Vanacker, 2014)`
* **Narrative Citations:** `As Bernard et al. (2021) wrote...`

> ⚠️ **Parsing Scope:** The tool cannot parse alternative formatting frameworks, such as bracketed numbers (IEEE), superscript numbers (Chicago history), or author/page combinations (MLA).

> ⚠️ **Publication Years:** Citations of works published before 1600 or after 2099 raise a fatal error (`MIN_PUBLICATION_YEAR` and `MAX_PUBLICATION_YEAR` configuration in `.env` file).

### 2. Isolated Remote Processes

The application maintains four separated metadata workflows:

* **Process A: CSL Target Journal Style Definition Retrieval (Submission Context)**
When you specify a submission journal via `-j`, the tool maps the journal title to its corresponding style identifier recognized by [citation.doi.org](https://citation.doi.org/). It automates this mapping by querying the official [CSL Styles GitHub Repository](https://github.com/citation-style-language/styles). For some major journals, the identifier is simply the lowercase title with spaces replaced by hyphens (e.g., `earth-surface-processes-and-landforms`). For others, it maps the title to its inherited parent format (e.g., mapping AGU journals to `american-geophysical-union`, or Copernicus journals to `copernicus-publications`).
* **Process B: Manuscript Cited Journal Metadata Lookup**
The tool extracts the cited journal titles listed in the manuscript’s trailing `Journals` section and queries the Crossref `/journals` endpoint. This step resolves those titles to their official ISSNs and verifies their publication status.
* **Process C: Work DOI Lookup**
Using the first author(s)'s surname and the publication year extracted from the in-text citation, the tool queries the remote API `/works` endpoint selected via the `-a` argument to resolve the correct DOI.
* **Process D: Work Metadata Fetching**
For Crossref, the tool fetches work metadata at the same time as Process C. For OpenAlex, the tool is currently unable to process their native metadata using the local `citeproc-py` bibliographic rendering engine; therefore, the tool fetches Crossref metadata by calling the DOI Negotiation Service at [doi.org](https://doi.org) after Process C concludes.

### 3. Upstream API Pipeline Variations

The choice of backend API shifts how network requests and filters are structured:

| Operational Feature | Crossref (`-a Crossref`) | OpenAlex (`-a OpenAlex`, Default) |
| --- | --- | --- |
| **Primary Information Source** | Publishers directly. | Crossref aggregated with diverse external data sources. |
| **ISSN Filter Architecture** | Supports only one ISSN filter per network call. Requires $N$ separate API calls for $N$ ISSNs, increasing execution latency. | Supports filtering by an array of multiple ISSNs (e.g., ISSNa OR ISSNb) in a single request. Reduces total API calls, yielding a faster execution loop. |
| **Native API Author Filtering** | Lacks isolated author-filtering fields. Surnames cannot be locked down and must be passed as broad text keywords. | Supports direct, native filtering fields by author name. |
| **Metadata Output Payload** | Loose, publisher-dependent CSL-JSON format. | Structured OpenAlex-specific JSON format. Comprehensive bibliographic info is widely available for journal articles. |
| **API Name Field Layout** | Distinctly discriminates between explicit `given` and `family` name fields. | Combines names into a single `full name` string field; it does not distinguish given names from family names natively. |
| **Post-API Call Filtering Engine** | Executes a strict, precise **full match** evaluation against the author's family name on the returned items. | Executes a **partial match** evaluation on the returned strings. Because OpenAlex indexes full-name strings, a search for an author with the family name "Jerome" will capture instances where "Jerome" appears as a given name. Irrelevant matches must be cleaned manually in the final CSV. |

### 4. The Unified Translation Layer

Once raw metadata items are returned, they pass through a dedicated **Translator Class**. This layer normalizes the structurally divergent JSON payloads into uniform standard CSL-JSON, injects missing required attributes (such as generating the missing `id` field from the DOI for Crossref records), and routes the uniform CSL-JSON directly into the local `citeproc-py` rendering engine to compile the plain-text bibliography.

---

## 💾 Caching & Operational Limitations

### Cited Journal Metadata Cache & Loop Exception

Cited journal records are cached based on the expiration timeline defined by `JOURNAL_UPDATE_DAYS` in your `.env` file.

* **Permanence Rule:** Valid resolved cited journals will not be re-queried remotely until the cache window expires.
* **The Incomplete State Loop:** If a cited journal title in the registry contains incomplete metadata—such as a missing ISSN, or a recorded ISSN that has zero associated publication history—the tool flags it as an incomplete state. This state triggers a forced remote refresh on **every subsequent run** regardless of cache age. This update mechanism operates strictly at the coarse **journal title level**, not the individual ISSN level. If a cited journal possesses multiple ISSNs and only one lacks metadata, the tool forces a full remote API reload for all records sharing that input title. To stop the tool from repeatedly querying the API for these unresolvable titles during a session, use the `--skip-journal-update` flag.

### Work Metadata Cache

Once an in-text citation has been evaluated against the resolved ISSN filters, the outcome (success or failure) is written permanently to the local work cache repository. Successfully evaluated in-text citations are never re-checked on subsequent runs, unless the system cache is cleared globally via `--clear-cache`. Failed evaluated citations are re-checked on subsequent runs in any case. To stop the tool from repeatedly querying the API for these unresolvable citations during a session, use the `--skip-work-update` flag.


### Rigid Cited Journal Title Matching in Cited Journal Queries to APIs

While the tool implements string normalization to strip case and handle basic punctuation discrepancies (e.g., matching *"Proceedings of the Royal Society A: Mathematical, Physical and Engineering Sciences"* against its unpunctuated registry entry), cited journal titles with slight morphological variations (e.g., *Natural Hazards and Earth System Sciences* vs. the registered *Natural Hazards and Earth System Science*) completely fail to resolve to an ISSN and are excluded.

### Strict ISSN Filter Enforcement in Cited Work Queries to APIs

To exclude thousands of irrelevant work DOI results returned by an API based only on first author names, the tool applies absolute ISSN filters to all work queries. This introduces specific constraints:

* **Missing Registry ISSNs:** Some preprint repositories (such as *EGUsphere*) do not have an ISSN, causing citation lookups to fail.

* **Historical Cited Journal ISSN Shifts and Consolidation:** Certain cited journals share a complex indexing history where multiple distinct sub-publications were grouped under a single parent ISSN before receiving independent identifiers.

* *Example (AGU):* *Journal of Geophysical Research: Solid Earth* was historically consolidated under the ISSN of *Journal of Geophysical Research: Atmospheres* for metadata records spanning until 2012–2013. Consequently, for any citation dated prior to 2014, Crossref may only recognize the historical parent ISSN. To successfully resolve these entries, the user must include both titles (*Journal of Geophysical Research: Atmospheres* and *Journal of Geophysical Research: Solid Earth*) in the manuscript's journal list.
* *Other instances:* Similar historical tracking and splitting discrepancies affect journals such as *Comptes Rendus Geoscience* and *Journal of Earth System Science*, requiring identical multi-title listing for older papers.

* **Types of Works Supported:** Because the tool restricts all work metadata queries using strict ISSN filters, it primarily supports journal articles and works directly indexed under a validated ISSN. It cannot parse or resolve independent book chapters, monographs, or standalone tracking records unless they belong to an indexed book series (e.g., *Geological Society of London Special Publications*).

### Upstream HTML Pollution & Spacing of Work Titles and Metadata

Crossref and OpenAlex databases occasionally contain work titles embedded with raw line breaks (`\n`) and HTML formatting tags (e.g., `<sup>`, `<i>`), as originally submitted by publishers to Crossref. The tool cleans these strings using global regular expressions to strip tags and collapse consecutive whitespaces down to a single standard space character.

* **Side-Effect Impact:** Because scientific work titles utilize unpredictable structural conventions across disciplines (chemistry isotopes, gene sequences, mathematical formulas), the global space-collapsing rule can occasionally insert an unintended space adjacent to removed tags. For example, a raw entry structured as `<sup>\n 10\n </sup>Be` will render in the plain-text CSV output as `10 Be` instead of `10Be`. This is a downstream data tracking limitation; it cannot be resolved with structural parsers like BeautifulSoup because the formatting irregularities exist natively within the provider databases. Output text is written strictly in plain text; no subscript, superscript, or LaTeX formatting is preserved.

---

## 📊 Output Interpretation & Diagnostics

### Logs

Execution logs are handled simultaneously across two targets. Coarse-grained logs are output directly to the console depending on the runtime verbosity flags (defaulting to the warning level). Concurrently, a structured JSON log tracking all background execution records (debug level) is systematically saved to your local storage path at `LOG_DIR_PATH / "app.json.log"`.

### Coarse-Grained Progress Bar ETA

In default execution mode (without `-v` or `-vv`), the application displays a progress bar tracking high-level execution phases (e.g., transitions between parsing, cited journal ISSN and metadata resolution, and cited work DOI and metadata fetching). Because the progress bar tracks these major processing milestones rather than individual, fine-grained network requests, the Estimated Time of Arrival (ETA) updates in blocks. It should be treated as a rough phase indicator rather than a precise second-by-second countdown.

### Unresolved or Partly Resolved Cited Journals Table & Status Codes

At the end of execution, the console displays a table summarizing the status of cited journal titles that could not be fully resolved. This summary appears immediately above the CSV preview block. Cited journals in this table may have the following status:

1. **`Journal title not found`:** Exact cited journal title matching failed in the API. Either the spelling of the cited journal title is incorrect or the journal title is not registered in the API database.
2. **`Journal title found without ISSN`:** The API does not have an ISSN recorded for the cited journal title.
3. **`Journal title found with at least one ISSN without works`:** The API did not find published works for at least one of the ISSNs resolved for the cited journal title.

Cases (1) and (2) lead to the failure of the DOI lookup of any cited work published in these cited journal titles. DOI lookups for cited journals in case (3) do not always lead to DOI lookup failure if the cited journal has at least one ISSN resolved.

### Cited Work Bibliography CSV Preview Table & Status Codes

The console prints a final terminal layout featuring a preview of the bibliography results, showcasing one or two sample instances of each encountered lookup status. The complete set of bibliographic results with resolved and unresolved citations is written directly to your saved local output CSV file.

Each in-text citation is tagged with one of three definitive status codes in the final output document:

* **`OK`**
* *Meaning:* A unique, unambiguous DOI was resolved.
* *User Action:* The work reference is properly formatted and ready to be copied directly into your manuscript.


* **`Warning: Multiple matches`** (or `Ambiguous matches`)
* *Meaning:* The citation can be associated to multiple potential DOIs. **Note:** The possible causes are diverse: (1) inclusion of cited journals covering multiple fields in the cited journal list (e.g. `Nature`); (2) common author names (e.g. Zhang, Smith, Singh); (3) confusion between family and given names; (4) the author was first author in several publications for the year of the in-text citation.
* *User Action:* Review the generated CSV rows manually, choose the valid reference, and remove irrelevant rows before copying.


* **`Warning: Missing metadata`**
* *Meaning:* The remote API could not verify or match a specific DOI for the in-text citation. **Note:** The possible causes are diverse: (1) the first author(s) name(s) is misspelled or does not include a particle (e.g. Duchesne instead of Du Chesne); (2) the citation cites a given name instead of a family name (e.g. for `Nature` journal: Peng et al., 2001 instead of Zhang et al., 2001); (3) the author in the citation is not first author; (4) there is a mismatch between the citation and the actual number of coauthors of the work (e.g. Hergarten et al., 2024, 3 or more authors expected vs actual work, Hergarten, 2024, one author only); (5) the work was not published in any journal of the cited journal list at the end of the manuscript provided to the application or the journal ISSN was not resolved (see above section); (6) the year in the citation is not the correct year; (7) the work was not submitted to the API database (e.g. conference abstract, preprint); (8) the work was not published in a journal or similar types of publication, as it happens for monographs, reports, book chapters (e.g. `Gilbert, G. K. (1877). Land sculpture. In Report on the geology of the Henry Mountains (pp. 99–150). Government Printing Office.`).
* *User Action:* First, check if the problem is not one of the ones described in the note. If no obvious resolution, skip automation for this record. Manually search and extract the reference using [www.crossref.org](https://www.crossref.org), [OpenAlex.org](https://openalex.org), or [scholar.google.com](https://scholar.google.com).



---

## 🧪 Tests

Execute the test suites via `uv` using the configured `pytest` markers:

```bash
# Run the entire test suite
uv run pytest

# Run unit tests only (bypasses network overhead)
uv run pytest -m "not integration and not e2e"

# Run integration tests only (verifies Crossref and OpenAlex connections)
uv run pytest -m integration

# Run end-to-end manuscript processing tests
uv run pytest -m e2e

```

---

## 🐛 Known Bugs

None reported. Users are more than welcome to open an issue if they encounter unexpected behavior.

---

## 📅 Roadmap

* [ ] **Context-Aware Author Matching:** Implement secondary filters to improve DOI resolution accuracy for common surnames (e.g., Smith, Singh, Müller).