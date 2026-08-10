class LearnWikiError(Exception):
    """Base error for the project."""


class IngestError(LearnWikiError):
    """Fetching or transcribing a source failed."""


class ExtractionError(LearnWikiError):
    """The LLM returned output that could not be validated."""
