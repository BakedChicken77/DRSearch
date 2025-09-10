from app import index_options
from app.core import chain_config


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *_args, **_kwargs):
        return None

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _Cursor(self._rows)


def _run_fetch(monkeypatch, rows):
    monkeypatch.setattr(chain_config, "_PGVECTOR_URL", "postgresql://")
    monkeypatch.setattr(index_options.psycopg2, "connect", lambda *_, **__: _Conn(rows))
    return index_options._fetch_acronyms("dummy")


def test_fetch_acronyms_filters_empty_and_none(monkeypatch):
    rows = [
        {
            "cmetadata": {
                "acronym_keys": ["ABC", "", "DEF"],
                "acronym_values": ["Alpha", "foo", ""],
            }
        }
    ]
    assert _run_fetch(monkeypatch, rows) == {"ABC": "Alpha"}


def test_fetch_acronyms_respects_ignore_list_case_insensitive(monkeypatch):
    rows = [
        {
            "cmetadata": {
                "acronym_keys": ["HRS", "IT", "ip"],
                "acronym_values": [
                    "Human Resources",
                    "Information Tech",
                    "internet protocol",
                ],
            }
        }
    ]
    result = _run_fetch(monkeypatch, rows)
    assert result == {"HRS": "Human Resources"}


def test_fetch_acronyms_excludes_short_keys(monkeypatch):
    rows = [
        {
            "cmetadata": {
                "acronym_keys": ["AB", "ABC"],
                "acronym_values": ["Alpha Beta", "Gamma"],
            }
        }
    ]
    assert _run_fetch(monkeypatch, rows) == {"ABC": "Gamma"}


def test_fetch_acronyms_excludes_long_values(monkeypatch):
    rows = [
        {
            "cmetadata": {
                "acronym_keys": ["ABC", "LONG"],
                "acronym_values": [
                    "one two three four five six",
                    "word word",
                ],
            }
        }
    ]
    assert _run_fetch(monkeypatch, rows) == {"LONG": "word word"}


def test_fetch_acronyms_excludes_values_with_punctuation(monkeypatch):
    rows = [
        {
            "cmetadata": {
                "acronym_keys": ["ABC", "DEF"],
                "acronym_values": ["has, comma", "clean value"],
            }
        }
    ]
    assert _run_fetch(monkeypatch, rows) == {"DEF": "clean value"}


def test_fetch_acronyms_excludes_keys_with_more_lowercase(monkeypatch):
    rows = [
        {
            "cmetadata": {
                "acronym_keys": ["eMail", "ABC"],
                "acronym_values": ["electronic mail", "Just example"],
            }
        }
    ]
    assert _run_fetch(monkeypatch, rows) == {"ABC": "Just example"}
