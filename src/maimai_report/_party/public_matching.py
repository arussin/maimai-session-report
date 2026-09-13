"""Public comparison API v1; structural retrieval, never a skill prediction.

Standalone so downstream consumers can pin this small MIT module without taking
the analyzer, source corpus, browser application or private recommendation engine.
"""

from bisect import bisect_left, bisect_right
from collections import Counter
from math import floor, isfinite

API_VERSION = 1
GROUPS = ("cadence", "rhythm", "coordination", "holds", "slides", "spatial")


def tags(profile, analysis):
    record = (analysis or {}).get("charts", {}).get(profile["chart_id"])
    if not record or record.get("source_hash") != profile.get("source_hash"):
        return {}
    if analysis.get("version") not in {"research-overview-1", "research-overview-2"}:
        return {}
    representation = analysis.get("representation", "")
    result = {}
    for row in record.get("tags", []):
        idx, status, count, prevalence, *rest = row
        if representation in {"sparse-tags-2", "sparse-tags-3"}:
            complete = bool(status & 4)
            status = ("unknown", "detected", "not-detected-with-supported-coverage")[status & 3]
        else:
            complete = bool(rest and rest[0] == "complete")
        result[analysis["patterns"][idx]] = {
            "status": status,
            "count": count,
            "prevalence": prevalence,
            "complete": complete,
        }
    for idx in record.get("absent", []):
        result.setdefault(
            analysis["patterns"][idx],
            {
                "status": "not-detected-with-supported-coverage",
                "count": 0,
                "prevalence": 0,
                "complete": True,
            },
        )
    return result


class ComparisonIndex:
    def __init__(self, profiles, analysis=None):
        self.profiles = {}
        scale = {}
        for c in profiles:
            if (
                c.get("version") != "challenge-profile-1-experimental"
                or c["chart_id"] in self.profiles
            ):
                raise ValueError("Incompatible comparison profile")
            self.profiles[c["chart_id"]] = c
            for group in GROUPS:
                for key, value in c.get("demand", {}).get(group, {}).items():
                    if type(value) not in (int, float) or not isfinite(value):
                        raise ValueError("Invalid comparison measurement")
                    scale.setdefault((group, key), []).append(value)
        for values in scale.values():
            values.sort()
        self.vectors = {}
        for cid, c in self.profiles.items():
            vector = {}
            for group in GROUPS:
                vector[group] = {}
                for key, value in c.get("demand", {}).get(group, {}).items():
                    values = scale[group, key]
                    vector[group][key] = (
                        bisect_left(values, value) + bisect_right(values, value)
                    ) / (2 * len(values))
            self.vectors[cid] = vector
        self.analysis = analysis or {}
        self.tags = {cid: tags(c, self.analysis) for cid, c in self.profiles.items()}
        self.frequency = Counter(
            key
            for rows in self.tags.values()
            for key, row in rows.items()
            if row["status"] == "detected"
        )

    def compare(self, left, right):
        a, b = self.vectors[left], self.vectors[right]
        differences = {}
        for group in GROUPS:
            keys = sorted(a[group].keys() & b[group].keys())
            if keys:
                differences[group] = sum(abs(a[group][k] - b[group][k]) for k in keys) / len(keys)
        if len(differences) < 4:
            return None
        distance = floor(sum(differences.values()) / len(differences) * 1e6 + 0.5) / 1e6
        return {
            "distance": distance,
            "closest_groups": sorted(differences, key=lambda g: (differences[g], g))[:2],
            "largest_difference": max(differences, key=lambda g: (differences[g], g)),
        }

    def pattern_compare(self, left, right):
        a, b = self.tags[left], self.tags[right]
        shared, first, second, unknown = [], [], [], []
        difference = union = known = 0

        def rate(cid, row):
            span = self.analysis.get("charts", {}).get(cid, {}).get("span")
            return (
                row["count"] * 60e6 / (span[1] - span[0])
                if span and span[1] > span[0] and row["count"] is not None
                else 0
            )

        for key in self.analysis.get("patterns", []):
            x, y = a.get(key), b.get(key)
            xd, yd = bool(x and x["status"] == "detected"), bool(y and y["status"] == "detected")
            if xd and yd:
                shared.append(key)
            elif xd or yd:
                other = y if xd else x
                if other and other["status"] == "not-detected-with-supported-coverage":
                    (first if xd else second).append(key)
                else:
                    unknown.append(key)
            if (
                x
                and y
                and x["status"] != "unknown"
                and y["status"] != "unknown"
                and x["complete"]
                and y["complete"]
            ):
                known += 1
                if xd or yd:
                    weight = 1 / max(1, self.frequency[key])
                    rx, ry = (
                        (int(xd), int(yd))
                        if key.startswith("trait.")
                        else (rate(left, x), rate(right, y))
                    )
                    relative = abs(rx - ry) / (rx + ry) if rx + ry else 0
                    union += weight
                    difference += weight * (
                        0.5 * (xd != yd)
                        + 0.3 * relative
                        + 0.2 * abs((x["prevalence"] or 0) - (y["prevalence"] or 0))
                    )
        return {
            "shared": shared,
            "first": first,
            "second": second,
            "unknown": unknown,
            "coverage": known,
            "patternDistance": difference / union if union and known >= 4 else None,
        }

    def similar(self, chart_id, *, limit=8, eligible_ids=None, patterns=True):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Result limit must be 1..100")
        query = self.profiles[chart_id]
        family = query.get("song_family", query.get("song_id"))
        allowed = None if eligible_ids is None else set(eligible_ids)
        rows = []
        for cid, candidate in self.profiles.items():
            if (
                cid == chart_id
                or candidate.get("song_family", candidate.get("song_id")) == family
                or (allowed is not None and cid not in allowed)
            ):
                continue
            result = self.compare(chart_id, cid)
            if result is None:
                continue
            row = {"chart_id": cid, **result}
            if patterns:
                p = self.pattern_compare(chart_id, cid)
                d = p["patternDistance"]
                row.update(
                    patterns=p,
                    patternDistance=d,
                    rankDistance=result["distance"]
                    if d is None
                    else 0.6 * d + 0.4 * result["distance"],
                )
            rows.append(row)
        rows.sort(
            key=lambda r: (
                (r["patternDistance"] is None, r["rankDistance"], r["chart_id"])
                if patterns
                else (r["distance"], r["chart_id"])
            )
        )
        result, seen = [], set()
        for row in rows:
            c = self.profiles[row["chart_id"]]
            family = c.get("song_family", c.get("song_id"))
            if family not in seen:
                seen.add(family)
                result.append(row)
                if len(result) == limit:
                    break
        return result
