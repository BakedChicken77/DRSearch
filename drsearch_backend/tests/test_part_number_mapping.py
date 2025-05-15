from app.chain.mapping import PartNumberMapping


def test_part_number_mapping_reads_csv(tmp_path, monkeypatch):
    csv_data = "file_name,Downloaded File\nx.pdf,\\\\srv\\x.pdf\n"
    f = tmp_path / "m.csv"
    f.write_text(csv_data)

    # m = PartNumberMapping(f.name)
    monkeypatch.setattr("app.chain.mapping._MAPPING_DIR", tmp_path)
    m = PartNumberMapping(f.name.split("\\")[-1])   # basename only
    assert m.data == {"x.pdf": "\\\\srv\\x.pdf"}


def test_part_number_mapping_missing_file(caplog):
    m = PartNumberMapping("does-not-exist.csv")
    assert m.data is None
    # warning logged once
    warnings = [r for r in caplog.messages if "not found" in r]
    assert warnings
