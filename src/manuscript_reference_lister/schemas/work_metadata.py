from typing import TypedDict

# TODO: maybe some fields need to be None when they are ""


class WorkMetadata(TypedDict):
    input_first_authors_txt: str  # e.g. Lenard et al., Guns and Vanacker
    input_year_and_suffix: str  # e.g. 2020a
    input_ISSN: str  # e.g. 1752-0894
    reference: str  # e.g. Lenard, S. J. P., Lavé, J., France-Lanord, C., Aumaître, G., Bourlès, D. L., & Keddadouche, K. (2020). Steady erosion rates in the Himalayas through late Cenozoic climatic changes. Nature Geoscience, 13(6), 448–452. https://doi.org/10.1038/s41561-020-0585-2
    style: str  # e.g. apa
    DOI: str  # e.g. 10.1038/s41561-020-0585-2
    type: str  # e.g. journal-article


def is_work_metadata(record: dict) -> bool:
    """Check if a dictionary contains ALL keys defined in WorkMetadata."""
    required_keys = set(WorkMetadata.__annotations__.keys())
    return isinstance(record, dict) and required_keys.issubset(record.keys())


def create_work_metadata(**kwargs) -> WorkMetadata:
    """Creates a default WorkMetadata with values overridable by kwargs."""
    defaults: WorkMetadata = {
        "input_first_authors_txt": "Unknown",
        "input_year_and_suffix": "2010",
        "input_ISSN": "1752-0894",
        "reference": "",
        "style": "apa",
        "DOI": "",
        "type": "",
    }
    defaults.update(kwargs)
    return defaults
