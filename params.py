from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from starlette.datastructures import QueryParams


@dataclass
class Filters:
    show_unique_sentences: Literal["true"] | Literal["false"]
    book_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = 10
    page: int = 0

    @classmethod
    def from_query_params(cls, query_params: QueryParams):
        show_unique_sentences = (
            "true" if query_params.get("unique") == "true" else "false"
        )
        return cls(
            show_unique_sentences=show_unique_sentences,
            page=int(query_params.get("page", 0)),
            date_from=cls.parse_date(query_params.get("start-date-filter", "")),
            date_to=cls.parse_date(query_params.get("end-date-filter", "")),
            book_id=query_params.get("book-filter", None),
        )

    def should_show_unique_sentences(self) -> bool:
        return self.show_unique_sentences == "true"

    @classmethod
    def parse_date(cls, date_string) -> datetime | None:
        if not date_string:
            return None
        try:
            return datetime.strptime(date_string, "%Y-%m-%d")
        except ValueError:
            return None


@dataclass
class Sorting:
    sort_by: str = "date"
    sort_order: str = "desc"

    @classmethod
    def from_query_params(cls, query_params: QueryParams):
        return cls(
            sort_by=query_params.get("sort_by", "date"),
            sort_order=query_params.get("sort_order", "asc"),
        )
