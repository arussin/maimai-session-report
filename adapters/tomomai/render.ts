// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 arussin (this adapter).
// Adapter to Tomomai / ともマイ by shedaniel and its contributors.
// Upstream: https://github.com/shedaniel/tomomai
// Revision: 7608b9c250f4a8778cdfd4768cdecb7628cd5889 (AGPLv3).
// This local JSON-to-B50 wrapper imports the pinned upstream renderer below.
// Downstream build patch, 2026-09-08: scripts/harden_tomomai.py restores
// catalogue/image/image-cache TLS validation; other upstream source is unchanged.
// See this directory's LICENSE and README.md, and ../../THIRD_PARTY_NOTICES.md.
// No warranty; SEGA artwork is not relicensed by the project's MIT grant.
import fs from "node:fs/promises";
import path from "node:path";

import { renderImage, type SongForRender } from "../_tomomai/apps/render/src/lib/render-image";
import { getCatalog } from "../_tomomai/apps/render/src/lib/catalog";
import { splitSongs } from "../_tomomai/apps/render/src/lib/rating-calculator";
import { commonSnapshotResources, renderToWebp } from "../_tomomai/apps/render/src/render-route";
import type { Difficulty, FullCombo, SongType } from "../_tomomai/apps/render/src/lib/types";

type JsonObject = Record<string, unknown>;

const FALLBACK_ART = "/res/icons/base.png";

function object(value: unknown, label: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`Missing ${label}`);
  return value as JsonObject;
}
function array(value: unknown, label: string): JsonObject[] {
  if (!Array.isArray(value)) throw new Error(`Missing ${label}[]`);
  return value.map((item, i) => object(item, `${label}[${i}]`));
}
function string(value: unknown, label: string): string {
  if (typeof value !== "string" || !value) throw new Error(`Missing ${label}`);
  return value;
}
function number(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

const FC_MAP: Record<string, FullCombo> = {
  "FULL COMBO": "fc",
  "FULL COMBO+": "fc+",
  "ALL PERFECT": "ap",
  "ALL PERFECT+": "ap+",
};

function chartIdentity(rawDifficulty: string): { type: SongType; difficulty: Difficulty } {
  const type: SongType = /^DX\s+/i.test(rawDifficulty) ? "dx" : "std";
  const normalized = rawDifficulty.replace(/^DX\s+/i, "").toLowerCase().replace(/[^a-z]/g, "");
  const aliases: Record<string, Difficulty> = {
    basic: "basic",
    advanced: "advanced",
    expert: "expert",
    master: "master",
    remaster: "remaster",
    utage: "utage",
  };
  const difficulty = aliases[normalized];
  if (!difficulty) throw new Error(`Unsupported Kamaitachi difficulty: ${rawDifficulty}`);
  return { type, difficulty };
}

async function main(): Promise<void> {
  const [_afterPath, reportPath, outputPath] = process.argv.slice(2);
  if (!reportPath || !outputPath) {
    throw new Error("usage: render_tomomai_b50.ts AFTER_PBS REPORT_INPUT OUTPUT_WEBP");
  }

  const report = JSON.parse(await fs.readFile(reportPath, "utf8")) as JsonObject;
  const afterReport = object(report.after, "report.after");
  const new15 = array(afterReport.new15, "report.after.new15");
  const old35 = array(afterReport.old35, "report.after.old35");
  if (new15.length !== 15 || old35.length !== 35) {
    throw new Error(`Report B50 is incomplete: new15=${new15.length}, old35=${old35.length}`);
  }

  const catalog = await getCatalog();
  const allEntries = [...catalog.values()];
  const intlEntries = allEntries.filter((entry) => entry.region === "intl");
  if (!intlEntries.length) throw new Error("Tomomai catalog returned no INTL charts");
  const gameVersion = Math.max(...intlEntries.map((entry) => entry.gameVersion));

  const catalogByTitle = new Map<string, typeof allEntries>();
  for (const entry of allEntries) {
    const bucket = catalogByTitle.get(entry.songName) ?? [];
    bucket.push(entry);
    catalogByTitle.set(entry.songName, bucket);
  }

  const fallbackTitles = new Set<string>();
  function convert(row: JsonObject, isNew: boolean): SongForRender {
    const title = string(row.title, "b50.title");
    const { type, difficulty } = chartIdentity(string(row.difficulty, "b50.difficulty"));
    const candidates = (catalogByTitle.get(title) ?? []).sort((a, b) => {
      const aExact = (a.type === type ? 2 : 0) + (a.difficulty === difficulty ? 1 : 0);
      const bExact = (b.type === type ? 2 : 0) + (b.difficulty === difficulty ? 1 : 0);
      const aIntl = a.region === "intl" ? 1 : 0;
      const bIntl = b.region === "intl" ? 1 : 0;
      return bExact - aExact || bIntl - aIntl || b.gameVersion - a.gameVersion;
    });
    const entry = candidates[0];
    if (!entry) fallbackTitles.add(title);

    const lamp = typeof row.lamp === "string" ? row.lamp : "";
    return {
      songName: title,
      cover: entry?.cover ?? FALLBACK_ART,
      difficulty,
      type,
      // Tomomai stores chart constants in tenths (105 means 10.5).
      // report-input uses the human-scale decimal, so convert units here.
      levelPrecise: Math.round(number(row.levelNum) * 10),
      addedVersion: isNew ? gameVersion : 0,
      achievement: Math.round(number(row.percent) * 10_000),
      fc: FC_MAP[lamp] ?? "none",
      fs: "none",
    };
  }

  const renderSongs = [
    ...new15.map((row) => convert(row, true)),
    ...old35.map((row) => convert(row, false)),
  ];

  // Tomomai's live catalogue occasionally retains relative generic jackets or
  // stale CDN URLs. Its renderer treats non-/res paths as fetchable URLs, so
  // normalize these before rendering and fail soft to Tomomai's neutral art.
  await Promise.all(renderSongs.map(async (song) => {
    if (song.cover === FALLBACK_ART) return;
    if (!/^https?:\/\//i.test(song.cover)) {
      fallbackTitles.add(song.songName);
      song.cover = FALLBACK_ART;
      return;
    }
    try {
      const response = await fetch(song.cover, {
        signal: AbortSignal.timeout(10_000),
        headers: { Range: "bytes=0-0" },
      });
      await response.body?.cancel();
      if (!response.ok) {
        fallbackTitles.add(song.songName);
        song.cover = FALLBACK_ART;
      }
    } catch {
      fallbackTitles.add(song.songName);
      song.cover = FALLBACK_ART;
    }
  }));

  if (fallbackTitles.size) {
    console.warn(`Using neutral jacket fallback for ${fallbackTitles.size} charts`);
  }

  const rating = Math.trunc(number(afterReport.reconstructedRating, number(afterReport.naiveRating)));
  const displayName = process.env.MAIMAI_REPORT_DISPLAY_NAME || process.env.MAIMAI_REPORT_USERNAME || "Player";
  const snapshotData = {
    snapshot: {
      id: "",
      fetchedAt: new Date(),
      rating,
      displayName,
      gameVersion,
      courseRankUrl: FALLBACK_ART,
      classRankUrl: FALLBACK_ART,
      stars: 0,
      versionPlayCount: 0,
      totalPlayCount: 0,
      title: "Kamaitachi",
      titleType: "normal" as const,
      iconUrl: FALLBACK_ART,
    },
    songs: renderSongs,
  };

  const { newSongsB15, oldSongsB35 } = splitSongs(renderSongs, gameVersion);
  if (newSongsB15.length !== 15 || oldSongsB35.length !== 35) {
    throw new Error(`Tomomai B50 split incomplete: B15=${newSongsB15.length}, B35=${oldSongsB35.length}`);
  }

  const outcome = await renderToWebp({
    routeName: "private-b50",
    requestId: `private-${Date.now()}`,
    scale: 2,
    resources: [
      ...commonSnapshotResources(snapshotData.snapshot, "intl"),
      "/res/label/new.png",
      "/res/label/old.png",
      ...newSongsB15.map((song) => song.cover),
      ...oldSongsB35.map((song) => song.cover),
    ],
    render: (cache) => renderImage(snapshotData, "intl", cache, undefined),
    filename: "maimai-b50",
  });

  if (!outcome.ok) throw new Error(`Tomomai render failed: ${JSON.stringify(outcome.body)}`);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, outcome.buffer);
  console.log(`B50 rendered: ${outcome.buffer.length} bytes; fallback jackets=${fallbackTitles.size}`);
}

main().catch((error) => {
  console.error("B50 rendering failed; retained score inputs are available for a build retry.");
  process.exitCode = 1;
});
