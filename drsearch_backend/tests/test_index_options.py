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
        {"cmetadata": {"acronym_keys": ["A", "", "B"], "acronym_values": ["Alpha", "foo", ""]}}
    ]
    assert _run_fetch(monkeypatch, rows) == {"A": "Alpha"}


def test_fetch_acronyms_respects_ignore_list_case_insensitive(monkeypatch):
    rows = [
        {
            "cmetadata": {
                "acronym_keys": ["HR", "IT", "ip"],
                "acronym_values": ["Human Resources", "Information Tech", "internet protocol"],
            }
        }
    ]
    result = _run_fetch(monkeypatch, rows)
    assert result == {"HR": "Human Resources"}
