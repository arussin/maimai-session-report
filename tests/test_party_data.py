"""History retention, boundary policy and materialization failure acceptance."""

import base64
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from maimai_report._party import player_data as core
from maimai_report.fixtures import load_scenario
from maimai_report.history.bundle import ArchiveError
from maimai_report.history.player import latest, materialize, publish
from maimai_report.history.storage import archive
from maimai_report.party import from_documents, from_path, prepare
from maimai_report.party_recommendations import prepare as recommendations
from maimai_report.party_recommendations import rating
from maimai_report.render import build_html, enrich_report
from tests.test_history import MemoryObjects, SQLite, prepared, source_fixture


def dataset(*, when=None, player=None):
    report, pbs = load_scenario("complete")
    report = enrich_report(report, pbs)
    for index, row in enumerate(report["session"]["scores"]):
        row["scoreID"] = f"synthetic-source-play-{index}"
    if when:
        report["generatedAt"] = when
    return from_documents(report, pbs, player=player)


class PlayerDataTests(unittest.TestCase):
    def test_profile_uses_recorded_pool_rating_and_distinct_source_sessions(self):
        report, payload = load_scenario("complete")
        report["capture"] = {"kind": "session", "sessionID": "retained-session"}
        first = from_documents(report, payload)
        report["generatedAt"] = "2026-09-13T18:00:00Z"
        combined = core.merge(first, from_documents(report, payload))
        summary = core.offer(combined)["profile"]
        self.assertEqual(summary["rating"], report["after"]["reconstructedRating"])
        self.assertEqual(summary["sessionCount"], 1)
        self.assertEqual(len(combined["captures"]), 2)

    def test_partial_or_unknown_ratings_do_not_get_a_profile_rating(self):
        report, payload = load_scenario("complete")
        partial = from_documents(report)
        self.assertIsNone(core.offer(partial)["profile"]["rating"])
        self.assertEqual(core.offer(partial)["profile"]["sessionCount"], 0)
        payload["body"]["pbs"][0]["calculatedData"]["rate"] = None
        unknown = from_documents(report, payload)
        self.assertIsNone(core.offer(unknown)["profile"]["rating"])

    def test_practice_uses_harder_other_family_and_never_repeats_exceeded_target(self):
        groups = ("cadence", "rhythm", "coordination", "holds", "slides", "spatial")
        rows = []
        refs = {}
        for cid, constant, family, versions in [
            ("anchor", 13, "anchor", ["prism"]),
            ("sibling", 13.1, "anchor", ["prism"]),
            ("harder", 13.3, "other", ["prism"]),
            ("too-hard", 13.6, "far", ["prism"]),
            ("unavailable", 13.2, "unavailable", ["circle"]),
        ]:
            rows.append(
                {
                    "chart_id": cid,
                    "source_hash": "a" * 64,
                    "version": "challenge-profile-1-experimental",
                    "song_family": family,
                    "demand": {g: {"measure": constant} for g in groups},
                }
            )
            refs[cid] = {
                "chart_id": cid,
                "constant": constant,
                "versions": versions,
                "displayVersion": "PRiSM",
                "songID": family,
                "title": cid,
                "artist": "Synthetic",
                "format": "DX",
                "difficulty": "MASTER",
                "level": "13",
            }
        score = {
            "chartID": "anchor",
            "songID": "anchor",
            "title": "Anchor",
            "difficulty": "DX MASTER",
            "levelNum": 13,
            "percent": 97,
            "rate": 252,
            "lamp": "CLEAR",
            "displayVersion": "PRiSM",
            "timeAchieved": 1000,
        }
        model = {
            "player": {"username": "fixture"},
            "generatedAt": "2026-08-30T12:00:00Z",
            "currentNewDisplayVersions": ["PRiSM"],
            "capture": {"kind": "pb-snapshot"},
        }
        value = from_documents(model, {"pbs": [score]})
        catalog = {"catalog": rows, "provider_mapping": {"charts": refs}}
        result = recommendations(value, catalog)
        self.assertTrue(result["ratingCompatible"])
        self.assertEqual(result["practice"]["chart"]["chartID"], "harder")
        self.assertEqual(result["practice"]["step"], 3)
        self.assertEqual(result["practice"]["targetPercent"], 97)
        self.assertEqual(result["practice"]["gain"], 258)
        self.assertIsNone(result["practice"]["match"]["patternDistance"])
        exceeded = {
            **score,
            "chartID": "harder",
            "songID": "other",
            "levelNum": 13.3,
            "percent": 98,
            "rate": rating(980000, 133, "CLEAR"),
        }
        value = from_documents(model, {"pbs": [score, exceeded]})
        self.assertIsNone(recommendations(value, catalog, [score])["practice"])
        # Without enough measured groups there is no fabricated structural match.
        for row in rows:
            row["demand"] = {"cadence": {"measure": 1}}
        self.assertIsNone(recommendations(value, catalog, [score])["practice"])

    def test_catalog_refresh_failure_retains_only_verified_compatible_cache(self):
        import hashlib

        from maimai_report.party_catalog import load

        data = {
            "schema_version": "maimai-public-integration-1",
            "matching_version": 1,
            "catalog_version": "synthetic",
            "catalog": [],
            "provider_mapping": {
                "schema_version": "provider-mapping-1",
                "provider": "kamaitachi",
                "game": "maimaidx",
                "charts": {},
            },
        }
        raw = json.dumps(data).encode()
        digest = hashlib.sha256(raw).hexdigest()
        manifest = {
            "default": "synthetic",
            "releases": [
                {
                    "version": "synthetic",
                    "integration": {
                        "path": f"integration/{digest}.json",
                        "sha256": digest,
                        "bytes": len(raw),
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "catalog.json"
            with patch(
                "maimai_report.party_catalog.fetch",
                side_effect=[json.dumps(manifest).encode(), raw],
            ):
                self.assertEqual(load(cache, refresh=True), (data, None))
            original = cache.read_bytes()
            with patch(
                "maimai_report.party_catalog.fetch", side_effect=OSError("Synthetic outage")
            ):
                result, warning = load(cache, refresh=True)
                self.assertEqual(result, data)
                self.assertIn("last verified", warning)
            self.assertEqual(cache.read_bytes(), original)
            with patch("maimai_report.party_catalog.fetch") as fetch:
                self.assertEqual(load(cache)[0], data)
                fetch.assert_not_called()
            cache.write_text(original.decode().replace("synthetic", "corrupted"))
            with self.assertRaisesRegex(ValueError, "integrity"):
                load(cache)

    def test_provider_policy_examples_and_invalid_lamp_combinations(self):
        # Published provider examples, including AP bonuses and one-tick boundaries.
        for achievement, constant, lamp, expected in [
            (1001398, 130, "CLEAR", 281),
            (1001379, 127, "CLEAR", 274),
            (1002270, 125, "CLEAR", 270),
            (994936, 128, "CLEAR", 264),
            (1010000, 130, "ALL PERFECT+", 293),
            (1005000, 130, "ALL PERFECT", 293),
            (1004999, 140, "CLEAR", 312),
            (999999, 137, "CLEAR", 293),
            (989999, 129, "CLEAR", 263),
            (969999, 107, "CLEAR", 182),
            (799999, 115, "FAILED", 117),
            (750000, 124, "FAILED", 111),
        ]:
            self.assertEqual(rating(achievement, constant, lamp), expected)
        for achievement, lamp in [
            (1005000, "ALL PERFECT+"),
            (1010000, "ALL PERFECT"),
            (999000, "ALL PERFECT"),
            (790000, "CLEAR"),
            (810000, "FAILED"),
        ]:
            self.assertIsNone(rating(achievement, 130, lamp))

    def test_pool_floors_ties_and_incomplete_coverage(self):
        from maimai_report.party import chart_record, observation

        player = {
            "key": "kamaitachi:maimaidx:fixture",
            "provider": "kamaitachi",
            "game": "maimaidx",
            "username": "fixture",
            "displayName": "Fixture",
        }
        value = core.empty(player)
        pbs = {}
        # A full Old 35 and New 15, plus an uncounted Old chart with real upside.
        for i in range(51):
            cid = f"fixture-{i}"
            achievement = 969000 if i == 50 else 970000
            row = {
                "chartID": cid,
                "songID": cid,
                "title": cid,
                "difficulty": "MASTER",
                "percent": achievement / 10000,
                "levelNum": 13.9 if i == 50 else 13,
                "displayVersion": "PRiSM" if 35 <= i < 50 else "Old",
                "lamp": "CLEAR",
                "rate": rating(achievement, 139 if i == 50 else 130, "CLEAR"),
            }
            value["charts"][cid] = chart_record(row)
            r = observation(row)
            ref = core.digest(r)
            value["records"][ref] = r
            pbs[cid] = ref
        snap = {
            "capturedAt": 1000,
            "phase": "after",
            "complete": True,
            "versions": ["PRiSM"],
            "pbs": pbs,
        }
        value["snapshots"][core.digest(snap)] = snap
        value = core.seal(value)
        result = recommendations(value)
        self.assertTrue(result["ratingCompatible"])
        self.assertEqual(result["floors"], {"old": 252, "new": 252})
        opportunity = next(x for x in result["rating"] if x["chart"]["chartID"] == "fixture-50")
        self.assertEqual(opportunity["gain"], 17)
        self.assertEqual(opportunity["targetGrade"], "S")
        # A target matching the existing floor has no marginal pool gain.
        low = deepcopy(value)
        del low["snapshots"][core.digest(snap)]
        snap = deepcopy(snap)
        snap["complete"] = False
        low["snapshots"][core.digest(snap)] = snap
        self.assertFalse(recommendations(core.seal(low))["ratingCompatible"])

    def test_concurrent_publication_reloads_winner_and_keeps_both_histories(self):
        objects, db = MemoryObjects(), SQLite()
        self.addCleanup(db.connection.close)
        first = dataset()
        second = dataset(when="2026-08-30T12:00:00Z")
        original = db.query
        interleaved = False

        def query(sql, params=()):
            nonlocal interleaved
            if sql.startswith("UPDATE player_state") and not interleaved:
                interleaved = True
                with patch.object(db, "query", original):
                    publish(objects, db, "fixture", [second])
            return original(sql, params)

        with patch.object(db, "query", query):
            publish(objects, db, "fixture", [first])
        self.assertEqual(latest(objects, db, "fixture")[1], core.merge(first, second))

    def test_full_pbs_same_export_and_embedded_payload(self):
        report, pbs = load_scenario("complete")
        report = enrich_report(report, pbs)
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "player.maimai.json.gz"
            data = prepare(report, player_file=file)
            html = build_html(report)
            embedded = json.loads(
                html.split('<script id="party-data" type="application/json">')[1].split(
                    "</script>"
                )[0]
            )
            self.assertEqual(base64.b64decode(embedded["payload"]), file.read_bytes())
            self.assertEqual(core.decode(file.read_bytes()), data)
            self.assertEqual(len(core.current(data)[0]), len(pbs["body"]["pbs"]))
            prepare(report, player_file=file)
            self.assertEqual(core.read(file), data)

    def test_older_history_never_replaces_newest_pbs_or_duplicates_plays(self):
        old = dataset()
        new = dataset(when="2026-08-30T12:00:00Z")
        combined = core.merge(new, old, old)
        self.assertEqual(core.current(combined)[0], core.current(new)[0])
        self.assertEqual(len(combined["plays"]), len(new["plays"]))
        self.assertEqual(core.merge(old, new), core.merge(new, old))
        other = deepcopy(old)
        other["player"].update(username="different", key="kamaitachi:maimaidx:different")
        other = core.seal(other)
        with self.assertRaisesRegex(ValueError, "different players"):
            core.merge(old, other)

    def test_corrupt_oversized_and_failed_writes_preserve_file(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "player.gz"
            data = dataset()
            core.write(file, data)
            original = file.read_bytes()
            with patch("os.replace", side_effect=OSError("Synthetic interruption")):
                with self.assertRaises(OSError):
                    core.write(file, data)
            self.assertEqual(file.read_bytes(), original)
            with self.assertRaises(ValueError):
                core.decode(original[:-8])
            with patch.object(core, "MAX_COMPRESSED", 10):
                with self.assertRaises(ValueError):
                    core.encode(data)
            self.assertEqual(file.read_bytes(), original)
            with self.assertRaises(ValueError):
                list(from_path(Path(directory) / "absent"))

    def test_pb_only_has_no_invented_plays_and_reports_incomplete_collection(self):
        report, _ = load_scenario("empty")
        report["capture"] = {
            "kind": "pb-snapshot",
            "source": "kamaitachi",
            "ratingAsOf": report["generatedAt"],
        }
        data = from_documents(report)
        self.assertFalse(data["plays"])
        self.assertFalse(core.current(data)[1]["complete"])
        self.assertFalse(recommendations(data)["ratingCompatible"])
        self.assertEqual(next(iter(data["captures"].values()))["sourceKind"], "pb-snapshot")

    def test_grade_boundaries_and_provider_one_tick_steps(self):
        for achievement, expected in [
            (969998, 211),
            (969999, 221),
            (970000, 252),
            (989998, 261),
            (989999, 265),
            (990000, 267),
            (999998, 274),
            (999999, 278),
            (1000000, 280),
            (1004998, 282),
            (1004999, 290),
            (1005000, 292),
            (1010000, 292),
        ]:
            with self.subTest(achievement=achievement):
                self.assertEqual(rating(achievement, 130), expected)
        self.assertEqual(rating(1000000, 130, "ALL PERFECT"), 281)

    def test_backfill_pb_revisions_and_failed_publication_preserve_head(self):
        objects, db, recovery = MemoryObjects(), SQLite(), MemoryObjects()
        self.addCleanup(db.connection.close)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source_fixture(path)
            bundle = prepared(path)
            archive(bundle, objects, db)
            materialize(objects, db, bundle.manifest["scope"], None, recovery_objects=recovery)
            before = latest(objects, db, bundle.manifest["scope"])
            self.assertIsNotNone(before)
            newer = dataset(when="2026-08-30T12:00:00Z")
            with patch.object(
                objects, "create", side_effect=ArchiveError("Synthetic interrupted upload")
            ):
                with self.assertRaises(ArchiveError):
                    publish(objects, db, bundle.manifest["scope"], [newer])
            self.assertEqual(latest(objects, db, bundle.manifest["scope"]), before)
            publish(objects, db, bundle.manifest["scope"], [newer])
            self.assertGreater(
                latest(objects, db, bundle.manifest["scope"])[0]["offer"]["capturedAt"],
                before[0]["offer"]["capturedAt"],
            )
            self.assertEqual(
                db.query("SELECT latest_id FROM archive_state")[0]["latest_id"], bundle.capture_id
            )
