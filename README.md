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
```uv run references-lister -f "C:\Documents\manuscript.docx" -o "C:\Documents\bibliography.csv" -s "copernicus-publications"```

# Control log verbosity (-v for INFO, -vv for DEBUG):
```uv run references-lister -f "C:\Documents\manuscript.docx" -v```

# Pipe source directly
```echo "Text (Lenard et al., 2020)\r\nJournals\r\nNature Geoscience" | uv run references-lister```

**CLI arguments:**
* `-f` : Path to the `.docx` manuscript to parse.
* `-o` : Path to the output CSV file. Contains the parsed citations, Crossref/DOI lookup status, and formatted references. *(Default: `OUTPUT_DIR_PATH / "manuscript_references.csv"` if omitted)*.
* `-s` : Style identifier recognized by [citation.doi.org](https://citation.doi.org/). *(Default: `apa` if omitted)*.



# Run tests
```uv run pytest```

# Run specific test suites
Unit tests only:
```uv run pytest -m "not integration and not e2e"```
Integration (included Crossref API and DOI negotiation service) tests only:
```uv run pytest -m integration```
End to end tests only:
```uv run pytest -m e2e```



## 🐛 Known Bugs

None reported. Feel free to open an issue if you encounter unexpected behavior.

## ⚠️ Limitations with moderate impact

## 📝 Limitations with minor impact

### 📝 Finding the Correct Style Name (`-s`)

The tool formats references using the CSL style identifiers recognized by [citation.doi.org](https://citation.doi.org/).

For many major journals, the identifier is simply the lowercase title with spaces replaced by hyphens (e.g., `earth-surface-processes-and-landforms`). However, many journals do not have a unique style and instead inherit a parent format (e.g., Copernicus journals use `copernicus-publications`, AGU journals use `american-geophysical-union`).

Since the tool does not yet automate this lookup, you can find the exact string manually using the official CSL repository:

1. Search for your target journal title on the [CSL Styles GitHub Repository](https://github.com/citation-style-language/styles).
2. Open the journal's `.csl` file and inspect the first few lines:

#### Case A: The journal has its own independent style

Look at the `<id>` tag. If there is no link containing `rel="independent-parent"`, your style name is the final part of the URL inside the `<id>` tag.

```xml
<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" default-locale="en-US" class="in-text" version="1.0">
  <info>
    <title>Earth Surface Processes and Landforms</title>
    <id>http://www.zotero.org/styles/earth-surface-processes-and-landforms</id>

```

👉 *Value to pass to `-s`:* `earth-surface-processes-and-landforms`

#### Case B: The journal shares a style with a parent publisher

If the file includes a link with `rel="independent-parent"`, the tool requires the parent style name found at the end of that specific `href` attribute.

```xml
<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" version="1.0" default-locale="en-US">
  <info>
    <title>Geophysical Research Letters</title>
    <id>http://www.zotero.org/styles/geophysical-research-letters</id>
    <link href="http://www.zotero.org/styles/american-geophysical-union" rel="independent-parent"/>

```

👉 *Value to pass to `-s`:* `american-geophysical-union`

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
* **DOI Citation Negotiation Service (`doi.org`):** Once a unique DOI is successfully retrieved from Crossref, this service is queried with specific HTTP headers (`Accept: text/x-bibliography; style=apa` or other style-specific strings) to fetch the fully formatted bibliographic reference.

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

* [ ] **Automated Style Lookup:** Resolve journal titles to their official CSL style identifier automatically.
* [ ] **Context-Aware Author Matching:** Implement secondary filters to improve DOI resolution accuracy for common surnames (e.g., Smith, Singh, Müller).
