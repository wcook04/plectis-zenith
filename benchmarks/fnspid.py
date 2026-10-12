"""Pinned FNSPID AA raw prices/news -> native six-lane daily feed snapshots.

No upstream preprocessing is executed. In particular, parse original EST/EDT
publication strings instead of upstream's incorrectly shifted UTC column.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REVISION = "4054842ec476953b30ee874d4b7e8eea786a21fa"
REPOSITORY = "https://github.com/zGeneral/fnspid"
RAW_BASE = f"https://raw.githubusercontent.com/Zdong104/FNSPID_Financial_News_Dataset/{REVISION}/data_processor"
FILES = {
    "aa-news.csv": {"upstream": "news_data_raw/aa.csv", "bytes": 7150795,
                    "sha256": "ebffcd331219c30b066706579c2fe8e61ab0d4380743b3ba70d424836ace33ed"},
    "aa-prices.csv": {"upstream": "stock_price_data_raw/aa.csv", "bytes": 1509616,
                      "sha256": "50725eb03d9daf850da70a8cbbb3ce4d8eba88f46b089ea7575cc2ee5d7d84dd"},
}
LANES = {"STOCK": "global_stock_feed", "ETF": "global_etf_feed", "MACRO": "global_macro_feed",
         "NEWS": "global_news_feed", "POLYMARKET": "global_polymarket_feed",
         "CALCULATOR": "global_calculator_feed"}
POLICY = {
    "prices": "last 20 actual XNYS daily Close/OHLCV rows ending at issue close; no Adj Close substitution",
    "news": "all unique substantive original bodies within previous 7 calendar days, original timezone checked; never use preprocessed UTC",
    "missing": "literal Text=0, absent bodies, absent publication clocks and missing lanes are unavailable, never neutral evidence",
    "universe": "one AA price series; AA news-file assignment does not establish article-specific relevance",
    "publication": "original publisher timestamps are asserted publication times; historical capture and revision vintages remain unverified",
    "rights": "local research custody only; repository license does not establish redistribution rights in publisher articles",
}


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def calendar_for(start: str, end: str):
    import exchange_calendars
    return exchange_calendars.get_calendar("XNYS", start=start, end=end)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(directory):
    manifest = json.loads((directory / "source-manifest.json").read_text())
    expected = {"schema": "fnspid_raw_source_v1", "repository": REPOSITORY, "revision": REVISION,
                "files": FILES, "policy": POLICY}
    if manifest != {**expected, "manifest_sha256": canonical_hash(expected)}:
        raise ValueError("FNSPID source manifest differs from audited pin/policy")
    for name, record in FILES.items():
        path = directory / name
        if path.is_symlink() or path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"FNSPID source bytes differ: {name}")
    return manifest


def acquire(directory, cached_source=None):
    if (directory / "source-manifest.json").exists():
        return verify(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError("Retain incomplete acquisition; use an empty directory")
    for name, record in FILES.items():
        if cached_source is not None:
            source = cached_source / ("fnspid-data_processor--" + record["upstream"].replace("/", "--"))
            if source.stat().st_size != record["bytes"] or sha(source) != record["sha256"]:
                raise ValueError("Cached raw source differs from pin")
            shutil.copyfile(source, directory / name)
        else:
            request = urllib.request.Request(f"{RAW_BASE}/{record['upstream']}", headers={"User-Agent": "Zenith-local-research/1"})
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read(record["bytes"] + 1)
            if len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise ValueError("Downloaded raw source differs from pin")
            (directory / name).write_bytes(raw)
    manifest = {"schema": "fnspid_raw_source_v1", "repository": REPOSITORY, "revision": REVISION,
                "files": FILES, "policy": POLICY}
    write_json(directory / "source-manifest.json", {**manifest, "manifest_sha256": canonical_hash(manifest)})
    return verify(directory)


def publication_time(value):
    match = re.fullmatch(r"(.+?)\s+—\s+(\d{1,2}:\d{2})\s+(am|pm)\s+(EST|EDT)", value.strip(), re.I)
    if match:
        day, clock, meridian, zone = match.groups()
        local = datetime.strptime(f"{day} {clock} {meridian.upper()}", "%B %d, %Y %I:%M %p")
    else:
        match = re.fullmatch(r"([A-Z]{3} \d{1,2}, \d{4}) (\d{1,2}:\d{2})(AM|PM) (EST|EDT)", value.strip(), re.I)
        if not match:
            raise ValueError("Original publication clock unavailable")
        day, clock, meridian, zone = match.groups()
        local = datetime.strptime(f"{day} {clock} {meridian.upper()}", "%b %d, %Y %I:%M %p")
    # Honor the explicit original offset, then verify the local civil timestamp.
    offset = -5 if zone.upper() == "EST" else -4
    aware = local.replace(tzinfo=timezone(timedelta(hours=offset)))
    ny = aware.astimezone(ZoneInfo("America/New_York"))
    if ny.replace(tzinfo=None) != local or ny.tzname() != zone.upper():
        raise ValueError("Publisher timezone conflicts with NY daylight-saving calendar")
    return aware.astimezone(timezone.utc)


def select_news(path, cutoff):
    selected, seen = [], set()
    counts = {"source_rows": 0, "missing_body": 0, "unusable_clock": 0, "future": 0, "older_than_window": 0, "duplicates": 0}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for number, row in enumerate(csv.DictReader(source), 2):
            counts["source_rows"] += 1
            body = row.get("Text", "").strip()
            if not body or body == "0":
                counts["missing_body"] += 1
                continue
            try:
                published = publication_time(row["Date"])
            except (ValueError, KeyError):
                counts["unusable_clock"] += 1
                continue
            if published > cutoff:
                counts["future"] += 1
                continue
            if published < cutoff - timedelta(days=7):
                counts["older_than_window"] += 1
                continue
            body_hash = hashlib.sha256(body.encode()).hexdigest()
            identity = (row["Url"], published.isoformat(), body_hash)
            if identity in seen:
                counts["duplicates"] += 1
                continue
            seen.add(identity)
            selected.append({"text": body, "url": row["Url"], "time": published.isoformat(),
                             "publication_time_utc": published.isoformat(), "available_at_utc": published.isoformat(),
                             "source_date_original": row["Date"], "original_text_sha256": body_hash,
                             "source_row": number, "source_handle": "FNSPID original publisher text",
                             "category": "historical_market_news", "symbol_relevance": "unverified",
                             "timestamp_basis": "original publisher clock; capture/revision history unverified"})
    selected.sort(key=lambda item: (item["time"], item["url"], item["original_text_sha256"]))
    counts["retained_rows"] = len(selected)
    counts["published_on_issue_day"] = sum(datetime.fromisoformat(r["time"]).astimezone(ZoneInfo("America/New_York")).date() == cutoff.astimezone(ZoneInfo("America/New_York")).date() for r in selected)
    return selected, counts


def select_prices(path, cutoff, calendar):
    selected = []
    with path.open(newline="") as source:
        for row in csv.DictReader(source):
            session = date.fromisoformat(row["Date"])
            if not cutoff.date() - timedelta(days=180) <= session <= cutoff.date():
                continue
            if not calendar.is_session(session.isoformat()):
                raise ValueError("Price row is not an exchange session")
            close = calendar.session_close(session.isoformat()).to_pydatetime().astimezone(timezone.utc)
            if close > cutoff:
                continue
            values = {key.lower(): float(row[key]) for key in ("Open", "High", "Low", "Close", "Volume")}
            if any(not math.isfinite(x) or x < 0 for x in values.values()) or values["close"] <= 0:
                raise ValueError("Invalid financial observation")
            selected.append({"symbol": "AA", "session_date": session.isoformat(), "available_at_utc": close.isoformat(), **values})
    selected.sort(key=lambda x: x["session_date"])
    if len({x["session_date"] for x in selected}) != len(selected):
        raise ValueError("Duplicate price session")
    if not selected or selected[-1]["session_date"] != cutoff.date().isoformat():
        raise ValueError("Exact issue-day price unavailable; refuse stale quote substitution")
    return selected[-20:]


def snapshot(directory, issue_date, output):
    manifest = verify(directory)
    issue = date.fromisoformat(issue_date)
    calendar = calendar_for((issue-timedelta(days=190)).isoformat(), (issue+timedelta(days=14)).isoformat())
    if not calendar.is_session(issue_date):
        raise ValueError("Issue date is not an XNYS session")
    cutoff = calendar.session_close(issue_date).to_pydatetime().astimezone(timezone.utc)
    prices = select_prices(directory / "aa-prices.csv", cutoff, calendar)
    news, coverage = select_news(directory / "aa-news.csv", cutoff)
    def evidence(prefix, subject, summary, source, identity):
        return {"ledger_id": prefix + "_" + canonical_hash(identity)[:8].upper(),
                "subject": subject, "signal_summary": summary, "source_ref": source}
    stock_evidence = [
        evidence("S", "AA", f"AA observed Close={prices[-1]['close']} at {cutoff.isoformat()}; no later observations.",
                 "global_stock_feed.data.price_history[-1]", prices[-1]),
        evidence("S", "AA history", f"{len(prices)} completed daily bars from {prices[0]['session_date']} to {issue_date}; no 63-session change available.",
                 "global_stock_feed.data.price_history", prices),
    ]
    change5 = (prices[-1]["close"] / prices[-6]["close"] - 1) * 100 if len(prices) >= 6 else None
    if change5 is not None:
        stock_evidence.append(evidence("S", "AA 5-session change",
            f"Close-to-Close five-session change = {change5:.8f} percent; {prices[-6]['session_date']} Close {prices[-6]['close']} to {issue_date} Close {prices[-1]['close']}.",
            "global_stock_feed.data.price_history[-6] and [-1]", {"from": prices[-6], "to": prices[-1], "formula": "100*(to.close/from.close-1)"}))
    news_evidence = [evidence("N", "publisher article", r["text"], f"global_news_feed.data.items[{i}]", {"url": r["url"], "body": r["original_text_sha256"], "time": r["time"]}) for i,r in enumerate(news)]
    for i,record in enumerate(news):
        record["ledger_id"] = news_evidence[i]["ledger_id"]
    all_ids = [r["ledger_id"] for r in stock_evidence + news_evidence]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("Evidence identifier collision")
    missing = [lane for lane in LANES if lane not in {"STOCK", "NEWS"}]
    packet = {"schema": "fnspid_daily_snapshot_v1", "symbol": "AA", "issue_date": issue_date,
              "issue_at_utc": cutoff.isoformat(), "revision": REVISION,
              "source_manifest_sha256": manifest["manifest_sha256"], "implementation_sha256": sha(Path(__file__)),
              "policy": POLICY, "prices": prices, "news": news, "news_coverage": coverage, "stock_evidence": stock_evidence, "news_evidence": news_evidence,
              "unavailable_feed_lanes": missing, "native_execution_claimed": False,
              "historical_performance_claimed": False, "price_vintage": "retrospective dataset Close; corporate-action vintage unverified"}
    packet["snapshot_sha256"] = canonical_hash(packet)
    metadata = {"tool": "fnspid_recorded_feed", "status": "partial", "timestamp": cutoff.isoformat(),
                "as_of": cutoff.isoformat(), "time_anchor": cutoff.isoformat(), "run_id": output.name,
                "context_class": "subject_side_evidence", "data_schema_version": "fnspid_daily_snapshot_v1",
                "source_manifest_sha256": manifest["manifest_sha256"], "source_revision": REVISION}
    stock = {"availability": "available", "columns": ["Category", "Ticker", "Identity", "Price", "Vol_20d", "Chg_5d", "Chg_63d", "Z_Short", "Z_Long"],
             "rows": [["Historical sample", "AA", "Alcoa", prices[-1]["close"], None, change5, None, None, None]],
             "price_history": prices, "price_basis": packet["price_vintage"], "evidence_dictionary": stock_evidence,
             "metric_definitions": {"Chg_5d": "100*(Close[t]/Close[t-5]-1), percent; exact source bars in price_history", "Chg_63d": "unavailable; only twenty bars supplied"}}
    feeds = {}
    for lane, node in LANES.items():
        data = stock if lane == "STOCK" else {"availability": "available" if news else "unavailable", "items": news, "coverage": coverage, "evidence_dictionary": news_evidence} if lane == "NEWS" else {
            "availability": "unavailable", "reason": "This bounded source contains prices and news only; no historical observations supplied for this lane.", "items": [], "rows": []}
        diagnostics = {"coverage": {"availability": data["availability"], "unavailable_feed_lanes": missing}}
        if lane == "STOCK":
            diagnostics["price_observations"] = {"AA": {"provider": "FNSPID", "session_date": issue_date, "interval": "1d", "auto_adjust": None, "price_basis": "dataset_close_vintage_unverified", "source_hash": FILES["aa-prices.csv"]["sha256"]}}
        lane_metadata = {**metadata, "diagnostics": diagnostics}
        if lane == "STOCK":
            # Acquisition status describes this observed price table, not other lanes.
            # Vintage uncertainty remains explicit and must match the scoring policy.
            lane_metadata.update(status="success", currency="USD", price_basis="dataset_close_vintage_unverified")
        feeds[node] = {"metadata": lane_metadata, "data": data}
    artifacts = {"issue-packet.json": packet, "runtime_context.json": {"as_of": cutoff.isoformat(), "time_anchor": cutoff.isoformat(), "adapter_only": True},
                 **{f"artifacts/{node}.json": value for node, value in feeds.items()}}
    if output.exists() and any(output.iterdir()):
        old = json.loads((output / "artifact-manifest.json").read_text())
        if old.get("snapshot_sha256") != packet["snapshot_sha256"] or set(old["files"]) != set(artifacts):
            raise ValueError("Refuse to overwrite a different or incomplete frozen snapshot")
        for name, value in artifacts.items():
            if sha(output/name) != old["files"][name] or json.loads((output/name).read_text()) != value:
                raise ValueError("Frozen artifact drift")
        return packet
    for name, value in artifacts.items():
        write_json(output / name, value)
    write_json(output / "artifact-manifest.json", {"schema": "fnspid_artifact_manifest_v1", "snapshot_sha256": packet["snapshot_sha256"],
                                                  "files": {name: sha(output/name) for name in artifacts}})
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    acq = sub.add_parser("acquire")
    acq.add_argument("--output", type=Path, default=ROOT/"work/datasets/fnspid-aa")
    acq.add_argument("--cached-source", type=Path)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--dataset", type=Path, default=ROOT/"work/datasets/fnspid-aa")
    snap.add_argument("--issue-date", required=True)
    snap.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "acquire":
        result = acquire(args.output, args.cached_source)
        print(json.dumps({"status": "source_verified", "revision": result["revision"]}))
    else:
        result = snapshot(args.dataset, args.issue_date, args.output)
        print(json.dumps({"status": "snapshot_verified", "snapshot_sha256": result["snapshot_sha256"], "price_rows": len(result["prices"]), "news": result["news_coverage"], "unavailable": result["unavailable_feed_lanes"]}))


if __name__ == "__main__":
    main()
