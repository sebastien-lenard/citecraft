## Manuscript Reference Lister
A lightweight Python tool designed for scientists to generate formatted reference lists directly from a .docx manuscript. By matching citations against a provided list of target journals, it automates the DOI lookup and citation formatting process using the Crossref API and DOI.org.
## 🚀 The Concept
Unlike complex reference managers, this tool focuses on simplicity:

   1. The Manuscript: A .docx file containing your text and citations (e.g., Lenard et al., 2020).
   2. The Journal List: A section at the end of your document under the heading Journals, with one exact journal title per line.
   3. The Result: The tool identifies the citations, matches them to the journals to resolve ISSNs, and retrieves metadata via the Crossref "Polite Pool."

Note on Journal Titles: This tool uses the journal list to resolve ISSNs. Because the Crossref API can return hundreds of results for generic titles like "Science," only exact matches are currently supported to ensure the metadata retrieved is correct.

## 🛠 Installation
This project uses uv for package and project management.
## 1. Install uv
Windows
```
powershell -c "irm https://astral.sh | iex"
```
macOS & Linux
```
curl -LsSf https://astral.sh | sh
```
## 2. Setup the Project

Clone the repository:
```
git clone https://github.com/sebastien-lenard/manuscript-reference-lister
```
Sync the environment
```
cd manuscript-reference-lister
uv sync
```
## ⚙️ Configuration
The application uses environment variables for path management and API settings.
1. Copy the template file:

* Windows: ```copy .env.example .env```
* macOS & Linux: ```cp .env.example .env```

2. Edit the .env file:

* Paths: Update WORK_DIR_PATH and OUTPUT_DIR_PATH.
* Crossref API: Set CROSSREF_API_EMAIL to your valid email to use the "Polite Pool" for better reliability.

## 📖 Usage
Run the tool using the uv run prefix.

# Process a manuscript file and specify the output path
For a specific style:
```uv run references-lister -f "C:\Documents\manuscript.docx" -o "C:\Documents\bibliography.csv" -s "copernicus-publications"```

For a submission journal (autodetection of style):
```uv run references-lister -f "C:\Documents\manuscript.docx" -o "C:\Documents\bibliography.csv" -j "Geomorphology"```

# Control log verbosity (-v for INFO, -vv for DEBUG):
```uv run references-lister -f "C:\Documents\manuscript.docx" -v```

# Clear cache (local repository)
Clear cache and process a manuscript:
```uv run references-lister -f "C:\Documents\manuscript.docx" --clear-cache```

Clear cache (maintenance only)
```uv run references-lister --clear-cache```

The tool will display a confirmation message.


# Pipe source directly
```echo "Text (Lenard et al., 2020)\r\nJournals\r\nNature Geoscience" | uv run references-lister```

**CLI arguments:**
* `-f` : Path to the `.docx` manuscript to parse.
* `-o` : Path to the output CSV file. Contains the parsed citations, Crossref/DOI lookup status, and formatted references. *(Default: `OUTPUT_DIR_PATH / "manuscript_references.csv"` if omitted)*.
* `-s` : Style identifier recognized by [citation.doi.org](https://citation.doi.org/). *(Default: `apa` if omitted)*.
* `-j` : Targeted journal title for submission, e.g. "Geomorphology". Title should be exact. The journal style overrides the style above.
* `--skip-journal-update` : Skips the remote Crossref API lookup for journal metadata and ISSNs. New journal titles are still registered locally, but without fetching remote metadata. Useful to bypass API latency when no new journals have been added to the manuscript.
* `--skip-work-update` : Skips the remote Crossref API lookup for work DOIs. Existing local records are processed normally, but no network calls are made to fetch missing DOIs. Useful to speed up re-runs when no new citations have been added to the manuscript.

**Input**

A manuscript with in-text citations of works following the APA style: format author last name 1 et al., year; author last name 1 and/et author last name 2, year; author last name 1, year. A suffix (e.g. a or b) works. The tool cannot parse other in-text citation styles, such as bracketed numbers (IEEE), superscript numbers (Chicago history), author last name page number (MLA).

The manuscript should have a section Journals at its end, which lists the journal titles on which the work lookup will be carried out. The tool currently cannot find a work published in a journal not in this section. For instance:
```

Journals
Nature Geoscience
Geomorphology

```

Alternatively, a raw text with similar characteristics can be provided to the tool.

**Output**

At the end of the execution, the console can display warnings for journals without ISSN. Several cases may occur: Journal title not found in the remote API, title found without ISSN, title found with an ISSN but without published work associated to this ISSN. The lookup for DOIs is carried out only on journal titles that have at least one ISSN with published work.

The console also displays a preview of the CSV output, with instances of the three possible lookup status:
* `OK` : A unique DOI has been found for the citation and reference can be copy-pasted to the manuscript as such.
* `Warning: Multiple matches` or `Ambiguous matches` : Several DOIs have been found for the citation. The user is invited to manually select the correct one and delete the other ones before copy-paste to the manuscript.
* `Warning: Missing metadata` : No DOI has been found for the citation. The user is invited to manually look for the reference using [www.crossref.org](www.crossref.org) or [scholar.google.com](scholar.google.com).


## Output & Interpretation

### Console Warnings

At the end of the execution, the console displays warnings for journals that could not be fully resolved. This happens in three specific cases:

1. **Journal title not found** in the Crossref registry.
2. **Journal found without an ISSN**.
3. **Journal found with an ISSN, but with zero published works** associated with it.

> 🔍 **Core Logic:** The tool only attempts DOI lookups for journals that have both a valid ISSN and at least one registered publication.

### CSV Preview & Status Codes

The console also prints a preview of the generated CSV file. Each citation receives one of three status codes in the output:

* `OK`
* **Meaning:** A unique DOI was successfully found.
* **Action:** The formatted reference is ready to be copied directly into your manuscript.


* `Warning: Multiple matches` (or `Ambiguous matches`)
* **Meaning:** Crossref returned multiple potential DOIs for this citation (due to common surnames or shared publication years).
* **Action:** Review the rows manually, keep the correct reference, and delete the incorrect duplicates.


* `Warning: Missing metadata`
* **Meaning:** No matching DOI could be found.
* **Action:** Manually search for the reference using [www.crossref.org](https://www.crossref.org) or [scholar.google.com](https://scholar.google.com).


## Tests
# Run tests
```uv run pytest```

# Run specific test suites
Unit tests only:
```uv run pytest -m "not integration and not e2e"```
Integration (included Crossref API and DOI negotiation service) tests only:
```uv run pytest -m integration```
End to end tests only:
```uv run pytest -m e2e```

## 💡 Additional tips about options

### 💡 Finding the Correct Style Name (`-s`)

The tool formats references using the CSL style identifiers recognized by [citation.doi.org](https://citation.doi.org/).

For some major journals, the identifier is simply the lowercase title with spaces replaced by hyphens (e.g., `earth-surface-processes-and-landforms`). However, many journals do not have a unique style and instead inherit a parent format (e.g., Copernicus journals use `copernicus-publications`, AGU journals such as Geophysical Research Letters use `american-geophysical-union`).

If you give the journal title as an option, the tool automates this lookup using the official CSL repository [CSL Styles GitHub Repository](https://github.com/citation-style-language/styles).

## 🐛 Known Bugs

None reported. Feel free to open an issue if you encounter unexpected behavior.

## ⚠️ Limitations with moderate impact

## 📝 Limitations with minor impact

### 📝 Coarse-Grained Cache Updates for Incomplete Journals

The tool maintains a local JSON database (`records`) to cache journal metadata across executions, minimizing redundant API requests to Crossref. This cache expires based on the `JOURNAL_UPDATE_DAYS` environment variable. 

However, if a journal title is flagged with incomplete metadata during a run, the tool triggers a remote Crossref refresh even if the cache has not expired. Incomplete metadata occurs under two conditions:
* **Missing ISSN:** The registry has no ISSN mapped to the title (`Found without ISSN`).
* **Missing Works:** An ISSN exists but has no registered publication years or historical records (`Found without work`).

**The Limitation:** 
The update mechanism operates at the **journal title level**, not the individual ISSN level. If a journal possesses multiple ISSNs (such as an old print ISSN and a modern e-ISSN) and *only one* of these records lacks metadata, the tool will force a full Crossref API reload for **all** records sharing that input title. While this ensures data completeness, it leads to redundant API queries for the valid ISSNs of that same journal.

### 📝 Coarse-Grained Progress Bar ETA
In default mode (without `-v` or `-vv`), the application displays a progress bar tracking high-level execution phases (e.g., transitions between parsing, journal metadata resolution, and work metadata fetching).

**Note on ETA accuracy:** Because the progress bar tracks these major processing milestones rather than individual, fine-grained network requests, the Estimated Time of Arrival (ETA) updates in blocks. It should be treated as a rough phase indicator rather than a precise second-by-second countdown.


## 🔌 External Dependencies & Limitations

### 1. System Interactions

The tool relies on two external web services to automate reference generation:

* **Crossref REST API:** Used in two distinct phases. First, it queries the `/journals` endpoint to resolve exact journal titles into standard ISSNs. Second, it queries the `/works` endpoint using author and year metadata combined with these ISSNs to isolate the specific publication.
* **DOI Citation Negotiation Service (`doi.org`):** Once a unique DOI is successfully retrieved from Crossref, this service is queried with specific HTTP headers (`Accept: application/vnd.citationstyles.csl+json` or other style-specific strings) to fetch all metadata associated with the DOI. The tool locally constructs the fully formatted bibliographic reference using these metadata.

### 2. API Limitations & Operational Impact

Due to structural behaviors in the Crossref index, automated matching can fail or produce false positives. The primary challenges include:

* **Weak Author Weighting in Queries:** The `/works` endpoint does not support strict, isolated filtering by author name (e.g., no `filter=author:Lenard`). Author names are treated as general keywords. Because the tool only possesses an author-year pair from the in-text citation—and lacks the article title—a broad keyword search for common surnames returns hundreds of irrelevant records.

* **Journal Metadata Gaps:** To mitigate the volume of irrelevant results, the tool restricts queries using ISSN filters. However, Crossref’s journal database depends heavily on publisher compliance, which remains inconsistent:
   * *Missing ISSNs:* Some prominent journals or preprint repositories (such as *EGUsphere*) do not have their ISSN properly mapped or indexed within the Crossref registry.
   * *Rigid Title Matching:* While the tool implements string normalization to handle punctuation discrepancies (e.g., matching *"Proceedings of the Royal Society A: Mathematical, Physical and Engineering Sciences"* against its unpunctuated registry entry), titles with slight morphological variations (e.g., *Natural Hazards and Earth System Sciences* vs. the registered *Natural Hazards and Earth System Science*) fail to resolve.

* **Historical ISSN Shifts and Consolidation:** Certain journals share a complex indexing history where multiple distinct sub-publications were grouped under a single parent ISSN before receiving their own independent identifiers.
   * *Example (AGU):* *Journal of Geophysical Research: Solid Earth* was historically consolidated under the ISSN of *Journal of Geophysical Research: Atmospheres* for metadata records spanning until 2012–2013. Consequently, for any citation dated prior to 2014, Crossref may only recognize the historical parent ISSN. To successfully resolve these entries, the user must include both titles (*Journal of Geophysical Research: Atmospheres* and *Journal of Geophysical Research: Solid Earth*) in the manuscript's journal list.
   * *Other instances:* Similar historical tracking and splitting discrepancies affect journals such as *Comptes Rendus Geoscience* and *Journal of Earth System Science*, requiring identical multi-title listing for older papers.

* **HTML Pollution and Whitespace Normalization:** Metadata returned by the Crossref API occasionally includes embedded HTML tags (such as `<i>`, `<b>`, or `<sup>`). The tool automatically sanitizes these strings by unescaping HTML entities and removing styling tags, while explicitly preserving structural `<sup>` and `<sub>` tags in the local work repository (`LOCAL_REPO_DIR_PATH / work_records.json`), but removing them in the final CSV output. 
  To handle chaotic spacing and raw line breaks (`\n`) embedded within these API records, the tool collapses all consecutive whitespaces into a single standard space character—matching how Crossref renders references on its own website.
  * *Operational Impact:* While this ensures reliable text processing, it can occasionally inject unintended spaces around superscripts or subscripts in mathematical expressions or chemical formulas (e.g., rendering as `CO <sub>2</sub>` instead of `CO<sub>2</sub>` in the local work repository and `CO 2` instead of `CO2` in the final output). Note that this side effect only occurs on API records that contain raw line breaks within or adjacent to the HTML tags.

### 3. Consequences for the User

When a journal title fails to resolve to an ISSN, or when an author keyword search yields inconclusive metadata, the tool cannot safely guarantee the precision of the DOI. To prevent the injection of silent errors into the bibliography, the tool skips these ambiguous entries.

> ⚠️ **Manual Intervention Required:** In these specific scenarios, users must manually search the Crossref interface or the journal's website to retrieve the correct DOI and complete the reference.


## 📅 Roadmap

* [ ] **Context-Aware Author Matching:** Implement secondary filters to improve DOI resolution accuracy for common surnames (e.g., Smith, Singh, Müller).
