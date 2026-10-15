"""Pinned, licensed NEPSE CSV ingestion. Never runs an upstream scraper."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
import subprocess
from datetime import date
from pathlib import Path

from .providers import write_json

SOURCE = "https://github.com/socrateai-official/nepse-open-data.git"
COMMIT = "497e27238a107de00c6f435a4f4f76983205577d"
FOLDERS = {"stock": "ohlc_adjusted_stock", "index": "ohlc_index"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fetch(destination: Path):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("download destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1", SOURCE, str(destination)], check=True)
    for args in (["sparse-checkout", "init", "--cone"],
                 ["sparse-checkout", "set", *FOLDERS.values()],
                 ["fetch", "--depth", "1", "origin", COMMIT],
                 ["checkout", "--detach", COMMIT]):
        subprocess.run(["git", "-C", str(destination), *args], check=True)
    return {"source": SOURCE, "commit": COMMIT, "directory": str(destination)}


def ingest(source: Path, output: Path, through: str | None = None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("immutable import destination already exists")
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual != COMMIT:
        raise ValueError("source commit differs from the pinned dataset")
    # Verify tracked files, not merely the HEAD name; an edited checkout is not the release.
    if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip():
        raise ValueError("source checkout contains changes")
    licence = (source / "LICENSE").read_text()
    if 'this dataset and associated documentation files' not in licence:
        raise ValueError("expected dataset-specific licence is absent")
    output.mkdir(parents=True)
    db = sqlite3.connect(output / "panel.sqlite")
    db.execute("CREATE TABLE observations (feed TEXT, symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY(feed,symbol,date))")
    if through is not None: date.fromisoformat(through)
    files, bad, duplicates = [], [], []
    excluded_files = 0
    missing_optional = {key: 0 for key in ("open", "high", "low", "volume")}
    counts = {key: 0 for key in FOLDERS}
    import math
    try:
        for feed, folder in FOLDERS.items():
            for file in sorted((source / folder).glob("*.csv")):
                expected_date = date.fromisoformat(file.stem.split("_", 1)[1]).isoformat()
                files.append({"path": str(file.relative_to(source)), "sha256": sha256(file)})
                if through is not None and expected_date > through:
                    excluded_files += 1
                    continue
                with file.open(newline="") as stream:
                    for line, row in enumerate(csv.DictReader(stream), 2):
                        if row["date"] != expected_date:
                            raise ValueError(f"date mismatch: {file.name}:{line}")
                        symbol = row["symbol"].strip()
                        try:
                            values = [None if row[k] == "" and k != "close" else float(row[k]) for k in ("open", "high", "low", "close", "volume")]
                        except (ValueError, TypeError):
                            bad.append({"file": str(file.relative_to(source)), "line": line, "reason": "missing/non-numeric source field", "row": row})
                            continue
                        if not symbol or any(v is not None and not math.isfinite(v) for v in values) or values[3] <= 0 or (values[4] is not None and values[4] < 0):
                            bad.append({"file": str(file.relative_to(source)), "line": line, "reason": "invalid numeric observation", "row": row})
                            continue
                        for key, value in zip(("open", "high", "low", "close", "volume"), values):
                            if value is None: missing_optional[key] += 1
                        try:
                            db.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)", (feed, symbol, expected_date, *values))
                        except sqlite3.IntegrityError as exc:
                            prior = db.execute("SELECT open,high,low,close,volume FROM observations WHERE feed=? AND symbol=? AND date=?", (feed, symbol, expected_date)).fetchone()
                            if list(prior) != values:
                                raise ValueError(f"conflicting duplicate observation: {feed}/{symbol}/{expected_date}") from exc
                            duplicates.append({"file": str(file.relative_to(source)), "line": line, "symbol": symbol})
                            continue
                        counts[feed] += 1
        db.commit()
        rows = db.execute("SELECT feed,symbol,COUNT(*),MIN(date),MAX(date) FROM observations GROUP BY feed,symbol ORDER BY feed,symbol").fetchall()
        with (output / "coverage.csv").open("w", newline="") as stream:
            writer = csv.writer(stream); writer.writerow(["feed", "symbol", "observations", "first_date", "last_date"]); writer.writerows(rows)
        report = {"schema": "zenith_nepse_import_v1", "source_url": SOURCE, "commit": COMMIT,
                  "rows": counts, "symbol_counts": {f: sum(r[0] == f for r in rows) for f in FOLDERS},
                  "through": through, "files_after_import_boundary": excluded_files,
                  "missing_optional_values": missing_optional,
                  "files": len(files), "invalid_rows": len(bad), "identical_duplicates": len(duplicates), "database_sha256": sha256(output/"panel.sqlite"), "licence_sha256": sha256(source / "LICENSE"),
                  "qualifications": ["publisher-adjusted historical snapshot; adjustment vintages unverified",
                                     "historical publication timestamps unknown; retrospective close-date replay only",
                                     "instrument types and historical sector membership not supplied",
                                     "source_volume units for stocks and indices are not assumed equal"]}
        write_json(output / "audit.json", report)
        write_json(output / "file_manifest.json", files)
        write_json(output / "quarantine.json", bad)
        write_json(output / "identical_duplicates.json", duplicates)
        shutil.copyfile(source / "LICENSE", output / "SOURCE_LICENSE.txt")
        (output / "ATTRIBUTION.txt").write_text(f"NEPSE Open Data, Copyright (c) 2025 SocrateAI.\n{SOURCE}\nCommit {COMMIT}\nPublisher-adjusted observations; see SOURCE_LICENSE.txt and audit.json.\n")
        return report
    finally:
        db.close()
