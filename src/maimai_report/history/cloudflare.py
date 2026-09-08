"""Cloudflare management API for D1 and the documented S3 SDK for private R2."""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from typing import Any

from .bundle import MAX_FILE_BYTES, ArchiveError, canonical, load_json


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ArchiveError("Cloudflare credentials cannot follow redirects")


def required(environ: Mapping[str, str], key: str) -> str:
    value = environ.get(key, "").strip()
    if not value:
        raise ArchiveError(f"Set {key} in the private workflow secret store")
    return value


class Cloudflare:
    def __init__(self, account: str, token: str):
        if not re.fullmatch(r"[0-9a-f]{32}", account) or not token:
            raise ArchiveError("A Cloudflare account and scoped API token are required")
        self.base = f"https://api.cloudflare.com/client/v4/accounts/{account}"
        self.token = token

    def request(self, path: str, *, method: str = "GET", data: dict | None = None) -> Any:
        if not path.startswith(("/d1/", "/r2/")) or ".." in path:
            raise ArchiveError("Unsupported Cloudflare storage endpoint")
        request = urllib.request.Request(  # noqa: S310 -- fixed HTTPS Cloudflare origin
            self.base + path,
            method=method,
            data=None if data is None else canonical(data),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.build_opener(NoRedirects()).open(request, timeout=45) as response:
                raw = response.read(MAX_FILE_BYTES + 1)
                if len(raw) > MAX_FILE_BYTES:
                    raise ArchiveError("Cloudflare response exceeded the safety bound")
        except urllib.error.HTTPError as exc:
            # Provider errors can echo SQL, score data, or authorization headers.
            raise ArchiveError(f"Cloudflare storage request failed (HTTP {exc.code})") from None
        except urllib.error.URLError:
            raise ArchiveError("Cloudflare storage connection failed") from None
        payload = load_json(raw)
        if payload.get("success") is not True:
            raise ArchiveError("Cloudflare storage rejected the operation")
        return payload["result"]


class D1:
    def __init__(self, api: Cloudflare, database_id: str):
        if not re.fullmatch(r"[0-9a-f-]{36}", database_id):
            raise ArchiveError("A provisioned D1 database UUID is required")
        self.api, self.database_id = api, database_id

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        result = self.api.request(
            f"/d1/database/{self.database_id}/query",
            method="POST",
            data={"sql": sql, "params": list(params)},
        )
        if (
            not isinstance(result, list)
            or not result
            or any(r.get("success") is not True for r in result)
        ):
            raise ArchiveError("D1 did not confirm the query")
        return [row for item in result for row in item.get("results", [])]


class R2:
    def __init__(self, account: str, bucket: str, environ: Mapping[str, str] | None = None):
        if not re.fullmatch(r"[0-9a-f]{32}", account) or not re.fullmatch(
            r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket
        ):
            raise ArchiveError("Invalid R2 account or bucket")
        env = os.environ if environ is None else environ
        access = required(env, "MAIMAI_HISTORY_R2_ACCESS_KEY_ID")
        secret = required(env, "MAIMAI_HISTORY_R2_SECRET_ACCESS_KEY")
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ArchiveError(
                "Install the optional history extra: pip install '.[history]'"
            ) from None
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
            region_name="auto",
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            config=Config(
                signature_version="s3v4",
                connect_timeout=15,
                read_timeout=45,
                retries={"total_max_attempts": 3, "mode": "standard"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        self.bucket = bucket

    def get(self, key: str) -> bytes | None:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            result = self.client.get_object(Bucket=self.bucket, Key=key)
            with result["Body"] as body:
                raw = body.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise ArchiveError("R2 object exceeds the archive size bound")
            return raw
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise ArchiveError(
                "R2 object read failed; inspect permissions or service status"
            ) from None
        except BotoCoreError:
            raise ArchiveError("R2 object read failed") from None

    def create(self, key: str, raw: bytes) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        current = self.get(key)
        if current is not None:
            return current
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=raw,
                IfNoneMatch="*",
                ContentType="application/octet-stream",
                CacheControl="private, no-store",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in (
                "PreconditionFailed",
                "412",
                "ConditionalRequestConflict",
            ):
                raise ArchiveError("R2 immutable upload failed") from None
        except BotoCoreError:
            raise ArchiveError("R2 immutable upload failed; retry the retained capture") from None
        stored = self.get(key)
        if stored is None:
            raise ArchiveError("R2 upload could not be verified; retry the retained capture")
        return stored

    def keys(self, prefix: str) -> Iterator[str]:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            pages = self.client.get_paginator("list_objects_v2").paginate(
                Bucket=self.bucket, Prefix=prefix
            )
            for page in pages:
                yield from (item["Key"] for item in page.get("Contents", []))
        except (ClientError, BotoCoreError):
            raise ArchiveError("R2 archive listing failed") from None
