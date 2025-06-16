from app.chain.mapping import PartNumberMapping


def test_create_mapping_table_from_csv(monkeypatch, tmp_path):
    from app.chain import mapping as mapping_mod

    csv_content = "file_name,Downloaded File\nabc.pdf,\\\\share\\abc.pdf\n"
    csv_file = tmp_path / "m.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    executed: list[tuple[str, tuple | list]] = []

    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def execute(self, q, params=None):
            executed.append((str(q), params))

        def executemany(self, q, params_seq):
            executed.append((str(q), list(params_seq)))

    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def cursor(self):
            return DummyCursor()

        def commit(self):
            executed.append(("commit", ()))

    monkeypatch.setattr(mapping_mod.psycopg2, "connect", lambda *_a, **_k: DummyConn())

    mapping_mod.create_mapping_table_from_csv(csv_file, "conn", "tbl")

    assert any("CREATE TABLE" in e[0] for e in executed)
    assert any("INSERT INTO" in e[0] for e in executed)


def test_part_number_mapping_reads_table(monkeypatch):
    rows = [("x.pdf", "\\\\srv\\x.pdf")]

    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def execute(self, _q):
            pass

        def fetchall(self):
            return rows

    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def cursor(self):
            return DummyCursor()

    monkeypatch.setattr("app.chain.mapping.psycopg2.connect", lambda *_a, **_k: DummyConn())

    m = PartNumberMapping("dummy_table")
    assert m.data == {"x.pdf": "\\\\srv\\x.pdf"}


def test_part_number_mapping_missing_table(caplog, monkeypatch):
    def _raise(*_a, **_k):
        raise Exception("missing")

    monkeypatch.setattr("app.chain.mapping.psycopg2.connect", _raise)

    m = PartNumberMapping("missing")
    assert m.data is None
    warnings = [r for r in caplog.messages if "Failed to load" in r]
    assert warnings
