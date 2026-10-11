"""Offline Philadelphia Fed RUC vintages; no forecast or source acquisition.

The availability boundary is a declared reconstruction policy, not an observed
intraday release clock: first XNYS open strictly after the midquarter 15th.
Original workbooks stay private. Monthly rows and quarterly versions differ.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import io
import math
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from benchmarks.finmultitime import calendar_for, next_open

SOURCE_URL = "https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/ruc"
PIN_SHA256 = "d971e59d3ed5f1322a46631743508fb1ad5eee39bfbe12425a641a277fdd9b9a"
MAX_COMPRESSED_BYTES = 2 * 1024 * 1024
POLICY = "first_XNYS_open_strictly_after_midquarter_15th; admit_strictly_before_issue"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MEMBERS = ("xl/workbook.xml", "xl/sharedStrings.xml", "xl/worksheets/sheet1.xml")


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include an explicit timezone")
    return value.astimezone(timezone.utc)


def vintage_cutoff(label: str) -> date:
    match = re.fullmatch(r"RUC(\d{2})Q([1-4])", label)
    if not match:
        raise ValueError("Invalid RUC vintage column")
    yy, quarter = map(int, match.groups())
    # RUC starts 1965Q4. Two-digit source labels cover 1965 through 2064.
    return date(1900 + yy if yy >= 65 else 2000 + yy, 3 * quarter - 1, 15)


def load_workbook(path: Path, *, acquired_at: datetime,
                  expected_sha256: str = PIN_SHA256, calendar=None,
                  source_basis: str = "Philadelphia_Fed_reconstructed_RUC_vintage") -> dict:
    """Validate a pinned, bounded XLSX and retain every period/version cell."""
    acquired = utc(acquired_at)
    with path.open("rb") as source:
        raw = source.read(MAX_COMPRESSED_BYTES + 1)
    if len(raw) > MAX_COMPRESSED_BYTES:
        raise ValueError("Workbook exceeds compressed size bound")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Workbook source hash mismatch")
    # Parse the exact bytes whose hash was admitted, never reopen a mutable path.
    with ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate workbook ZIP members")
        roots = {}
        for name in MEMBERS:
            info = archive.getinfo(name)
            if info.flag_bits & 1 or info.file_size > 12 * 1024 * 1024:
                raise ValueError("Unsupported or oversized workbook member")
            content = archive.read(name)
            if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
                raise ValueError("XML entity declarations forbidden")
            roots[name] = ET.fromstring(content)
    sheets = roots[MEMBERS[0]].findall("m:sheets/m:sheet", NS)
    if len(sheets) != 1 or sheets[0].get("name") != "ruc":
        raise ValueError("Expected single ruc workbook sheet")
    strings = ["".join(t.text or "" for t in item.findall(".//m:t", NS))
               for item in roots[MEMBERS[1]].findall("m:si", NS)]

    def cells(row):
        result = {}
        for cell in row:
            reference = cell.get("r", "")
            match = re.fullmatch(r"([A-Z]+)\d+", reference)
            if not match or match[1] in result or cell.find("m:f", NS) is not None:
                raise ValueError("Invalid, duplicate or formula workbook cell")
            value = cell.findtext("m:v", namespaces=NS)
            if cell.get("t") == "s":
                if value is None or not value.isdigit() or int(value) >= len(strings):
                    raise ValueError("Invalid workbook shared string")
                value = strings[int(value)]
            result[match[1]] = value
        return result

    rows = roots[MEMBERS[2]].findall("m:sheetData/m:row", NS)
    if not rows:
        raise ValueError("Empty workbook")
    headers = cells(rows[0])
    if headers.pop("A", None) != "DATE" or not headers:
        raise ValueError("Expected DATE and RUC columns")
    if len(set(headers.values())) != len(headers):
        raise ValueError("Duplicate vintage columns")
    cutoffs = {column: vintage_cutoff(label) for column, label in headers.items()}
    if calendar is None:
        calendar = calendar_for(str(min(cutoffs.values())), str(max(cutoffs.values()).replace(year=max(cutoffs.values()).year + 1)))
    vintages = {label: {"available_at": next_open(str(cutoffs[column]), calendar).isoformat(), "values": {}}
                for column, label in headers.items()}
    for row in rows[1:]:
        values = cells(row)
        # The pinned workbook ends with a formatting-only row (no cells).
        if not values:
            continue
        period = values.pop("A", "")
        if not isinstance(period, str) or not re.fullmatch(r"\d{4}:(0[1-9]|1[0-2])", period):
            raise ValueError("Invalid monthly observation period")
        period = period.replace(":", "-")
        if any(column not in headers for column in values):
            raise ValueError("Unexpected workbook column")
        for column, label in headers.items():
            if period in vintages[label]["values"]:
                raise ValueError("Duplicate observation period")
            value = values.get(column)
            if value in (None, "", "#N/A"):
                parsed = None
            else:
                parsed = float(value)
                if not math.isfinite(parsed) or not 0 <= parsed <= 100:
                    raise ValueError("Invalid unemployment percentage")
            vintages[label]["values"][period] = parsed
    return {"source_url": SOURCE_URL, "source_sha256": digest,
            "source_basis": source_basis, "acquired_at": acquired.isoformat(),
            "availability_basis": "reconstructed_cutoff_policy_not_original_delivery",
            "availability_policy": POLICY, "units": "percent", "adjustment": "seasonally_adjusted",
            "vintages": vintages}


def observation(workbook: dict, *, issue_at: datetime, period: str) -> dict:
    """Select the latest eligible version; missing never borrows another version."""
    issue = utc(issue_at)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise ValueError("Invalid requested observation period")
    if period > issue.strftime("%Y-%m"):
        raise ValueError("Requested observation period is future at issue")
    eligible = [(datetime.fromisoformat(v["available_at"]), label, v)
                for label, v in workbook["vintages"].items()
                if datetime.fromisoformat(v["available_at"]) < issue]
    selected = max(eligible, default=None, key=lambda item: item[0])
    value = selected[2]["values"].get(period) if selected else None
    return {key: workbook[key] for key in ("source_url", "source_sha256", "source_basis", "acquired_at",
            "availability_basis", "availability_policy", "units", "adjustment")} | {
        "issue_at": issue.isoformat(), "observation_period": period,
        "vintage_id": selected[1] if selected else None,
        "available_at": selected[0].isoformat() if selected else None,
        "value": value, "status": "available" if value is not None else "missing_observation" if selected else "no_eligible_vintage"}
