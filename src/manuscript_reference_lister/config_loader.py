import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# work and output directories
WORK_DIR_PATH = os.getenv("WORK_DIR_PATH", "output")
OUTPUT_DIR_PATH = os.getenv("OUTPUT_DIR_PATH", "output")
# Dedicated test directories
TEST_WORK_DIR_PATH = os.getenv("TEST_WORK_DIR_PATH", "tests_output")
TEST_OUTPUT_DIR_PATH = os.getenv("TEST_OUTPUT_DIR_PATH", "tests_output")

# Crossref Rest API
CROSSREF_API_DELAY = float(os.getenv("CROSSREF_API_DELAY", 0.5))
CROSSREF_API_EMAIL = os.getenv("CROSSREF_EMAIL", "default@example.com")
CROSSREF_API_JOURNALS_URL = os.getenv("CROSSREF_API_JOURNALS_URL", "")
CROSSREF_API_JOURNALS_ISSN_URL = os.getenv("CROSSREF_API_JOURNALS_ISSN_URL", "")
CROSSREF_API_STYLES_URL = os.getenv("CROSSREF_API_STYLES_URL", "")
CROSSREF_API_WORKS_URL = os.getenv("CROSSREF_API_WORKS_URL", "")
CROSSREF_API_MAX_RESULTS = int(os.getenv("CROSSREF_API_MAX_RESULTS", 6))
CROSSREF_API_TIMEOUT = float(os.getenv("CROSSREF_API_TIMEOUT", 10))
CROSSREF_API_MAX_RETRY = int(os.getenv("CROSSREF_API_MAX_RETRY", 10))

# DOI Content service negotiation
DOI_API_DELAY = float(os.getenv("DOI_API_DELAY", 0.4))
DOI_API_URL = os.getenv("DOI_API_URL", "")
DOI_API_TIMEOUT = float(os.getenv("DOI_API_TIMEOUT", 10))
DOI_API_MAX_RETRY = int(os.getenv("DOI_API_MAX_RETRY", 10))

CONTEXT_KEYWORDS = os.getenv("CONTEXT_KEYWORDS", "")

JOURNAL_UPDATE_DAYS = os.getenv("JOURNAL_UPDATE_DAYS", 30)
JOURNAL_UPDATE_MAX = os.getenv("JOURNAL_UPDATE_MAX", 100)

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
for d in [WORK_DIR_PATH, OUTPUT_DIR_PATH, TEST_WORK_DIR_PATH, TEST_OUTPUT_DIR_PATH]:
    if not Path(d).is_dir():
        os.makedirs(d)
