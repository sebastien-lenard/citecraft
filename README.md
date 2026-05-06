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

# Process a manuscript file
```uv run references-lister --input_file "manuscript.docx"```
# Pipe source directly
```echo "Text (Lenard et al., 2020)\r\nJournals\r\nNature Geoscience" | uv run references-lister```
# Run tests
```uv run pytest```
Unit tests only:
```uv run pytest -m unit```
Integration (included Crossref API and DOI negotiation service) tests only:
```uv run pytest -m integration```

## 📅 Roadmap

* Finalize formatted reference list generation (Expected in 1-2 weeks).
* Integration of pydantic for data validation.
* Researching context-aware matching for common surnames (Smith, Singh, etc.).
