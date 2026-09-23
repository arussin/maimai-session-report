"""Report-owned target selection using the upstream public comparison API."""

from collections.abc import Mapping, Sequence
from typing import Any

from ._party.player_data import current, number
from ._party.public_matching import ComparisonIndex

POLICY = "kamaitachi-maimaidx-f08148f-v1"
COEFFICIENTS = (
    (1005000, 224),
    (1004999, 222),
    (1000000, 216),
    (999999, 214),
    (995000, 211),
    (990000, 208),
    (989999, 206),
    (980000, 203),
    (970000, 200),
    (969999, 176),
    (940000, 168),
    (900000, 152),
    (800000, 136),
    (799999, 128),
    (750000, 120),
    (700000, 112),
    (600000, 96),
    (500000, 80),
    (400000, 64),
    (300000, 48),
    (200000, 32),
    (100000, 16),
    (0, 0),
)
BOUNDARIES = (
    (970000, "S"),
    (980000, "S+"),
    (990000, "SS"),
    (995000, "SS+"),
    (1000000, "SSS"),
    (1005000, "SSS+"),
)


def rating(achievement, constant, lamp=""):
    if (
        type(achievement) is not int
        or type(constant) is not int
        or not 0 <= achievement <= 1010000
        or constant < 0
    ):
        return None
    if (
        lamp == "ALL PERFECT+"
        and achievement != 1010000
        or achievement == 1010000
        and lamp
        and lamp != "ALL PERFECT+"
        or lamp == "ALL PERFECT"
        and achievement < 1000000
        or lamp == "FAILED"
        and achievement >= 800000
        or lamp == "CLEAR"
        and achievement < 800000
    ):
        return None
    score = min(achievement, 1005000)
    coefficient = next(c for minimum, c in COEFFICIENTS if score >= minimum)
    return score * coefficient * constant // 100000000 + int(
        lamp in {"ALL PERFECT", "ALL PERFECT+"}
    )


def prepare(
    data: Mapping[str, Any],
    catalog: Mapping[str, Any] | None = None,
    session_scores: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    pbs, snapshot = current(data)
    mappings = catalog.get("provider_mapping", {}).get("charts", {}) if catalog else {}
    # A provider ID migration must not count the same chart twice in a pool.
    # Keep all source records in the portable dataset; select only for analysis.
    dates = {}
    for snap in data["snapshots"].values():
        for cid in snap["pbs"]:
            dates[cid] = max(dates.get(cid, 0), snap["capturedAt"])
    resolved = {}
    for cid in pbs:
        ref = mappings.get(cid, {})
        key = ref.get("chart_id", "provider:" + cid)
        rank = (dates.get(cid, 0), not bool(ref.get("aliasOf")), cid)
        if key not in resolved or rank > resolved[key][0]:
            resolved[key] = (rank, cid)
    pbs = {cid: pbs[cid] for _, cid in resolved.values()}
    versions = snapshot["versions"] if snapshot else []
    compatible = bool(snapshot and snapshot["complete"] and versions) and all(
        r["displayVersion"]
        and r["rate"] is not None
        and r["rate"] == rating(r["achievement"], r["constant"], r["lamp"])
        for r in pbs.values()
    )
    profiles = {c["chart_id"]: c for c in catalog["catalog"]} if catalog else {}
    matcher = ComparisonIndex(list(profiles.values()), catalog.get("analysis")) if catalog else None
    public_pbs = {mappings[cid]["chart_id"]: r for cid, r in pbs.items() if cid in mappings}
    pools = {
        kind: sorted(
            (
                r["rate"]
                for r in pbs.values()
                if r["rate"] is not None and (r["displayVersion"] in versions) == (kind == "new")
            ),
            reverse=True,
        )
        for kind in ("old", "new")
    }
    floors = {
        kind: rows[slots - 1] if len(rows) >= slots else 0
        for kind, slots in (("old", 35), ("new", 15))
        for rows in [pools[kind]]
    }

    def gain(record, achievement):
        if not compatible or not record.get("displayVersion") or record.get("constant") is None:
            return None
        kind = "new" if record["displayVersion"] in versions else "old"
        projected = rating(achievement, record["constant"], record.get("lamp", ""))
        return (
            None
            if projected is None
            else max(0, projected - max(record.get("rate") or 0, floors[kind]))
        )

    def chart(cid):
        c = data["charts"].get(cid, {})
        r = pbs.get(cid, {})
        return {
            "chartID": cid,
            "songID": c.get("songID", ""),
            "title": c.get("title", ""),
            "artist": c.get("artist", ""),
            "difficulty": ("DX " if c.get("format") == "DX" else "") + c.get("difficulty", ""),
            "format": c.get("format"),
            "level": c.get("level", ""),
            "levelNum": (r.get("constant") or c.get("constant") or 0) / 10,
            "percent": r["achievement"] / 10000 if r.get("achievement") is not None else None,
            "grade": r.get("grade", ""),
            "rate": r.get("rate"),
            "lamp": r.get("lamp", ""),
        }

    # The selected session is preferred. PB-only reports use retained attempts,
    # then dated PBs. None of these sources imply calibrated reachability.
    anchor_rows = [
        (number(s.get("timeAchieved")) or 0, s.get("chartID"), achievement)
        for s in session_scores
        for achievement in [number(s.get("percent"), 10000)]
        if achievement is not None and 970000 <= achievement <= 1010000
    ]
    if not anchor_rows:
        anchor_rows = [
            (r["timeAchieved"] or 0, r["chartID"], r["achievement"])
            for ref in data["plays"].values()
            for r in [data["records"][ref]]
            if r["achievement"] is not None and r["achievement"] >= 970000
        ]
    if not anchor_rows:
        anchor_rows = [
            (r["timeAchieved"], cid, r["achievement"])
            for cid, r in pbs.items()
            if r["timeAchieved"] is not None
            and r["achievement"] is not None
            and r["achievement"] >= 970000
        ]
    anchors, families = [], set()
    for _, cid, achievement in sorted(anchor_rows, key=lambda r: (-r[0], str(r[1]))):
        ref = mappings.get(cid)
        if not ref:
            continue
        c = profiles[ref["chart_id"]]
        family = c.get("song_family", c.get("song_id"))
        if family not in families:
            anchors.append((cid, ref, c, achievement))
            families.add(family)
        if len(anchors) == 3:
            break

    def similarity(cid):
        if not matcher or cid not in mappings or not anchors:
            return 2.0
        scores = []
        for _, ref, _, _ in anchors:
            other = mappings[cid]["chart_id"]
            result = matcher.compare(ref["chart_id"], other)
            if result:
                p = matcher.pattern_compare(ref["chart_id"], other)["patternDistance"]
                scores.append(
                    result["distance"] if p is None else 0.6 * p + 0.4 * result["distance"]
                )
        return min(scores, default=2.0)

    opportunities = []
    if compatible:
        for cid, r in pbs.items():
            target = next(
                (
                    (n, g)
                    for n, g in BOUNDARIES
                    if r["achievement"] is not None and n > r["achievement"]
                ),
                None,
            )
            if target is None or target[0] - r["achievement"] > 25000:
                continue
            upside = gain(r, target[0])
            if upside:
                opportunities.append(
                    {
                        "chart": chart(cid),
                        "targetPercent": target[0] / 10000,
                        "targetGrade": target[1],
                        "gain": upside,
                        "gap": (target[0] - r["achievement"]) / 10000,
                        "similarity": similarity(cid),
                        "pool": "New 15" if r["displayVersion"] in versions else "Old 35",
                    }
                )
    opportunities.sort(
        key=lambda row: (-row["gain"], row["similarity"], row["gap"], row["chart"]["chartID"])
    )
    selected, seen = [], set()
    for row in opportunities:
        cid = row["chart"]["chartID"]
        public = mappings.get(cid, {}).get("chart_id")
        c = profiles.get(public, {})
        family = c.get("song_family", c.get("song_id", row["chart"]["songID"]))
        if family not in seen:
            seen.add(family)
            selected.append(row)
        if len(selected) == 2:
            break
    practice = []
    if matcher:
        release_keys = {"".join(ch for ch in v.lower() if ch.isalnum()) for v in versions}
        candidates = {
            ref["chart_id"]: (cid, ref) for cid, ref in mappings.items() if not ref.get("aliasOf")
        }
        for anchor_cid, anchor_ref, _anchor_profile, achievement in anchors:
            constant = anchor_ref.get("constant")
            if not isinstance(constant, (int, float)):
                continue
            target = max(n for n, _ in BOUNDARIES if n <= achievement)
            eligible = {
                pid
                for pid, (_, ref) in candidates.items()
                if release_keys.intersection(ref.get("versions", []))
                and isinstance(ref.get("constant"), (int, float))
                and 1 <= round(ref["constant"] * 10) - round(constant * 10) <= 5
                and (pid not in public_pbs or (public_pbs[pid]["achievement"] or 0) < target)
            }
            for match in matcher.similar(anchor_ref["chart_id"], limit=100, eligible_ids=eligible):
                pid = match["chart_id"]
                cid, ref = candidates[pid]
                c = profiles[pid]
                if c.get("song_family", c.get("song_id")) in seen:
                    continue
                existing = public_pbs.get(pid, {})
                estimate = gain(
                    {
                        **existing,
                        "constant": round(ref["constant"] * 10),
                        "displayVersion": ref.get("displayVersion", ""),
                    },
                    target,
                )
                target_chart = {
                    "chartID": cid,
                    "songID": ref["songID"],
                    "title": ref["title"],
                    "artist": ref["artist"],
                    "difficulty": ("DX " if ref["format"] == "DX" else "") + ref["difficulty"],
                    "level": ref["level"],
                    "levelNum": ref["constant"],
                    "percent": existing["achievement"] / 10000
                    if existing.get("achievement") is not None
                    else None,
                    "rate": existing.get("rate"),
                }
                practice.append(
                    {
                        "chart": target_chart,
                        "anchor": chart(anchor_cid),
                        "targetPercent": target / 10000,
                        "gain": estimate,
                        "step": round(ref["constant"] * 10) - round(constant * 10),
                        "match": match,
                    }
                )
    practice.sort(
        key=lambda row: (
            not bool(row["gain"]),
            row["match"].get("patternDistance") is None,
            row["match"].get("rankDistance", row["match"]["distance"]),
            row["step"],
            row["chart"]["chartID"],
        )
    )
    return {
        "version": 1,
        "policy": POLICY,
        "ratingCompatible": compatible,
        "rating": selected,
        "practice": practice[0] if practice else None,
        "floors": floors
        if snapshot
        and snapshot["complete"]
        and versions
        and all(r["rate"] is not None for r in pbs.values())
        else {"old": None, "new": None},
    }
