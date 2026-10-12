"""Verify selective substitution, real-input retention and the public boundary."""
import json
from pathlib import Path

import pytest

from zenith import demo

ROOT = Path(__file__).resolve().parents[1]


def source(directory, anchor):
    # Constructed test bytes exercise the retained-input path, not a market specimen.
    demo.write(directory / "runtime_context.json", {"as_of": anchor})
    for lane in demo.REAL_LANES:
        demo.write(directory / "artifacts" / f"global_{lane}_feed.json", {
            "id": f"global_{lane}_feed", "status": "success", "metadata": {"as_of": anchor},
            "data": {"test_private_marker": "RETAIN_THIS_EXACTLY", "rows": [["TEST", 100]]}})
    for lane in demo.REPLACED_LANES:
        (directory / "artifacts" / f"global_{lane}_feed.json").write_text("must not be read as JSON")


def test_mixed_demo_retains_inputs_and_recalculates_without_public_leak(tmp_path, monkeypatch):
    earlier, later, output = (tmp_path / s for s in ("before", "after", "prepared"))
    source(earlier, "2026-07-20T20:00:00+00:00")
    source(later, "2026-07-21T20:00:00+00:00")
    calls = []

    def calculator(config, run_dir):
        feeds = {lane: json.loads((run_dir / "artifacts" / f"global_{lane}_feed.json").read_text())
                 for lane in ("stock", "etf", "macro")}
        assert feeds["macro"]["metadata"]["synthetic_fixture"] is True
        assert feeds["stock"]["data"]["test_private_marker"] == "RETAIN_THIS_EXACTLY"
        calls.append(run_dir)
        return {"metadata": {"status": "success"}, "data": {"test_private_marker": "DERIVED_PRIVATE"}}

    monkeypatch.setattr(demo, "calculate", calculator)
    result = demo.prepare(ROOT, earlier, later, output)
    assert result["data_mode"] == "mixed" and result["model_calls"] == 0
    assert len(calls) == 2
    for original, name in ((earlier, "earlier"), (later, "later")):
        for lane in demo.REAL_LANES:
            relative = Path("artifacts") / f"global_{lane}_feed.json"
            assert (original / relative).read_bytes() == (output / name / relative).read_bytes()
        assert len(list((output / name / "artifacts").glob("*.json"))) == 6
    public = "".join(p.read_text() for p in (output / "public").glob("*.json"))
    assert "RETAIN_THIS_EXACTLY" not in public and "DERIVED_PRIVATE" not in public
    assert str(tmp_path) not in public
    with pytest.raises(ValueError, match="new directory"):
        demo.prepare(ROOT, earlier, later, output)


def test_mixed_demo_refuses_reversed_clocks_and_marked_substitutes(tmp_path):
    earlier, later = tmp_path / "a", tmp_path / "b"
    source(earlier, "2026-07-20T20:00:00+00:00")
    source(later, "2026-07-21T20:00:00+00:00")
    with pytest.raises(ValueError, match="Later snapshot"):
        demo.prepare(ROOT, later, earlier, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    p = earlier / "artifacts/global_stock_feed.json"
    value = json.loads(p.read_text()); value["metadata"]["synthetic_fixture"] = True
    demo.write(p, value)
    with pytest.raises(ValueError, match="requires real stock"):
        demo.prepare(ROOT, earlier, later, tmp_path / "out")


def test_public_edition_contains_no_real_payloads_or_old_execution_routes():
    from zenith.web import Website
    app = Website(ROOT)
    data = json.loads(app.get("/api/v1/evidence/sources").body)["data"]
    for snapshot in data["snapshots"]:
        assert len(snapshot["lanes"]) == 6
        for lane in snapshot["lanes"]:
            if lane["input_origin"] == "real_saved_input":
                assert lane["source_sha256"] == lane["input_sha256"]
                assert lane["public_payload"].startswith("withheld")
    for identifier in ("observations", "window-result", "conditional-result"):
        with pytest.raises(FileNotFoundError):
            app.get(f"/api/v1/evidence/{identifier}")
