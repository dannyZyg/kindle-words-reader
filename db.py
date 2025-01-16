import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class WordTable(Enum):
    """ Column names for word table """
    ID = "word_id"
    WORD = "word"
    STEM = "stem"
    LANG = "lang"
    CATEGORY = "category"


class LookupTable(Enum):
    """ Column names for lookup table """
    ID = "lookup_id"
    WORD = "word_key"
    BOOK = "book_key"
    USAGE = "usage"
    TIMESTAMP = "timestamp"


class BookTable(Enum):
    """ Column names for book table """
    ID = "book_id"
    TITLE = "book_title"
    AUTHORS = "book_authors"


class LearningState(Enum):
    LEARNING = 0
    MASTERED = 100


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
    def __init__(self, path: str) -> None:
        self.db = sqlite3.connect(path)
        self.db.row_factory = self._lookup_factory

    def _convert_to_datetime(self, timestamp: int) -> datetime:
        """Returns the UTC datetime from the db timestamp."""
        return datetime.fromtimestamp(timestamp=timestamp, tz=timezone.utc)

    def _lookup_factory(self, cursor: sqlite3.Cursor, row: sqlite3.Row) -> Lookup:
        """ Maps a table row to Lookup objects """
        # Get the column names
        fields = [column[0] for column in cursor.description]
        # Create a dict for the row of column name to value
        names_to_values = {key: value for key, value in zip(fields, row)}

        # Transform to Lookup object
        return Lookup(
            id=names_to_values.get(LookupTable.ID.value, None),
            sentence=names_to_values.get(LookupTable.USAGE.value, None),
            date=self._convert_to_datetime(names_to_values.get(LookupTable.TIMESTAMP.value, 0)),
            word=names_to_values.get(WordTable.WORD.value, None),
            word_id=names_to_values.get(WordTable.ID.value, None),
            book=names_to_values.get(BookTable.TITLE.value, None),
            language=names_to_values.get(WordTable.LANG.value, None),
            category=LearningState(names_to_values.get(WordTable.CATEGORY.value)),
        )

    def get_lookups(self) -> list[Lookup]:
        cursor = self.db.cursor()

        sql = """
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

        result = cursor.execute(sql)
        return result.fetchall()
