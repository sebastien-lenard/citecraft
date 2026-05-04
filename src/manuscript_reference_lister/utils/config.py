import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# work and output directories
LOCAL_REPO_DIR_PATH = os.getenv("LOCAL_REPO_DIR_PATH", "repo")
OUTPUT_DIR_PATH = os.getenv("OUTPUT_DIR_PATH", "output")

# Crossref Rest API
CROSSREF_API_DELAY = float(os.getenv("CROSSREF_API_DELAY", 0.5))
CROSSREF_API_EMAIL = os.getenv("CROSSREF_EMAIL", "default@example.com")
CROSSREF_API_JOURNALS_URL = os.getenv("CROSSREF_API_JOURNALS_URL", "")
CROSSREF_API_JOURNALS_ISSN_URL = os.getenv("CROSSREF_API_JOURNALS_ISSN_URL", "")
CROSSREF_API_STYLES_URL = os.getenv("CROSSREF_API_STYLES_URL", "")
CROSSREF_API_WORKS_URL = os.getenv("CROSSREF_API_WORKS_URL", "")
CROSSREF_API_WORKS_GET_LIMIT = int(os.getenv("CROSSREF_API_WORKS_GET_LIMIT", 6))
CROSSREF_API_TIMEOUT = float(os.getenv("CROSSREF_API_TIMEOUT", 10))
CROSSREF_API_MAX_RETRY = int(os.getenv("CROSSREF_API_MAX_RETRY", 10))

# DOI Content service negotiation
DOI_API_DELAY = float(os.getenv("DOI_API_DELAY", 0.4))
DOI_API_URL = os.getenv("DOI_API_URL", "")
DOI_API_TIMEOUT = float(os.getenv("DOI_API_TIMEOUT", 10))
DOI_API_MAX_RETRY = int(os.getenv("DOI_API_MAX_RETRY", 10))

CONTEXT_KEYWORDS = os.getenv("CONTEXT_KEYWORDS", "")

JOURNAL_UPDATE_DAYS = int(os.getenv("JOURNAL_UPDATE_DAYS", 30))
JOURNAL_UPDATE_LIMIT = int(os.getenv("JOURNAL_UPDATE_LIMIT", 100))

PARSER_DEFAULT_BLACKLIST = [
    "Fig",
    "Figs",
    "Figure",
    "Figures",
    "Tab",
    "Table",
    "Eq",
    "Plate",
    "Section",
    "See",
    "e.g.",
    "i.e.",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

# TODO: Should be in a function called only when necessary.
# Ensure directories exist
for d in [LOCAL_REPO_DIR_PATH, OUTPUT_DIR_PATH]:
    if not Path(d).is_dir():
        os.makedirs(d)
