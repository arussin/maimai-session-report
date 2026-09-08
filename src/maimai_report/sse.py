"""Minimal server-sent-event parsing for Kamaitachi import completion."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .errors import ImportFailedError, ImportStreamEndedError


@dataclass(frozen=True, slots=True)
class ServerSentEvent:
    """One dispatched SSE event."""

    name: str | None
    data: str


def iter_events(lines: Iterable[bytes | str]) -> Iterator[ServerSentEvent]:
    """Parse complete SSE records, dispatching only on blank lines.

    The source workflow intentionally treats a stream that ends without a final
    blank-line dispatch as incomplete. This function therefore does not synthesize
    an event at EOF.
    """

    event_name: str | None = None
    data_lines: list[str] = []

    for raw_line in lines:
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", errors="replace")
        else:
            line = raw_line
        line = line.rstrip("\r\n")

        if line == "":
            if event_name is not None or data_lines:
                yield ServerSentEvent(event_name, "\n".join(data_lines))
            event_name = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue

        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)


def wait_for_completion(lines: Iterable[bytes | str]) -> None:
    """Return on ``done`` and fail on every non-completing terminal outcome."""

    for event in iter_events(lines):
        if event.name == "done":
            return
        if event.name == "import:failed":
            # Upstream error descriptions can contain private integration details.
            # A length limit is not redaction; never relay the service's body to logs.
            raise ImportFailedError(
                "MYT import failed. Check the import status and integration in Kamaitachi "
                "before starting another explicit sync."
            )
    raise ImportStreamEndedError("Import progress stream ended before completion.")
