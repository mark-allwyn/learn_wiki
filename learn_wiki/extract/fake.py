from learn_wiki.models import SourceDocument, Extraction


class FakeExtractor:
    def __init__(self, result: Extraction):
        self._result = result

    def extract(self, doc: SourceDocument) -> Extraction:
        return self._result
