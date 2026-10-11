"""Bounded, pinned FinMultiTime AAPL import and historical subject-only snapshot.

Archive transport/parsing uses Python's standard library. Snapshot session times
use this project's declared exchange_calendars dependency. No upstream code,
pickle, model endpoint, or downloader script is executed.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import urllib.request
import urllib.parse
import zipfile

DATASET = "Wenyan0110/Multimodal-Dataset-Image_Text_Table_TimeSeries-for-Financial-Time-Series-Forecasting"
REVISION = "72d4e97b9acb92651949b8efb22c55676ff633ff"
PROTOCOL = "finmultitime_aapl_three_channel_v1"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "work/datasets/finmultitime"
MAX_RANGE = 16 * 1024 * 1024
MAX_TRANSFER = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 48 * 1024 * 1024
MAX_TOTAL_MEMBER_BYTES = 96 * 1024 * 1024
ARCHIVES = {
    "time_series/S&P500_time_series.zip": (483028209, {
        "S&P500_time_series/aapl.csv": "aapl-prices.csv"}),
    "text/sp500_news.zip": (3605043317, {
        "sp500_news/AAPL.jsonl": "aapl-news.jsonl"}),
    "table/SP500_tabular.zip": (3309800083, {
        "financial_reports/aapl/condensed_consolidated_balance_sheets.json": "aapl-balance-sheets.json",
        "financial_reports/aapl/condensed_consolidated_statement_of_equity.json": "aapl-equity.json",
        "financial_reports/aapl/condensed_consolidated_statement_of_cash_flows.json": "aapl-cash-flows.json"}),
}
EXPECTED_FILES = {name for _, members in ARCHIVES.values() for name in members.values()}
EXPECTED_SOURCE_HASHES = {
    "aapl-prices.csv": "80524d21ca03e539cf5792ce2f446a5913ae26955b1981a4061929635a01f444",
    "aapl-news.jsonl": "d464056a2c668bda7f76936fbe78171e94b2b2b6388fd53efb3ca918e9af4659",
    "aapl-balance-sheets.json": "a974b912aa33b731bff446adde1d84cd09e0315f0c4b83a47c8f38ebbe09455e",
    "aapl-equity.json": "d07dd7e7adf6d3a437a431c73c28750299ac2a0bea7a0dd485c81aa2b1496ae9",
    "aapl-cash-flows.json": "f95d982b0d619d121b18d0a926698a851922ded8d0af420e272d55d8b8c7b06f",
}
CONCEPTS = {
    "CashAndCashEquivalentsAtCarryingValue", "Assets", "Liabilities", "StockholdersEquity",
    "AccountsPayableCurrent", "AccountsReceivableNetCurrent", "InventoryNet", "AssetsCurrent",
    "LiabilitiesCurrent", "LongTermDebtCurrent", "LongTermDebtNoncurrent", "CommonStockSharesOutstanding",
    "NetIncomeLoss", "OperatingIncomeLoss", "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInInvestingActivities",
    "NetCashProvidedByUsedInFinancingActivities", "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsOfDividends", "PaymentsForRepurchaseOfCommonStock",
}
POLICY = {
    "price": "source daily row usable at the actual XNYS session close; historical price vintage/adjustment unverified",
    "text": "day-only Date interpreted as US publisher calendar date; activate at following XNYS session open, never on source day",
    "fundamentals": "per-fact filed date plus accession controls availability; activate at following XNYS session open; period end and outer filing_date do not control it",
    "text_selection": "latest five eligible unique URL+date+article-hash records within seven calendar days; retain first 800 chars and original text hash",
    "fundamental_selection": "whitelisted US-GAAP concepts, latest eligible period and filing per concept/unit/start duration; retain original accession/filed/end",
    "missing": "explicit unavailable; no neutral, zero-valued, synthetic or current-data replacement",
}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def canonical_hash(value) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


class RangeBudget:
    def __init__(self, maximum=MAX_TRANSFER):
        self.maximum, self.transferred, self.requests = maximum, 0, []


class RemoteArchive(io.RawIOBase):
    """Seekable read-only ZIP transport; reject servers ignoring bounded ranges."""
    def __init__(self, url, size, budget, opener=urllib.request.urlopen):
        self.url, self.size, self.budget, self.opener, self.position = url, size, budget, opener, 0

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset if whence == 2 else -1
        if not 0 <= position <= self.size:
            raise ValueError("Archive seek outside declared bounds")
        self.position = position
        return position

    def read(self, size=-1):
        size = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if not size:
            return b""
        if size > MAX_RANGE or self.budget.transferred + size > self.budget.maximum:
            raise ValueError("Bounded archive transfer cap exceeded")
        start, end = self.position, self.position + size - 1
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "Plectis-Zenith-FinMultiTime/1"})
        with self.opener(request, timeout=45) as response:
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{self.size}":
                raise ValueError("Server did not honor the exact pinned archive range; full download refused")
            raw = response.read(size + 1)
        if len(raw) != size:
            raise ValueError("Archive range length mismatch")
        self.budget.transferred += size
        self.budget.requests.append({"archive_url": self.url, "start": start, "bytes": size})
        self.position += size
        return raw


def read_member(archive, name, size_limit=MAX_MEMBER_BYTES):
    matches = [item for item in archive.infolist() if item.filename == name]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate allowlisted ZIP member")
    info = matches[0]
    if info.is_dir() or info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
        raise ValueError("Unsupported or encrypted allowlisted ZIP member")
    if not 0 < info.file_size <= size_limit or info.compress_size > MAX_RANGE:
        raise ValueError("Allowlisted member exceeds extraction bounds")
    with archive.open(info) as member:
        raw = member.read(size_limit + 1)
    if len(raw) != info.file_size or len(raw) > size_limit:
        raise ValueError("ZIP size declaration mismatch")
    # zipfile validates the central-directory CRC when the complete member is read.
    return info, raw


def verify_dataset(directory: Path):
    manifest = json.loads((directory / "source-manifest.json").read_text())
    frozen = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if canonical_hash(frozen) != manifest.get("manifest_sha256"):
        raise ValueError("Dataset manifest identity drift")
    if manifest.get("dataset") != DATASET or manifest.get("revision") != REVISION or manifest.get("protocol_version") != PROTOCOL:
        raise ValueError("Dataset pin or protocol mismatch")
    names = [r["path"] for r in manifest["files"]]
    if len(names) != len(EXPECTED_FILES) or set(names) != EXPECTED_FILES:
        raise ValueError("Dataset must contain exactly the five allowlisted AAPL leaves")
    if manifest.get("availability_policy") != POLICY:
        raise ValueError("Frozen availability policy mismatch")
    if sum(r["bytes"] for r in manifest["files"]) > MAX_TOTAL_MEMBER_BYTES:
        raise ValueError("Frozen source total-size cap exceeded")
    for record in manifest["files"]:
        path = directory / record["path"]
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise ValueError("Dataset member path escapes local custody directory")
        if record["bytes"] > MAX_MEMBER_BYTES or path.stat().st_size != record["bytes"]:
            raise ValueError("Frozen source member-size cap/mismatch")
        if record["sha256"] != EXPECTED_SOURCE_HASHES[record["path"]]:
            raise ValueError("Frozen source checksum disagrees with audited pinned member")
        raw = path.read_bytes()
        if len(raw) != record["bytes"] or digest(raw) != record["sha256"]:
            raise ValueError("Frozen source file checksum/size mismatch")
    return manifest


def import_dataset(directory: Path = DEFAULT_DATA):
    if (directory / "source-manifest.json").exists():
        return verify_dataset(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any((directory / name).exists() for name in EXPECTED_FILES):
        raise ValueError("Incomplete prior import retained: choose a new empty custody directory")
    budget, records, total = RangeBudget(), [], 0
    for path, (size, members) in ARCHIVES.items():
        url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{urllib.parse.quote(path, safe='/')}"
        with zipfile.ZipFile(RemoteArchive(url, size, budget)) as archive:
            if len(archive.infolist()) > 12000:
                raise ValueError("Archive member-count cap exceeded")
            for name, output in members.items():
                info, raw = read_member(archive, name)
                if digest(raw) != EXPECTED_SOURCE_HASHES[output]:
                    raise ValueError("Downloaded member disagrees with independently audited pinned bytes")
                total += len(raw)
                if total > MAX_TOTAL_MEMBER_BYTES:
                    raise ValueError("Total extracted data cap exceeded")
                (directory / output).write_bytes(raw)
                records.append({"path": output, "archive_url": url, "archive_bytes": size, "member": name,
                                "bytes": len(raw), "compressed_bytes": info.compress_size,
                                "crc32": f"{info.CRC:08x}", "sha256": digest(raw)})
    manifest = {"schema_version": "finmultitime_source_manifest_v1", "protocol_version": PROTOCOL,
                "dataset": DATASET, "revision": REVISION, "symbol": "AAPL",
                "acquired_at_utc": datetime.now(timezone.utc).isoformat(), "files": records,
                "source_url": f"https://huggingface.co/datasets/{DATASET}/tree/{REVISION}",
                "paper": "https://arxiv.org/abs/2506.05019", "implementation_sha256": digest(Path(__file__).read_bytes()),
                "availability_policy": POLICY, "transport_bytes": budget.transferred,
                "range_requests": budget.requests, "upstream_code_executed": False,
                "rights": {"release_card_license": "MIT", "source_material_rights": "Nasdaq/publisher news and Yahoo prices require separate redistribution review",
                           "public_raw_data_redistribution_allowed_by_this_import": False,
                           "custody": "local research only; ignored work directory"},
                "original_protocol": "four-modal published corpus; this AAPL three-channel adapter is a new preparation protocol, not a published-score reproduction"}
    manifest["manifest_sha256"] = canonical_hash(manifest)
    write_json(directory / "source-manifest.json", manifest)
    return verify_dataset(directory)


def calendar_for(start: str, end: str):
    import exchange_calendars
    return exchange_calendars.get_calendar("XNYS", start=start, end=end)


def next_open(stamp: str, calendar):
    # Strictly later calendar date, so a date-only item cannot enter its own day.
    following = date.fromisoformat(stamp) + timedelta(days=1)
    session = calendar.date_to_session(following.isoformat(), direction="next")
    return calendar.session_open(session).to_pydatetime().astimezone(timezone.utc)


def finite(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a numeric financial fact")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite financial value")
    return result


def source_lines(path: Path):
    with path.open() as source:
        yield from source


def price_records(path: Path, calendar, cutoff):
    records, rejected = [], 0
    for row in csv.DictReader(source_lines(path)):
        try:
            stamp = datetime.fromisoformat(row["Date"]).date().isoformat()
            if stamp > cutoff.date().isoformat():
                continue
            if not calendar.is_session(stamp):
                rejected += 1
                continue
            available = calendar.session_close(stamp).to_pydatetime().astimezone(timezone.utc)
            if available > cutoff:
                continue
            record = {name.lower(): finite(row[name]) for name in ["Open", "High", "Low", "Close", "Volume"]}
            if min(record[k] for k in ["open", "high", "low", "close"]) <= 0 or record["volume"] < 0:
                raise ValueError("Invalid price row")
            records.append({"symbol": "AAPL", "source_date": row["Date"], "session_date": stamp,
                            "available_at_utc": available.isoformat(), **record})
        except (ValueError, KeyError, TypeError):
            rejected += 1
    records.sort(key=lambda r: r["session_date"])
    if len({r["session_date"] for r in records}) != len(records):
        raise ValueError("Duplicate source price session")
    return records[-20:], {"eligible_price_rows": len(records), "rejected_rows": rejected, "retained_rows": min(20, len(records))}


def news_records(path: Path, calendar, cutoff):
    selected, unique, rejected, eligible = [], set(), 0, 0
    lower = cutoff.date() - timedelta(days=7)
    for line in source_lines(path):
        try:
            raw = json.loads(line)
            stamp = raw["Date"]
            if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
                raise ValueError("Expected day-only news date")
            source_day = date.fromisoformat(stamp)
            if not lower <= source_day < cutoff.date():
                continue
            available = next_open(stamp, calendar)
            if available > cutoff:
                continue
            text, url = raw["Article"], raw["Url"]
            if not isinstance(text, str) or not text.strip() or not isinstance(url, str):
                raise ValueError("Missing article or URL")
            key = (stamp, url, digest(text.encode()))
            if key in unique:
                continue
            unique.add(key); eligible += 1
            selected.append({"id": canonical_hash(key), "symbol": "AAPL", "source_date": stamp,
                             "available_at_utc": available.isoformat(), "url": url, "text": text[:800],
                             "original_text_sha256": key[-1], "original_chars": len(text),
                             "truncated_chars": max(0, len(text) - 800),
                             "time_uncertainty": "day-only; assumed US publisher date, precise publication/ingest time unverified"})
        except (ValueError, KeyError, TypeError):
            rejected += 1
    selected.sort(key=lambda r: (r["source_date"], r["id"]), reverse=True)
    return selected[:5], {"eligible_unique_news_rows": eligible, "rejected_rows": rejected,
                          "retained_rows": min(5, len(selected)), "omitted_rows": max(0, len(selected) - 5)}


def fundamental_records(paths, calendar, cutoff):
    latest, seen, rejected, eligible = {}, set(), 0, 0
    for path in paths:
        try:
            root = json.loads(path.read_text())
        except json.JSONDecodeError:
            rejected += 1
            continue
        if not isinstance(root, dict) or not isinstance(root.get("filings", []), list):
            rejected += 1
            continue
        for filing in root.get("filings", []):
            if not isinstance(filing, dict) or not isinstance(filing.get("facts", {}), dict):
                rejected += 1
                continue
            taxonomy = filing.get("facts", {}).get("us-gaap", {})
            if not isinstance(taxonomy, dict):
                rejected += 1
                continue
            for concept, entry in taxonomy.items():
                if concept not in CONCEPTS:
                    continue
                if not isinstance(entry, dict) or not isinstance(entry.get("units", {}), dict):
                    rejected += 1
                    continue
                for unit, facts in entry.get("units", {}).items():
                    if not isinstance(facts, list):
                        rejected += 1
                        continue
                    for fact in facts:
                        try:
                            if not isinstance(fact, dict):
                                raise ValueError("Expected a financial fact object")
                            filed, end, accession = fact["filed"], fact["end"], fact["accn"]
                            date.fromisoformat(filed); date.fromisoformat(end)
                            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
                                raise ValueError("Invalid filing accession")
                            if filed >= cutoff.date().isoformat() or end > filed:
                                continue
                            available = next_open(filed, calendar)
                            if available > cutoff:
                                continue
                            val = finite(fact["val"])
                            duration_start = fact.get("start", "")
                            if duration_start:
                                date.fromisoformat(duration_start)
                                if duration_start > end:
                                    raise ValueError("Fact period starts after it ends")
                            identity = (concept, unit, duration_start, end, filed, accession, val)
                            if identity in seen:
                                continue
                            seen.add(identity); eligible += 1
                            key = (concept, unit, duration_start)
                            record = {"symbol": "AAPL", "taxonomy": "us-gaap", "concept": concept, "unit": unit,
                                      "value": val, "start": duration_start or None, "end": end, "filed": filed,
                                      "accession": accession, "form": fact.get("form"), "fiscal_year": fact.get("fy"),
                                      "fiscal_period": fact.get("fp"), "available_at_utc": available.isoformat(),
                                      "source_path": path.name, "outer_filing_date": filing.get("filing_date"),
                                      "time_uncertainty": "per-fact SEC filed day only; exact acceptance and data acquisition time unverified"}
                            if key not in latest or (end, filed, accession) > (latest[key]["end"], latest[key]["filed"], latest[key]["accession"]):
                                latest[key] = record
                        except (ValueError, KeyError, TypeError):
                            rejected += 1
    # Prefer the latest period/context for each concept/unit, retaining duration explicitly.
    context = {}
    for record in latest.values():
        key = (record["concept"], record["unit"])
        if key not in context or (record["end"], record["filed"], record["accession"], record["start"] or "") > (context[key]["end"], context[key]["filed"], context[key]["accession"], context[key]["start"] or ""):
            context[key] = record
    selected = sorted(context.values(), key=lambda r: (r["concept"], r["unit"]))
    return selected, {"eligible_unique_facts": eligible, "rejected_facts": rejected, "retained_rows": len(selected)}


def snapshot(directory: Path, issue_date: str, output: Path, calendar=None):
    manifest = verify_dataset(directory)
    date.fromisoformat(issue_date)
    calendar = calendar or calendar_for("1999-01-01", "2026-01-01")
    if not calendar.is_session(issue_date):
        raise ValueError("Issue date is not an XNYS session")
    cutoff = calendar.session_close(issue_date).to_pydatetime().astimezone(timezone.utc)
    prices, price_receipt = price_records(directory / "aapl-prices.csv", calendar, cutoff)
    current_price = bool(prices and prices[-1]["session_date"] == issue_date)
    price_receipt.update({"current_issue_price_available": current_price,
                          "latest_source_session": prices[-1]["session_date"] if prices else None,
                          "data_gap": None if current_price else "missing_exact_issue_session_bar"})
    news, news_receipt = news_records(directory / "aapl-news.jsonl", calendar, cutoff)
    fundamentals, fact_receipt = fundamental_records([directory / name for name in sorted(EXPECTED_FILES) if name.endswith(".json")], calendar, cutoff)
    sources = {r["path"]: {"sha256": r["sha256"], "source_url": r["archive_url"], "member": r["member"]} for r in manifest["files"]}
    channels = {"prices": {"availability": "available" if current_price else "partial_stale" if prices else "unavailable", "records": prices, "selection_receipt": price_receipt},
                "text": {"availability": "available" if news else "unavailable", "records": news, "selection_receipt": news_receipt},
                "fundamentals": {"availability": "available" if fundamentals else "unavailable", "records": fundamentals, "selection_receipt": fact_receipt}}
    for channel in channels.values():
        if any(datetime.fromisoformat(r["available_at_utc"]) > cutoff for r in channel["records"]):
            raise ValueError("Snapshot contains unavailable evidence")
    packet = {"schema_version": "finmultitime_historical_issue_packet_v1", "protocol_version": PROTOCOL,
              "dataset_revision": REVISION, "source_manifest_sha256": manifest["manifest_sha256"],
              "implementation_sha256": digest(Path(__file__).read_bytes()), "issue_at_utc": cutoff.isoformat(),
              "issue_date": issue_date, "symbol": "AAPL", "channels": channels, "sources": sources,
              "availability_policy": POLICY, "unavailable_feed_lanes": ["ETF", "MACRO", "POLYMARKET", "STOCKGRID", "CALCULATOR"],
              "truth_side_evidence_included": False, "native_lab_execution_claimed": False,
              "historical_llm_performance_claimed": False, "public_raw_data_redistribution_allowed": False,
              "limitations": ["The source card's MIT label does not establish all publisher/platform redistribution rights.",
                              "Historical text may be in modern model training data; no contamination-free claim.",
                              "Date-only publication/filing availability is conservatively approximated, not proven point-in-time acquisition.",
                              "Source prices have retrospective adjustment/vintage uncertainty.",
                              "AAPL file assignment does not prove every article is relevant to AAPL; no relevance model is applied.",
                              "This is a three-channel preparation slice, not the published four-modal forecasting protocol or seven-lane Lab completion."]}
    packet["snapshot_sha256"] = canonical_hash(packet)
    if (output / "issue-packet.json").exists():
        previous = json.loads((output / "issue-packet.json").read_text())
        if previous != packet:
            raise ValueError("Refuse to overwrite a different frozen issue snapshot; choose a new output directory")
        artifacts = json.loads((output / "artifact-manifest.json").read_text())
        expected_paths = {"issue-packet.json", "feed-envelopes.json", "artifacts/global_stock_feed.json",
                          "artifacts/global_news_feed.json", "runtime_context.json"}
        if set(artifacts["files"]) != expected_paths or artifacts.get("snapshot_sha256") != packet["snapshot_sha256"]:
            raise ValueError("Frozen snapshot artifact manifest mismatch")
        for name, expected in artifacts["files"].items():
            if digest((output / name).read_bytes()) != expected:
                raise ValueError("Frozen snapshot artifact drift")
        # Verification-only replay: do not rewrite artifacts whose bytes may be evidence.
        return packet
    write_json(output / "issue-packet.json", packet)
    from system.lib.feed_envelope import build_envelope
    metadata = {"timestamp": cutoff.isoformat(), "as_of": cutoff.isoformat(), "status": "partial",
                "context_class": "subject_side_evidence", "dataset_revision": REVISION,
                "source_manifest_sha256": manifest["manifest_sha256"], "historical_availability_unverified": True,
                "run_id": output.name, "time_anchor": cutoff.isoformat(),
                "data_schema_version": "finmultitime_historical_adapter_v1"}
    observation = {"provider": "FinMultiTime", "session_date": prices[-1]["session_date"] if prices else None,
                   "interval": "1d", "auto_adjust": None, "price_basis": "dataset_ohlcv_adjustment_unverified",
                   "currency": None, "source_hash": sources["aapl-prices.csv"]["sha256"]}
    stock_data = {"columns": ["Category", "Ticker", "Identity", "Price", "Vol_20d", "Chg_5d", "Chg_63d", "Z_Short", "Z_Long"],
                  "rows": [["Historical sample", "AAPL", "Apple Inc.", prices[-1]["close"] if current_price else None, None, None, None, None, None]] if prices else [],
                  "price_history": prices, "fundamentals": fundamentals,
                  "fundamental_provider": "FinMultiTime SEC fact extracts; per-fact filed/accession availability"}
    news_data = {"items": [{"text": record["text"], "time": record["available_at_utc"], "url": record["url"],
                            "source_handle": "FinMultiTime", "source_label": "Historical publisher article; activation time is estimated",
                            "category": "historical_dataset", "source_date": record["source_date"],
                            "publication_time_utc": None, "available_at_utc": record["available_at_utc"],
                            "time_uncertainty": record["time_uncertainty"], "original_text_sha256": record["original_text_sha256"]} for record in news]}
    feeds = {"STOCK": build_envelope({**metadata, "tool": "finmultitime_historical_prices_and_facts"},
                                    stock_data),
             "NEWS": build_envelope({**metadata, "tool": "finmultitime_day_only_articles"}, news_data)}
    feeds["STOCK"]["metadata"]["diagnostics"] = {"price_observations": {"AAPL": observation}, "coverage": price_receipt,
                                                 "fundamental_coverage": fact_receipt, "missing_feed_lanes": packet["unavailable_feed_lanes"]}
    feeds["NEWS"]["metadata"]["diagnostics"] = {"coverage": news_receipt, "publication_timestamps_observed": False,
                                                "time_field_basis": "conservative following-session activation, not original publication time"}
    # Canonical artifact names, but no invented engine node-success/hash/group receipts.
    write_json(output / "artifacts/global_stock_feed.json", feeds["STOCK"])
    write_json(output / "artifacts/global_news_feed.json", feeds["NEWS"])
    write_json(output / "runtime_context.json", {"as_of": cutoff.isoformat(), "time_anchor": cutoff.isoformat(),
                                                 "adapter_only": True, "unavailable_feed_lanes": packet["unavailable_feed_lanes"]})
    write_json(output / "feed-envelopes.json", {"feeds": feeds, "issue_at_utc": cutoff.isoformat(),
                                               "available_channels": [k for k, v in channels.items() if v["availability"] == "available"],
                                               "unavailable_feed_lanes": packet["unavailable_feed_lanes"], "native_lab_execution_claimed": False})
    names = ["issue-packet.json", "feed-envelopes.json", "artifacts/global_stock_feed.json",
             "artifacts/global_news_feed.json", "runtime_context.json"]
    write_json(output / "artifact-manifest.json", {"schema_version": "finmultitime_snapshot_artifacts_v1",
                                                  "snapshot_sha256": packet["snapshot_sha256"],
                                                  "files": {name: digest((output / name).read_bytes()) for name in names}})
    return packet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    acquire = sub.add_parser("import"); acquire.add_argument("--output", type=Path, default=DEFAULT_DATA)
    view = sub.add_parser("snapshot"); view.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    view.add_argument("--issue-date", required=True); view.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            result = import_dataset(args.output)
            print(json.dumps({"status": "imported_verified", "revision": result["revision"], "files": len(result["files"]),
                              "transport_bytes": result["transport_bytes"], "output": str(args.output)}))
        else:
            result = snapshot(args.dataset, args.issue_date, args.output)
            print(json.dumps({"status": "snapshot_written", "snapshot_sha256": result["snapshot_sha256"],
                              "channels": {k: {"availability": v["availability"], "records": len(v["records"])} for k, v in result["channels"].items()}}))
        return 0
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print(f"FinMultiTime refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
