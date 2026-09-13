"""Portable player data v1. Standard library only; no report-generator dependency.

Achievements use integer 0.0001% ticks, constants use integer tenths, and dates
use UTC milliseconds. Content-addressed observations are shared by snapshots and
actual plays; a PB observation never implies a play took place at capture time.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path

FORMAT = "maimai-player-data"
VERSION = 1
MAX_COMPRESSED = 32 * 1024 * 1024
MAX_DECODED = 128 * 1024 * 1024
MAX_RECORDS = 1_000_000
HEX = re.compile(r"[a-f0-9]{64}\Z")
RECORD_FIELDS = {
    "chartID",
    "achievement",
    "grade",
    "rate",
    "lamp",
    "sync",
    "constant",
    "displayVersion",
    "timeAchieved",
    "dxScore",
    "maxDxScore",
    "maxCombo",
    "fast",
    "slow",
    "miss",
    "good",
    "great",
    "perfect",
    "pcrit",
}
CHART_FIELDS = {
    "chartID",
    "songID",
    "title",
    "artist",
    "format",
    "difficulty",
    "level",
    "constant",
    "displayVersion",
    "inGameID",
}


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(value, maximum=512, empty=False):
    if (
        not isinstance(value, str)
        or len(value.encode("utf-16-le", errors="surrogatepass")) // 2 > maximum
        or (not empty and not value)
    ):
        raise ValueError("Invalid player-data text")
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError("Control characters are not allowed in player data")
    return value


def _integer(value, maximum=2**53 - 1, nullable=False):
    if value is None and nullable:
        return
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Invalid player-data integer")


def validate(data, *, check_revision=True):
    if (
        not isinstance(data, dict)
        or set(data)
        != {
            "format",
            "schemaVersion",
            "revision",
            "player",
            "charts",
            "records",
            "plays",
            "snapshots",
            "captures",
        }
        or data["format"] != FORMAT
        or type(data["schemaVersion"]) is not int
        or data["schemaVersion"] != VERSION
    ):
        raise ValueError("Unsupported player file; expected maimai-player-data v1")
    player = data["player"]
    if not isinstance(player, dict) or set(player) != {
        "key",
        "provider",
        "game",
        "username",
        "displayName",
    }:
        raise ValueError("Invalid player identity")
    for value in player.values():
        _text(value, 200)
    if player["provider"] != "kamaitachi" or player["game"] != "maimaidx":
        raise ValueError("Unsupported player source")
    expected = "kamaitachi:maimaidx:" + player["username"].lower()
    if player["key"] != expected:
        raise ValueError("Player identity disagrees with source")
    for name in ("charts", "records", "plays", "snapshots", "captures"):
        rows = data[name]
        if not isinstance(rows, dict) or len(rows) > MAX_RECORDS:
            raise ValueError("Invalid or oversized player collection")
        for key in rows:
            _text(key, 256)
            if key in {"__proto__", "constructor", "prototype"}:
                raise ValueError("Reserved player-data identity")
    for key, c in data["charts"].items():
        if not isinstance(c, dict) or set(c) != CHART_FIELDS or c["chartID"] != key:
            raise ValueError("Invalid chart reference")
        for name in ("chartID", "songID", "format", "difficulty"):
            _text(c[name], 256)
        for name in ("title", "artist", "level", "displayVersion"):
            _text(c[name], 512, empty=True)
        if c["format"] not in {"STD", "DX"}:
            raise ValueError("Invalid chart format")
        _integer(c["constant"], 200, nullable=True)
        _integer(c["inGameID"], nullable=True)
    for key, record in data["records"].items():
        if not HEX.fullmatch(key) or not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            raise ValueError("Invalid observation")
        if not isinstance(record["chartID"], str) or record["chartID"] not in data["charts"]:
            raise ValueError("Observation chart missing")
        _integer(record["achievement"], 1_010_000, nullable=True)
        _integer(record["constant"], 200, nullable=True)
        for field in ("grade", "lamp", "sync", "displayVersion"):
            _text(record[field], 512, empty=True)
        for field in RECORD_FIELDS - {
            "chartID",
            "achievement",
            "constant",
            "grade",
            "lamp",
            "sync",
            "displayVersion",
        }:
            _integer(record[field], nullable=True)
        if digest(record) != key:
            raise ValueError("Observation integrity mismatch")
    for ref in data["plays"].values():
        if not isinstance(ref, str) or ref not in data["records"]:
            raise ValueError("Play observation missing")
    for key, snap in data["snapshots"].items():
        if not isinstance(snap, dict) or set(snap) != {
            "capturedAt",
            "phase",
            "complete",
            "versions",
            "pbs",
        }:
            raise ValueError("Invalid PB snapshot")
        _integer(snap["capturedAt"])
        if not isinstance(snap["phase"], str) or snap["phase"] not in {"before", "after"}:
            raise ValueError("Invalid snapshot phase")
        if type(snap["complete"]) is not bool or not isinstance(snap["versions"], list):
            raise ValueError("Invalid snapshot coverage")
        for value in snap["versions"]:
            _text(value)
        if not isinstance(snap["pbs"], dict):
            raise ValueError("Invalid PB collection")
        for cid, ref in snap["pbs"].items():
            if (
                not isinstance(ref, str)
                or ref not in data["records"]
                or data["records"][ref]["chartID"] != cid
            ):
                raise ValueError("PB chart mismatch")
        if digest(snap) != key:
            raise ValueError("Snapshot integrity mismatch")
    for key, capture in data["captures"].items():
        if not isinstance(capture, dict) or set(capture) != {
            "capturedAt",
            "sourceKind",
            "sourceID",
            "sessionID",
            "historyCoverage",
            "playIDs",
            "snapshotIDs",
        }:
            raise ValueError("Invalid capture")
        _integer(capture["capturedAt"])
        for name in ("sourceKind", "sourceID", "sessionID", "historyCoverage"):
            _text(capture[name], empty=True)
        for name, collection in (("playIDs", "plays"), ("snapshotIDs", "snapshots")):
            if (
                not isinstance(capture[name], list)
                or not all(isinstance(ref, str) for ref in capture[name])
                or len(capture[name]) != len(set(capture[name]))
            ):
                raise ValueError("Invalid capture references")
            if any(ref not in data[collection] for ref in capture[name]):
                raise ValueError("Capture observation missing")
        if digest(capture) != key:
            raise ValueError("Capture integrity mismatch")
    if not isinstance(data["revision"], str) or not HEX.fullmatch(data["revision"]):
        raise ValueError("Invalid dataset revision")
    if (
        check_revision
        and digest({k: v for k, v in data.items() if k != "revision"}) != data["revision"]
    ):
        raise ValueError("Player file integrity mismatch")
    return data


def seal(data):
    data["revision"] = digest({k: v for k, v in data.items() if k != "revision"})
    return validate(data)


def empty(player):
    return seal(
        {
            "format": FORMAT,
            "schemaVersion": VERSION,
            "player": player,
            **{name: {} for name in ("charts", "records", "plays", "snapshots", "captures")},
        }
    )


def current(data):
    """Latest complete snapshot plus newer partial observations, never max-ever PBs."""
    pbs, newest = {}, None
    for _, snap in sorted(
        data["snapshots"].items(),
        key=lambda item: (item[1]["capturedAt"], item[1]["phase"] == "after", item[0]),
    ):
        if snap["complete"]:
            pbs = {}
        pbs.update(snap["pbs"])
        newest = snap
    return {cid: data["records"][ref] for cid, ref in pbs.items()}, newest


def offer(data):
    pbs, snap = current(data)
    return {
        "format": FORMAT,
        "schemaVersion": VERSION,
        "revision": data["revision"],
        "player": data["player"],
        "capturedAt": snap["capturedAt"] if snap else 0,
        "pbCount": len(pbs),
        "pbCoverage": "complete" if snap and snap["complete"] else "partial",
        "playCount": len(data["plays"]),
        "snapshotIDs": sorted(data["snapshots"]),
        "captureIDs": sorted(data["captures"]),
        "historyCoverage": "retained-only",
    }


def observation_dates(data):
    dates = {"charts": {}, "plays": {}}
    for capture in data["captures"].values():
        for pid in capture["playIDs"]:
            dates["plays"][pid] = max(dates["plays"].get(pid, 0), capture["capturedAt"])
    for pid, when in dates["plays"].items():
        cid = data["records"][data["plays"][pid]]["chartID"]
        dates["charts"][cid] = max(dates["charts"].get(cid, 0), when)
    for snap in data["snapshots"].values():
        for cid in snap["pbs"]:
            dates["charts"][cid] = max(dates["charts"].get(cid, 0), snap["capturedAt"])
    return dates


def merge(*datasets):
    if not datasets:
        raise ValueError("No player data supplied")
    result = deepcopy(validate(datasets[0]))
    for dataset in datasets[1:]:
        validate(dataset)
        if result["player"]["key"] != dataset["player"]["key"]:
            raise ValueError("Cannot merge different players")
        left_time = max((s["capturedAt"] for s in result["snapshots"].values()), default=0)
        right_time = max((s["capturedAt"] for s in dataset["snapshots"].values()), default=0)
        left_dates, right_dates = observation_dates(result), observation_dates(dataset)
        if (right_time, canonical(dataset["player"])) >= (left_time, canonical(result["player"])):
            result["player"] = deepcopy(dataset["player"])
        for name in ("records", "snapshots", "captures"):
            for key, value in dataset[name].items():
                if key in result[name] and result[name][key] != value:
                    raise ValueError("Conflicting retained observation")
                result[name][key] = deepcopy(value)
        # Provider corrections may revise a play; latest observation wins. Equal
        # capture dates use content order so merging is deterministic.
        for name in ("charts", "plays"):
            for key, value in dataset[name].items():
                old = result[name].get(key)
                if old is None or (right_dates[name].get(key, 0), canonical(value)) >= (
                    left_dates[name].get(key, 0),
                    canonical(old),
                ):
                    result[name][key] = deepcopy(value)
    return seal(result)


def encode(data):
    raw = canonical(validate(data))
    if len(raw) > MAX_DECODED:
        raise ValueError("Player history exceeds 128 MiB; no history was omitted")
    packed = gzip.compress(raw, mtime=0)
    if len(packed) > MAX_COMPRESSED:
        raise ValueError("Player file exceeds 32 MiB; no history was omitted")
    return packed


def decode(raw):
    if len(raw) > MAX_COMPRESSED:
        raise ValueError("Player file exceeds 32 MiB")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            decoded = stream.read(MAX_DECODED + 1)
        if len(decoded) > MAX_DECODED:
            raise ValueError("Expanded player file exceeds 128 MiB")
        return validate(json.loads(decoded))
    except (OSError, EOFError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid compressed player file") from exc


def read(path):
    with Path(path).open("rb") as stream:
        return decode(stream.read(MAX_COMPRESSED + 1))


def write(path, data):
    """Atomic replacement; caller holds a lock if performing read/merge/write."""
    raw = encode(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".player-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def number(value, scale=1):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return int(round(value * scale))
