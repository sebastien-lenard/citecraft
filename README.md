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

## ⚠️ Known Issues

## 🐛 Known Bugs

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

### 3. Consequences for the User

When a journal title fails to resolve to an ISSN, or when an author keyword search yields inconclusive metadata, the tool cannot safely guarantee the precision of the DOI. To prevent the injection of silent errors into the bibliography, the tool skips these ambiguous entries.

> ⚠️ **Manual Intervention Required:** In these specific scenarios, users must manually search the Crossref interface or the journal's website to retrieve the correct DOI and complete the reference.

## 🔌Journals and ISSN: good to know

Some distinct journals were grouped under a unique ISSN and later had their own ISSN. For instance, Journal of Geophysical Research: Solid Earth was grouped with other instances under the ISSN of Journal of Geophysical Research until 2012/2013. In that case, if a citation is earlier than 2014, the user should add in the list of Journals of the manuscript the title Journal of Geophysical Research, in addition to Journal of Geophysical Research: Solid Earth.

## 📅 Roadmap

* Researching context-aware matching for common surnames (Smith, Singh, etc.).
