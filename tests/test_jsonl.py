import json
from src import jsonl


def test_roundtrip_with_unicode_line_separators(tmp_path):
    # U+2028 / U+2029 / U+0085 อยู่ในประกาศงานจริง; splitlines() จะตัด 1 record เป็น 2 บรรทัด
    rows = [{"id": 1, "text": "a\u2028b\u2029c\u0085d\x1ce"}, {"id": 2, "text": "ไทย"}]
    p = tmp_path / "x.jsonl"
    jsonl.write_jsonl(p, rows)
    assert jsonl.read_jsonl(p) == rows
    assert len(p.read_text(encoding="utf-8").splitlines()) == 2   # เครื่องมืออื่นที่ใช้ splitlines ก็ยังอ่านได้


def test_reads_files_written_by_plain_json_dumps(tmp_path):
    p = tmp_path / "old.jsonl"
    p.write_text(json.dumps({"t": "a\u2028b"}, ensure_ascii=False) + "\n" + json.dumps({"t": "z"}) + "\n", encoding="utf-8")
    assert [r["t"] for r in jsonl.read_jsonl(p)] == ["a\u2028b", "z"]


def test_truncated_last_line_is_skipped(tmp_path, capsys):
    p = tmp_path / "t.jsonl"
    p.write_text('{"a": 1}\n{"a": 2}\n{"a": ', encoding="utf-8")
    assert jsonl.read_jsonl(p) == [{"a": 1}, {"a": 2}]
    assert "อ่านไม่ได้" in capsys.readouterr().err


def test_missing_file_and_bom_and_crlf(tmp_path):
    assert jsonl.read_jsonl(tmp_path / "nope.jsonl") == []
    p = tmp_path / "b.jsonl"
    p.write_bytes(b'\xef\xbb\xbf{"a": 1}\r\n\r\n{"a": 2}\r\n')
    assert jsonl.read_jsonl(p) == [{"a": 1}, {"a": 2}]


def test_write_is_atomic_no_tmp_left(tmp_path):
    p = tmp_path / "w.jsonl"
    jsonl.write_jsonl(p, [{"a": 1}])
    jsonl.append_jsonl(p, [{"a": 2}])
    assert jsonl.read_jsonl(p) == [{"a": 1}, {"a": 2}]
    assert [f.name for f in tmp_path.iterdir()] == ["w.jsonl"]
