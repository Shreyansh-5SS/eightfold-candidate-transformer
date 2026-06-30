from abc import ABC, abstractmethod
from typing import List
from src.models import RawRecord


class SourceParser(ABC):
    """Common interface every source (structured or unstructured) implements."""

    SOURCE_NAME: str = "base"

    @abstractmethod
    def parse(self, input_path_or_url: str) -> List[RawRecord]:
        """Return a list of RawRecord — empty list on any failure, never raises."""
        raise NotImplementedError