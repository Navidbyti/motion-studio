import hashlib
import json

import pytest

from motion_studio import data
from motion_studio.claims import verify_claims
from motion_studio.util import StudioError


def test_canonical_and_tokens():
    assert data.canonical("−1,234.50") == "-1234.50"
    assert data.canonical("+1.29") == "1.29"
    assert data.canonical("۴۲۷٫۳۵") == "427.35"
    assert data.number_tokens("CO2 hit 427.35 ppm in 2025 (+34.8%)") == ["427.35", "2025", "+34.8%"]


def test_bind_and_provenance(proj):
    (proj / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (proj / "data" / "raw" / "t.csv").write_text("year,v\n1960,-0.03\n2024,1.29\n", encoding="utf-8")
    (proj / "data" / "bindings.json").write_text(json.dumps({
        "values": {"t2024": {"value": "1.29", "display": "+1.29 °C", "source": "raw/t.csv", "location": "line 3"},
                   "big": {"value": "268563", "display": "268,563 miles"}},
        "series": {"t": {"file": "raw/t.csv", "x": "year", "y": "v"}}}), encoding="utf-8")
    out = data.bind(proj)
    assert out["values"]["t2024"]["prefix"] == "+" and out["values"]["t2024"]["suffix"] == " °C"
    assert out["values"]["big"]["grouping"] is True
    allowed = data.allowed_numbers(data.load(proj), ["31 GPS satellites"])
    for ok in ("+1.29", "1960", "−0.03", "268,563", "31"):
        assert data.number_allowed(ok, allowed), ok
    for bad in ("0.03", "1.3", "268,564"):          # dropped sign, rounding drift, typo
        assert not data.number_allowed(bad, allowed), bad


def test_bind_rejects_display_mismatch_and_dirty_series(proj):
    (proj / "data" / "bindings.json").write_text(json.dumps({"values": {"x": {"value": "1.29", "display": "1.3 °C"}}}), encoding="utf-8")
    with pytest.raises(StudioError):
        data.bind(proj)
    (proj / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (proj / "data" / "raw" / "d.csv").write_text("year,v\n2020,***\n", encoding="utf-8")
    (proj / "data" / "bindings.json").write_text(json.dumps({"series": {"s": {"file": "raw/d.csv", "x": "year", "y": "v"}}}), encoding="utf-8")
    with pytest.raises(StudioError, match="non-numeric"):
        data.bind(proj)


def test_claims_ledger(tmp_path):
    src = tmp_path / "sources" / "nasa.txt"
    src.parent.mkdir()
    src.write_text("Orion traveled 268,563 miles from Earth.", encoding="utf-8")
    ledger = {"schemaVersion": 1,
              "sources": [{"id": "nasa", "uri": "sources/nasa.txt", "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                           "title": "Artemis I", "publisher": "NASA", "url": "https://www.nasa.gov/mission/artemis-i/",
                           "publicationDate": None, "retrievedDate": "2026-09-28"}],
              "claims": [{"id": "dist", "text": "Orion flew 268,563 miles from Earth", "eventDate": "2022-11-28", "uncertainty": "",
                          "onScreen": ["268,563 miles from Earth"],
                          "evidence": [{"sourceId": "nasa", "quote": "268,563 miles from Earth", "relation": "supports", "location": "para 1"}]}]}
    path = tmp_path / "claims.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    r = verify_claims(path)
    assert r["status"] == "source_linked" and r["onScreen"] == ["268,563 miles from Earth"]
    ledger["claims"][0]["evidence"][0]["quote"] = "268,564 miles"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    assert verify_claims(path)["status"] == "failed"
