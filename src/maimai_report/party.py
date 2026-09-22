"""Compatibility imports for report-owned player capture conversion."""

from .player_capture import (
    body as body,
)
from .player_capture import (
    chart_record as chart_record,
)
from .player_capture import (
    compact_payload as compact_payload,
)
from .player_capture import (
    documents_from_directory as documents_from_directory,
)
from .player_capture import (
    file_lock as file_lock,
)
from .player_capture import (
    from_bundle as from_bundle,
)
from .player_capture import (
    from_documents as from_documents,
)
from .player_capture import (
    from_path as from_path,
)
from .player_capture import (
    identity as identity,
)
from .player_capture import (
    observation as observation,
)
from .player_capture import (
    pb_play_id as pb_play_id,
)
from .player_capture import (
    prepare_dataset as prepare_dataset,
)
from .player_capture import (
    timestamp as timestamp,
)


def prepare(report, *, source=None, history=(), player_file=None):
    """Compatibility wrapper retaining the historical dictionary mutation."""
    from .compatibility import prepare_player

    return prepare_player(report, source=source, history=history, player_file=player_file)
