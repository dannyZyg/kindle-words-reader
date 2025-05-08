import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from params import Filters


class WordTable(Enum):
    """Column names for word table"""

    ID = "word_id"
    WORD = "word"
    STEM = "stem"
    LANG = "lang"
    CATEGORY = "category"


class LookupTable(Enum):
    """Column names for lookup table"""

    ID = "lookup_id"
    WORD = "word_key"
    BOOK = "book_key"
    USAGE = "usage"
    TIMESTAMP = "timestamp"


class BookTable(Enum):
    """Column names for book table"""

    ID = "book_id"
    TITLE = "book_title"
    AUTHORS = "book_authors"


class LearningState(Enum):
    LEARNING = 0
    MASTERED = 100


@dataclass
class Book:
    id: str
    title: str


@dataclass
class Lookup:
    id: str  # CR!D7ZAMANRR92JQCKW5YCR7V5E92ST:CC94DA53:1133:5
    word: str
    book: str
    sentence: str  # The actual sentence where the word was looked up!
    date: datetime
    word_id: str
    language: str  # e.g. ja
    category: LearningState  # enum e.g. LearningState.LEARNING


class KindleVocabDB:
    _instance = None

    def __init__(self, path: str) -> None:
        if KindleVocabDB._instance is not None:
            raise RuntimeError("call instance() instead")

        self._db: sqlite3.Connection = sqlite3.connect(path)

    @classmethod
    def instance(cls, path: str):
        if not cls._instance:
            cls._instance = cls(path)

        return cls._instance

    def _convert_to_datetime(self, timestamp_ms: int) -> datetime:
        """Returns the UTC datetime from the db ms timestamp."""

        # database timestamps are in ms. Convert to seconds.
        timestamp_sec = timestamp_ms / 1000
        return datetime.fromtimestamp(timestamp_sec, tz=timezone.utc)

    def _datetime_to_milliseconds(self, dt: datetime) -> int:
        """Converts a UTC datetime to milliseconds since epoch."""
        # Ensure the datetime object is timezone-aware (UTC in this case)
        if dt.tzinfo is None:
            # Assuming naive datetimes are UTC if not specified otherwise
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    def _book_factory(self, cursor: sqlite3.Cursor, row: sqlite3.Row) -> Book:
        # Get the column names
        fields = [column[0] for column in cursor.description]
        # Create a dict for the row of column name to value
        names_to_values = {key: value for key, value in zip(fields, row)}

        return Book(
            id=names_to_values.get(BookTable.ID.value, ""),
            title=names_to_values.get(BookTable.TITLE.value, ""),
        )

    def _lookup_factory(self, cursor: sqlite3.Cursor, row: sqlite3.Row) -> Lookup:
        """Maps a table row to Lookup objects"""
        # Get the column names
        fields = [column[0] for column in cursor.description]
        # Create a dict for the row of column name to value
        names_to_values = {key: value for key, value in zip(fields, row)}

        # Transform to Lookup object
        return Lookup(
            id=names_to_values.get(LookupTable.ID.value, ""),
            sentence=names_to_values.get(LookupTable.USAGE.value, ""),
            date=self._convert_to_datetime(
                names_to_values.get(LookupTable.TIMESTAMP.value, 0)
            ),
            word=names_to_values.get(WordTable.WORD.value, ""),
            word_id=names_to_values.get(WordTable.ID.value, ""),
            book=names_to_values.get(BookTable.TITLE.value, ""),
            language=names_to_values.get(WordTable.LANG.value, ""),
            category=LearningState(names_to_values.get(WordTable.CATEGORY.value)),
        )

    def get_books_with_lookups(self) -> list[Book]:
        cursor = self._db.cursor()
        cursor.row_factory = self._book_factory

        sql = """
        SELECT DISTINCT
            b.id as book_id,
            b.title as book_title
        FROM LOOKUPS lu
        INNER JOIN BOOK_INFO b ON b.id = lu.book_key
        ORDER BY b.title ASC;
        """
        result = cursor.execute(sql)
        return result.fetchall()

    def get_lookups(self, filters: Filters) -> list[Lookup]:
        cursor = self._db.cursor()
        cursor.row_factory = self._lookup_factory

        offset = filters.limit * filters.page

        sql_base = """
        SELECT
            lu.id as lookup_id,
            lu.word_key,
            lu.book_key,
            lu.usage,
            lu.timestamp,
            w.id as word_id,
            w.word,
            w.stem,
            w.lang,
            w.category,
            b.id as book_id,
            b.title as book_title,
            b.authors as book_authors
        FROM LOOKUPS lu
        INNER JOIN WORDS w ON w.id = lu.word_key
        INNER JOIN BOOK_INFO b ON b.id = lu.book_key
        """

        where_clauses = []
        parameters = []

        if filters.should_show_unique_sentences():
            where_clauses.append("""
                lu.usage IN (
                    SELECT lu.usage
                    FROM LOOKUPS lu
                    GROUP BY lu.usage
                    HAVING COUNT(*) = 1
                )
            """)

        if filters.date_from:
            # Convert datetime to milliseconds since epoch for comparison
            date_from_ms = self._datetime_to_milliseconds(filters.date_from)
            where_clauses.append("lu.timestamp >= ?")
            parameters.append(date_from_ms)

        if filters.date_to:
            # Convert datetime to milliseconds since epoch for comparison
            date_to_ms = self._datetime_to_milliseconds(filters.date_to)
            where_clauses.append("lu.timestamp <= ?")
            parameters.append(date_to_ms)

        if filters.book_id:
            where_clauses.append("lu.book_key = ?")
            parameters.append(filters.book_id)

        # Combine WHERE clauses if any
        if where_clauses:
            sql_base += " WHERE " + " AND ".join(where_clauses)

        # Add ORDER BY, LIMIT, and OFFSET
        sql_base += """
        ORDER BY lu.timestamp DESC
        LIMIT ? OFFSET ?
        """
        parameters.extend([filters.limit, offset])

        result = cursor.execute(sql_base, parameters)
        return result.fetchall()

    def close(self):
        """Closes the database connection."""
        if hasattr(self, "_db") and self._db:
            self._db.close()
            print("Database connection closed.")
