"""Optional build-time jacket preparation. Rendering and browser use stay offline."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
import warnings
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CATALOGUE_URL = "https://maimai.sega.jp/data/maimai_songs.json"
JACKET_BASE = "https://maimaidx-eng.com/maimai-mobile/img/Music/"
IMAGE_NAME = re.compile(r"[A-Za-z0-9_-]+\.(?:png|jpg|jpeg)", re.IGNORECASE)
MAX_DOWNLOAD = 4 * 1024 * 1024


class ArtworkUnavailable(ValueError):
    """Optional artwork cannot be prepared; the analytical report can still render."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise ArtworkUnavailable("The public artwork source redirected unexpectedly")


def _download(url: str) -> bytes:
    if url != CATALOGUE_URL and not (
        url.startswith(JACKET_BASE) and IMAGE_NAME.fullmatch(url.removeprefix(JACKET_BASE))
    ):
        raise ArtworkUnavailable("Artwork requests must use the approved public static source")
    # Both accepted forms above are fixed HTTPS origins with no caller-supplied path.
    request = urllib.request.Request(url, headers={"User-Agent": "maimai-report-artwork/1"})  # noqa: S310
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=10) as response:  # noqa: S310
        content = response.read(MAX_DOWNLOAD + 1)
    if len(content) > MAX_DOWNLOAD:
        raise ArtworkUnavailable("Public artwork response exceeds the download limit")
    return content


def _normalize(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def match_catalogue(
    songs: Mapping[str, tuple[str, str]], catalogue: list[dict[str, Any]]
) -> dict[str, str]:
    """Require exact normalized title AND artist and a unique image filename."""
    index: dict[tuple[str, str], set[str]] = {}
    for row in catalogue:
        if not isinstance(row, dict):
            continue
        name = row.get("image_url")
        title, artist = _normalize(row.get("title")), _normalize(row.get("artist"))
        if title and artist and isinstance(name, str) and IMAGE_NAME.fullmatch(name):
            index.setdefault((title, artist), set()).add(name)
    result = {}
    for song_id, (title, artist) in songs.items():
        names = index.get((_normalize(title), _normalize(artist)), set())
        if len(names) == 1:
            result[song_id] = next(iter(names))
    return result


def report_songs(report: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    """Only artwork for records actually retained by the report is needed."""
    records = []
    for snapshot in ("before", "after"):
        model = report.get(snapshot) or {}
        for pool in ("old35", "new15", "newPool"):
            records.extend(model.get(pool) or [])
    session = report.get("session") or {}
    for name in ("scores", "changedPBs"):
        records.extend(session.get(name) or [])
    candidates: dict[str, set[tuple[str, str]]] = {}
    for item in records:
        if not isinstance(item, Mapping):
            continue
        song_id = item.get("songID")
        if all(
            isinstance(item.get(key), str) and item[key] for key in ("songID", "title", "artist")
        ):
            candidates.setdefault(song_id, set()).add((item["title"], item["artist"]))
    return {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}


def _thumbnail(content: bytes) -> str:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ArtworkUnavailable("Install the optional 'artwork' extra to prepare jackets") from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ArtworkUnavailable("The jacket source is not a supported raster image")
                if image.width * image.height > 16_000_000:
                    raise ArtworkUnavailable("The jacket source dimensions exceed the limit")
                image.thumbnail((112, 112), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.convert("RGB").save(output, format="WEBP", quality=85, method=4)
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ArtworkUnavailable("The jacket source dimensions exceed the limit") from exc
    return "data:image/webp;base64," + base64.b64encode(output.getvalue()).decode("ascii")


@dataclass
class ArtworkResult:
    jackets: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, dict[str, str]] = field(default_factory=dict)
    requested: int = 0
    matched: int = 0
    warnings: list[str] = field(default_factory=list)


def prepare_jackets(
    report: Mapping[str, Any],
    cache_dir: Path,
    *,
    catalogue_path: Path | None = None,
    offline: bool = False,
    fetch: Callable[[str], bytes] = _download,
) -> ArtworkResult:
    """Prepare a private embedded cache using public static files, never score APIs.

    Missing or ambiguous matches deliberately remain absent. Source failures do
    not prevent the report from being built. Offline mode never invokes fetch.
    """
    songs = report_songs(report)
    result = ArtworkResult(requested=len(songs))
    if not songs:
        return result
    try:
        import PIL.Image  # noqa: F401
    except ImportError:
        result.warnings.append("Install the optional 'artwork' extra to prepare jackets")
        return result
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    catalogue_file = Path(catalogue_path) if catalogue_path else cache_dir / "catalogue.json"
    try:
        if catalogue_path or offline:
            raw = catalogue_file.read_bytes()
        else:
            try:
                raw = fetch(CATALOGUE_URL)
                if not isinstance(json.loads(raw), list):
                    raise ArtworkUnavailable("The public catalogue is not a list")
                catalogue_file.write_bytes(raw)
            except (OSError, ValueError):
                raw = catalogue_file.read_bytes()
                result.warnings.append("Public catalogue unavailable; using its saved copy")
        catalogue = json.loads(raw)
        if not isinstance(catalogue, list):
            raise ArtworkUnavailable("The public catalogue is not a list")
    except (OSError, ValueError):
        result.warnings.append("No usable public catalogue; jackets remain unavailable")
        return result
    matches = match_catalogue(songs, catalogue)
    result.matched = len(matches)

    def load_image(filename: str) -> tuple[str, str, str] | None:
        cached = cache_dir / filename
        try:
            content = cached.read_bytes() if cached.is_file() else None
            if content is None:
                if offline:
                    return None
                content = fetch(JACKET_BASE + filename)
            thumbnail = _thumbnail(content)
            if not cached.exists():
                cached.write_bytes(content)
            return filename, thumbnail, hashlib.sha256(content).hexdigest()
        except (OSError, ValueError, Warning):
            return None

    with ThreadPoolExecutor(max_workers=4) as executor:
        images = {
            item[0]: item[1:]
            for item in executor.map(load_image, sorted(set(matches.values())))
            if item is not None
        }
    for song_id, filename in matches.items():
        if filename in images:
            thumbnail, digest = images[filename]
            result.jackets[song_id] = thumbnail
            result.provenance[song_id] = {
                "filename": filename,
                "source": JACKET_BASE + filename,
                "sha256": digest,
            }
    missing = len(matches) - len(result.jackets)
    if missing:
        result.warnings.append(f"{missing} matched jackets unavailable; using honest placeholders")
    return result
