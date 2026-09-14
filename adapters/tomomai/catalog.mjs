// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 arussin.
// Public catalogue adapter for Tomomai / ともマイ by shedaniel and contributors.
// API contract: shedaniel/tomomai@acf975ae520b1b2e6223d41d2e8875539e83b190

const ORIGIN = 'https://tomomai.lol';
const REGION = 'intl';
const TIMEOUT_MS = 15000;
const DIFFICULTIES = new Set(['basic', 'advanced', 'expert', 'master', 'remaster', 'utage']);

class CatalogError extends Error {
  constructor(stage, reason, cause) {
    super(`B50 catalogue ${stage}: ${reason}`, { cause });
    this.name = 'CatalogError';
  }
}

export function describeFailure(error) {
  if (error instanceof CatalogError) return error.message;
  // Never print arbitrary upstream response bodies, URLs, or score-bearing errors.
  const code = error?.cause?.code ?? error?.code;
  return typeof code === 'string' && /^(ERR_|UND_ERR_|E)[A-Z0-9_]{1,70}$/.test(code)
    ? `B50 renderer failed (${code})`
    : 'B50 renderer failed; inspect the retained inputs and upstream stage log';
}

async function fetchJSON(path, stage, fetcher) {
  let response;
  try {
    response = await fetcher(`${ORIGIN}${path}`, { signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (cause) {
    throw new CatalogError(stage, describeFailure(cause), cause);
  }
  if (!response.ok) throw new CatalogError(stage, `HTTP ${response.status}`);
  try {
    return await response.json();
  } catch (cause) {
    throw new CatalogError(stage, 'invalid JSON', cause);
  }
}

export async function getIntlCatalog(fetcher = fetch) {
  const versions = await fetchJSON('/api/v1/songs/versions?region=intl', 'versions', fetcher);
  const version = versions?.currentVersion;
  if (!Number.isInteger(version) || version < -32768 || version > 32767 ||
      !Array.isArray(versions?.versions) || !versions.versions.some(v => v?.id === version)) {
    throw new CatalogError('versions', 'invalid current international version');
  }
  const body = await fetchJSON(`/api/v1/songs?region=intl&gameVersion=${version}`, 'songs', fetcher);
  if (!Array.isArray(body?.songs) || body.songs.length === 0) {
    throw new CatalogError('songs', 'empty or invalid songs array');
  }
  const catalog = new Map();
  for (const entry of body.songs) {
    if (!entry || typeof entry.songId !== 'string' || !entry.songId ||
        typeof entry.songName !== 'string' || !entry.songName ||
        (entry.cover !== null && typeof entry.cover !== 'string') ||
        !['std', 'dx', 'utage'].includes(entry.type) || !DIFFICULTIES.has(entry.difficulty) ||
        entry.region !== REGION || entry.gameVersion !== version || catalog.has(entry.songId)) {
      throw new CatalogError('songs', 'invalid, duplicate, or mismatched chart entry');
    }
    catalog.set(entry.songId, entry);
  }
  return catalog;
}
