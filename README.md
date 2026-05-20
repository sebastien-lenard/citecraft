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

# Process a manuscript file and specify output
```uv run references-lister -f "manuscript.docx" -o "C:\Documents\bibliography.csv```
Output file can be omitted, default generated file is OUTPUT_DIR_PATH / "manuscript_references.csv"
# Pipe source directly
```echo "Text (Lenard et al., 2020)\r\nJournals\r\nNature Geoscience" | uv run references-lister```
# Run tests
```uv run pytest```
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

### Coarse-Grained Cache Updates for Incomplete Journals

The tool maintains a local JSON database (`records`) to cache journal metadata across executions, minimizing redundant API requests to Crossref. This cache expires based on the `JOURNAL_UPDATE_DAYS` environment variable. 

However, if a journal title is flagged with incomplete metadata during a run, the tool triggers a remote Crossref refresh even if the cache has not expired. Incomplete metadata occurs under two conditions:
* **Missing ISSN:** The registry has no ISSN mapped to the title (`Found without ISSN`).
* **Missing Works:** An ISSN exists but has no registered publication years or historical records (`Found without work`).

**The Limitation:** 
The update mechanism operates at the **journal title level**, not the individual ISSN level. If a journal possesses multiple ISSNs (such as an old print ISSN and a modern e-ISSN) and *only one* of these records lacks metadata, the tool will force a full Crossref API reload for **all** records sharing that input title. While this ensures data completeness, it leads to redundant API queries for the valid ISSNs of that same journal.

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
* **References that include HTML code:** Certain references include HTML code. The tool converts HTML entities, remove end of lines and HTML tags, except the superscript and subscript ones. During this operation, existing spaces are preserved (reduced to 1 space character), which makes references appear like in the crossref website. This may not be optimal for mathematic or chemical constant or formulas. Note that some references, despite having subscripts and superscripts are not concerned by this issue (because they don't include ends-of-line).
* **HTML Pollution and Whitespace Normalization:** Metadata returned by the Crossref API occasionally includes embedded HTML tags (such as `<i>`, `<b>`, or `<sup>`). The tool automatically sanitizes these strings by unescaping HTML entities and removing styling tags, while explicitly preserving structural `<sup>` and `<sub>` tags. 
  To handle chaotic spacing and raw line breaks (`\n`) embedded within these API records, the tool collapses all consecutive whitespaces into a single standard space character—matching how Crossref renders references on its own website.
  * *Operational Impact:* While this ensures reliable text processing, it can occasionally inject unintended spaces around superscripts or subscripts in mathematical expressions or chemical formulas (e.g., rendering as `CO <sub>2</sub>` instead of `CO<sub>2</sub>`). Note that this side effect only occurs on API records that contain raw line breaks within or adjacent to the HTML tags.

### 3. Consequences for the User

When a journal title fails to resolve to an ISSN, or when an author keyword search yields inconclusive metadata, the tool cannot safely guarantee the precision of the DOI. To prevent the injection of silent errors into the bibliography, the tool skips these ambiguous entries.

> ⚠️ **Manual Intervention Required:** In these specific scenarios, users must manually search the Crossref interface or the journal's website to retrieve the correct DOI and complete the reference.


## 📅 Roadmap

* Researching context-aware matching for common surnames (Smith, Singh, etc.).
