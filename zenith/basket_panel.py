"""Shared, cutoff-bound numerical evidence for the native basket graph."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

from .market_data import sha256
from .providers import digest, write_json

HORIZON = 5
OPERATIONS = ("trend", "breadth", "volume", "lag")


def finite(value):
    return json.loads(json.dumps(value, default=lambda v: v.item() if hasattr(v, "item") else str(v), allow_nan=False))


def ridge(x, y, current, alpha=100.0):
    """Fit scaling and a dual ridge on the supplied training rows only."""
    x, y, current = np.asarray(x), np.asarray(y), np.asarray(current)
    mean = x.mean(axis=0); scale = x.std(axis=0)
    scale = np.where(scale > 1e-8, scale, 1.0)
    z = np.clip((x - mean) / scale, -10, 10)
    q = np.clip((current - mean) / scale, -10, 10)
    ym = y.mean(axis=0)
    # Divide by feature count so the registered penalty has the same meaning for subsets.
    normalizer = max(1, x.shape[1])
    dual = np.linalg.solve(z @ z.T / normalizer + alpha * np.eye(len(z)), y - ym)
    return ym + (q @ z.T / normalizer) @ dual


class Panel:
    def __init__(self, folder, formation="2021-12-30", groups=6):
        self.folder = Path(folder).resolve()
        audit = json.loads((self.folder / "audit.json").read_text())
        if sha256(self.folder / "panel.sqlite") != audit["database_sha256"]:
            raise ValueError("import database hash mismatch")
        with sqlite3.connect(self.folder / "panel.sqlite") as db:
            stock = pd.read_sql_query("SELECT * FROM observations WHERE feed='stock' ORDER BY date,symbol", db)
            index = pd.read_sql_query("SELECT * FROM observations WHERE feed='index' ORDER BY date,symbol", db)
        close = stock.pivot(index="date", columns="symbol", values="close").sort_index()
        market_dates = sorted(set(index.loc[index.symbol == "NEPSE_index", "date"]) & set(close.index))
        if not market_dates: raise ValueError("supplied market-session calendar absent")
        close = close.reindex(market_dates)
        volume = stock.pivot(index="date", columns="symbol", values="volume").reindex(close.index)
        self.dates = close.index.to_numpy(dtype=str)
        self.formation_i = int(np.searchsorted(self.dates, formation, side="right") - 1)
        if self.formation_i < 252:
            raise ValueError("formation needs at least 252 preceding market sessions")
        self.formation = self.dates[self.formation_i]
        history = close.iloc[self.formation_i-251:self.formation_i+1]
        eligible = (history.notna().mean() >= .95) & history.iloc[-1].notna() & (volume.reindex(history.index).median() > 0)
        self.symbols = sorted(history.columns[eligible])
        if len(self.symbols) < groups * 5:
            raise ValueError("insufficient formation-eligible universe")
        raw = close[self.symbols]
        marked = raw.ffill()  # Explicit last-quote index, never a future fill.
        returns = marked.pct_change(fill_method=None)
        past = returns.iloc[self.formation_i-125:self.formation_i+1].fillna(0)
        market = past.mean(axis=1).to_numpy()
        beta = {s: float(np.mean((past[s].to_numpy()-past[s].mean())*(market-market.mean())) / max(np.var(market), 1e-12)) for s in self.symbols}
        ordered = sorted(self.symbols, key=lambda s: (beta[s], s))
        self.groups = {f"B{i+1:02}": list(chunk) for i, chunk in enumerate(np.array_split(ordered, groups))}
        self.basket_ids = list(self.groups)
        base = marked.iloc[self.formation_i]
        self.baskets = pd.DataFrame({b: 100 * (marked[members] / base[members]).mean(axis=1, skipna=False) for b, members in self.groups.items()})
        observed_i = pd.DataFrame(np.where(raw.notna(), np.arange(len(raw))[:, None], np.nan), index=raw.index, columns=raw.columns).ffill()
        self.age = observed_i.rsub(np.arange(len(raw)), axis=0)
        self.raw = raw
        self.marked = marked
        features = {}
        symbol_groups = {s: b for b, members in self.groups.items() for s in members}
        self.feature_info = []
        def add(name, series, group, op):
            features[name] = series.replace([np.inf, -np.inf], np.nan).fillna(0)
            self.feature_info.append({"name": name, "group": group, "op": op})
        for s in self.symbols:
            b = symbol_groups[s]
            for lag in (1, 5, 20): add(f"{s}:return{lag}", marked[s].pct_change(lag, fill_method=None), b, "trend")
            add(f"{s}:volatility20", returns[s].rolling(20, min_periods=10).std(), b, "breadth")
            v = volume[s].fillna(0)
            add(f"{s}:relative_volume", v / v.rolling(20, min_periods=10).mean() - 1, b, "volume")
            add(f"{s}:quote_age", self.age[s], b, "breadth")
        for b, members in self.groups.items():
            for lag in (1, 5, 20): add(f"{b}:return{lag}", self.baskets[b].pct_change(lag, fill_method=None), b, "trend")
            r = marked[members].pct_change(5, fill_method=None)
            add(f"{b}:breadth5", (r > 0).mean(axis=1), b, "breadth")
            add(f"{b}:dispersion5", r.std(axis=1), b, "breadth")
        indices = index.pivot(index="date", columns="symbol", values="close").reindex(close.index)
        self.indices = sorted(s for s in indices if indices[s].iloc[:self.formation_i+1].notna().sum() >= 126)
        for s in self.indices:
            series = indices[s].ffill()
            for lag in (1, 5, 20): add(f"{s}:return{lag}", series.pct_change(lag, fill_method=None), "INDEX", "trend")
        self.x = pd.DataFrame(features).to_numpy(dtype=float)
        # Labels remain in evaluator memory. A snapshot exports only matured labels.
        self.y = (self.baskets.shift(-HORIZON) / self.baskets - 1).to_numpy()
        self.manifest = {"schema": "zenith_research_baskets_v1", "source_commit": json.loads((self.folder/"audit.json").read_text())["commit"],
                         "formation_date": str(self.formation), "groups": self.groups, "index_inputs": self.indices,
                         "formation_rule": "252-session coverage >= 95%; quote at formation; positive median source volume; six balanced groups ranked by past 126-session beta to the equal-weight universe",
                         "weighting": "equal initial value at formation, fixed shares thereafter",
                         "target": "five market-session return of last-observed-quote research index",
                         "missing_rule": "carry last observed quote forward; record age and stale fraction; no zero-valued price, future fill, constituent deletion or future-survival screen",
                         "qualifications": ["research groups, not historical sectors or traded ETFs", "may contain non-equity instrument types; source has no authoritative classification", "publisher-adjusted retrospective snapshot, not certified point-in-time data", "stale marks are not executable prices or realised liquidation values"]}
        self.manifest["sha256"] = digest(self.manifest)

    def cutoff_index(self, cutoff):
        matches = np.flatnonzero(self.dates == cutoff)
        if len(matches) != 1 or matches[0] <= self.formation_i:
            raise ValueError("cutoff must be a market session after formation")
        return int(matches[0])

    def snapshot(self, cutoff, destination, mode="directed"):
        i = self.cutoff_index(cutoff)
        destination = Path(destination).resolve()
        if destination.exists(): raise ValueError("snapshot already exists")
        destination.mkdir(parents=True)
        # Up to 252 mature training origins and the current feature vector; no unresolved label.
        origins = np.arange(max(252, i-HORIZON-251), i-HORIZON+1)
        valid = np.isfinite(self.y[origins]).all(axis=1)
        origins = origins[valid]
        if len(origins) < 160: raise ValueError("insufficient mature training origins")
        xx, yy = self.x[origins], self.y[origins]
        base = ridge(xx, yy, self.x[i])
        # The gap ensures training labels mature before each validation origin.
        val_positions = np.arange(len(origins)-40, len(origins), HORIZON)
        val_base = []
        for k in val_positions:
            train = origins + HORIZON <= origins[k]
            val_base.append(ridge(xx[train], yy[train], xx[k]))
        np.savez_compressed(destination / "history.npz", x=xx, y=yy, current=self.x[i], origins=origins,
                            dates=self.dates[origins], label_end_dates=self.dates[origins+HORIZON],
                            val_positions=val_positions, val_baseline=np.asarray(val_base))
        stock_rows = []
        columns = {d["name"]: j for j, d in enumerate(self.feature_info)}
        for b, members in self.groups.items():
            for s in members:
                stock_rows.append({"symbol": s, "basket": b,
                                   **{k: round(float(self.x[i, columns[s+":"+k]]), 6) for k in ("return1", "return5", "return20", "volatility20", "relative_volume", "quote_age")}})
        overview = {"cutoff": cutoff, "horizon_sessions": HORIZON, "universe_sha256": self.manifest["sha256"],
                    "basket_ids": self.basket_ids, "groups": self.groups, "index_inputs": self.indices,
                    "constituent_count": len(self.symbols), "feature_count": self.x.shape[1],
                    "training_origins": len(origins), "baseline": dict(zip(self.basket_ids, base.tolist())),
                    "stock_observations": stock_rows,
                    "basket_observations": {b: {"value": float(self.baskets.iloc[i][b]), "return5": float(self.baskets[b].iloc[i]/self.baskets[b].iloc[i-5]-1), "stale_fraction": float((self.age.iloc[i][self.groups[b]] > 0).mean())} for b in self.basket_ids},
                    "query_contract": {"operations": list(OPERATIONS), "sources": self.basket_ids+["INDEX", "ALL"], "lags": [0, 1, 5, 20], "maximum_queries": 6,
                                       "index_operations": ["trend", "lag"],
                                       "output": "queries: [{target: basket ID, source: basket ID or INDEX or ALL, operation: trend|breadth|volume|lag, lag: 0|1|5|20, reason: brief question}]"}}
        # Lagged feature windows, still bounded by the very same cutoff.
        np.savez_compressed(destination / "features.npz", x=self.x[:i+1])
        payload = {"cutoff": cutoff, "mode": mode, "overview": overview, "feature_info": self.feature_info,
                   "store": str(destination / "history.npz"), "store_sha256": sha256(destination / "history.npz"),
                   "features": str(destination / "features.npz"), "features_sha256": sha256(destination / "features.npz")}
        write_json(destination / "artifacts/basket_panel_feed.json", {"status": "success", "metadata": {"as_of": cutoff+"T23:59:59+00:00"}, "data": finite(payload)})
        write_json(destination / "runtime_context.json", {"as_of": cutoff+"T23:59:59+00:00"})
        write_json(destination / "basket_manifest.json", self.manifest)
        return overview

    def outcome(self, cutoff):
        i = self.cutoff_index(cutoff)
        if i + HORIZON >= len(self.dates): raise ValueError("unmatured horizon")
        values = self.y[i]
        if not np.isfinite(values).all(): raise ValueError("unresolved basket outcome")
        return {"cutoff": cutoff, "target_date": str(self.dates[i+HORIZON]), "returns": dict(zip(self.basket_ids, values.tolist())),
                "stale_fraction": {b: float((self.age.iloc[i+HORIZON][m] > 0).mean()) for b, m in self.groups.items()}}


def investigate(payload, queries):
    if not isinstance(queries, list) or len(queries) > 6: raise ValueError("query budget exceeded")
    for name in ("store", "features"):
        if sha256(payload[name]) != payload[name+"_sha256"]: raise ValueError("cutoff store hash mismatch")
    history = np.load(payload["store"], allow_pickle=False)
    features = np.load(payload["features"], allow_pickle=False)["x"]
    if max(history["label_end_dates"]) > payload["cutoff"]: raise ValueError("future training label")
    b_ids = payload["overview"]["basket_ids"]
    outputs = []
    for q in queries:
        if not isinstance(q, dict) or set(q) - {"target", "source", "operation", "lag", "reason"}: raise ValueError("unknown query fields")
        if q.get("target") not in b_ids or q.get("source") not in b_ids + ["ALL", "INDEX"] or q.get("operation") not in OPERATIONS or type(q.get("lag")) is not int or q["lag"] not in [0,1,5,20]: raise ValueError("invalid bounded query")
        cols = [i for i, d in enumerate(payload["feature_info"]) if (q["source"] == "ALL" or d["group"] == q["source"]) and (q["operation"] == "lag" or d["op"] == q["operation"])]
        if not cols: raise ValueError("query has no matching features")
        target = b_ids.index(q["target"])
        x = features[history["origins"]-q["lag"]][:, cols]
        y = history["y"][:, target]
        pred = float(ridge(x, y, features[-1-q["lag"], cols]))
        gains = []
        for n, k in enumerate(history["val_positions"]):
            train = history["origins"] + HORIZON <= history["origins"][k]
            candidate = float(ridge(x[train], y[train], x[k]))
            original = history["val_baseline"][n, target]
            gains.append(float((y[k]-original)**2 - (y[k]-candidate)**2))
        outputs.append({"candidate_id": f"Q{len(outputs)+1}", "query": q, "prediction": pred, "validation_gain": float(np.mean(gains)),
                        "validation_cases": len(gains), "validation_last_label_date": str(max(history["label_end_dates"])),
                        "feature_count": len(cols), "data_sha256": payload["store_sha256"], "cutoff": payload["cutoff"]})
    return outputs
