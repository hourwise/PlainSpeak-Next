"""The review session: everything the desktop knows, with no Qt in it.

Deliberately importable without PySide6. Session state, the state machine that
governs it, review decisions and the save service are all decisions a test should
be able to make and check without an event loop, a widget or a display — so none
of them lives in a widget.

The one rule this file exists to enforce is that a session is a *view* of an
engine snapshot, never a second opinion about it. It holds a `ReviewBundle` and a
set of accepted and rejected identifiers, and it asks the pipeline to
materialise. It does not decide what a change is, where it goes, or whether it is
safe.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional

from ..pipeline.review import (
    KIND_STYLE,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    ChangeView,
    PreviewResult,
    ReviewBundle,
    ReviewError,
)
from ..pipeline.style_plan import STATUS_REVIEW_REQUIRED


class State(Enum):
    """Where a session is, and therefore what it will let you do.

    Explicit because the alternative is a scattering of `if self._bundle is not
    None and not self._busy` conditions that nobody can enumerate. An interface
    asks the session what is permitted; the session does not ask the interface
    what it feels like doing.
    """

    EMPTY = "empty"
    LOADED = "loaded"
    ANALYZING = "analyzing"
    READY = "ready"
    REVIEWED = "reviewed"
    SAVED = "saved"
    ERROR = "error"


class SessionError(RuntimeError):
    """An operation was attempted in a state that does not permit it."""


class SaveError(RuntimeError):
    """A save was refused or failed. The source is never affected either way."""


#: The default shown when the application starts. A *product* decision about
#: what to preselect in a combo box, and emphatically not an engine default:
#: every pipeline call still names its profile explicitly.
DEFAULT_PROFILE = "natural"


@dataclass(frozen=True)
class SessionSnapshot:
    """An immutable view of the session, safe to hand to a widget.

    Widgets render this and nothing else. Handing them the live session would
    let a rendering path mutate review state, which is the single most likely
    way a review interface goes wrong.
    """

    state: State
    path: Optional[Path]
    profile_id: str
    source_text: str
    preview: Optional[PreviewResult]
    diagnostics: tuple
    identities: dict
    accepted: frozenset
    rejected: frozenset
    message: str = ""
    saved_to: Optional[Path] = None

    @property
    def revised_text(self) -> str:
        return self.preview.revised_text if self.preview is not None else ""

    @property
    def changes(self) -> tuple[ChangeView, ...]:
        return self.preview.changes if self.preview is not None else ()

    @property
    def undecided(self) -> tuple[ChangeView, ...]:
        return tuple(
            item for item in self.changes
            if item.kind == KIND_STYLE and item.status == STATUS_REVIEW_REQUIRED
        )

    @property
    def has_unsaved_decisions(self) -> bool:
        return bool(self.accepted or self.rejected) and self.state is not State.SAVED

    @property
    def can_analyze(self) -> bool:
        return self.state in (State.LOADED, State.READY, State.REVIEWED, State.SAVED, State.ERROR) \
            and self.source_text != ""

    @property
    def can_review(self) -> bool:
        return self.state in (State.READY, State.REVIEWED, State.SAVED)

    @property
    def can_save(self) -> bool:
        return self.can_review and self.preview is not None

    @property
    def busy(self) -> bool:
        return self.state is State.ANALYZING


class ReviewSession:
    """One document, one profile, one immutable engine snapshot at a time.

    Review decisions select among proposals the engine has already made and
    already bound to a plan hash. Nothing here re-plans: an interface that
    re-analysed after every click would move proposal identifiers under a person
    who was halfway through reading them.
    """

    def __init__(self, profile_id: str = DEFAULT_PROFILE) -> None:
        self._state = State.EMPTY
        self._path: Optional[Path] = None
        self._source = ""
        self._profile_id = profile_id
        self._bundle: Optional[ReviewBundle] = None
        self._preview: Optional[PreviewResult] = None
        self._accepted: set[str] = set()
        self._rejected: set[str] = set()
        self._message = ""
        self._saved_to: Optional[Path] = None
        #: Bumped whenever anything invalidates an in-flight analysis. A worker
        #: result carrying a stale token is discarded rather than applied.
        self._generation = 0

    # ── Reading ────────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        return self._state

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def profile_id(self) -> str:
        return self._profile_id

    @property
    def bundle(self) -> Optional[ReviewBundle]:
        return self._bundle

    def snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(
            state=self._state,
            path=self._path,
            profile_id=self._profile_id,
            source_text=self._source,
            preview=self._preview,
            diagnostics=self._bundle.diagnostics() if self._bundle else (),
            identities=self._bundle.identities() if self._bundle else {},
            accepted=frozenset(self._accepted),
            rejected=frozenset(self._rejected),
            message=self._message,
            saved_to=self._saved_to,
        )

    # ── Transitions ────────────────────────────────────────────────────────

    def load(self, path: Path, source: str) -> int:
        """Take a new document. Everything about the previous one is discarded."""
        self._path = Path(path)
        self._source = source
        self._bundle = None
        self._preview = None
        self._accepted.clear()
        self._rejected.clear()
        self._saved_to = None
        self._message = ""
        self._state = State.LOADED
        return self._invalidate()

    def set_profile(self, profile_id: str) -> int:
        """Change the profile, discarding every decision made under the old one.

        Phase 9 makes this safe at the engine level — proposal identifiers are
        scoped to the profile, so an acceptance under `natural` cannot be
        replayed under `technical`. This makes it *visible*: the decisions are
        cleared rather than silently failing later, and the interface can say so.
        """
        if profile_id == self._profile_id:
            return self._generation
        self._profile_id = profile_id
        self._bundle = None
        self._preview = None
        self._accepted.clear()
        self._rejected.clear()
        self._saved_to = None
        self._message = ""
        if self._state is not State.EMPTY:
            self._state = State.LOADED
        return self._invalidate()

    def begin_analysis(self) -> int:
        if not self.snapshot().can_analyze:
            raise SessionError(f"cannot analyse from {self._state.value}")
        self._state = State.ANALYZING
        self._message = ""
        return self._invalidate()

    def accept_analysis(self, bundle: ReviewBundle, generation: int) -> bool:
        """Take a worker's result, or discard it as stale.

        The staleness check is the whole point. A slow analysis under one profile
        must never replace a newer one under another, and the guard is the
        generation token plus the input and profile the result was computed
        against — not a timestamp, and not the order results happen to arrive in.
        """
        if generation != self._generation:
            return False
        if bundle.input_hash != _hash_of(self._source):
            return False
        if bundle.profile_id != self._profile_id:
            return False

        self._bundle = bundle
        self._accepted.clear()
        self._rejected.clear()
        self._preview = bundle.preview()
        self._state = State.READY
        return True

    def fail_analysis(self, message: str, generation: int) -> bool:
        if generation != self._generation:
            return False
        self._message = message
        self._state = State.ERROR
        return True

    # ── Review decisions ───────────────────────────────────────────────────

    def accept(self, change_id: str) -> None:
        self._decide(change_id, accepted=True)

    def reject(self, change_id: str) -> None:
        self._decide(change_id, accepted=False)

    def clear_decision(self, change_id: str) -> None:
        self._accepted.discard(change_id)
        self._rejected.discard(change_id)
        self._rematerialise()

    def _decide(self, change_id: str, accepted: bool) -> None:
        if not self.snapshot().can_review or self._bundle is None:
            raise SessionError(f"cannot review from {self._state.value}")
        if change_id not in {item.proposal_id for item in self._bundle.reviewable}:
            raise SessionError(f"{change_id} is not awaiting review")

        self._accepted.discard(change_id)
        self._rejected.discard(change_id)
        (self._accepted if accepted else self._rejected).add(change_id)
        self._rematerialise()
        self._state = State.REVIEWED

    def _rematerialise(self) -> None:
        """Rebuild the preview from the same plan. Never re-plan."""
        assert self._bundle is not None
        self._preview = self._bundle.preview(
            accepted=self._accepted, rejected=self._rejected
        )
        self._saved_to = None

    # ── Saving ─────────────────────────────────────────────────────────────

    def mark_saved(self, destination: Path) -> None:
        self._saved_to = Path(destination)
        self._state = State.SAVED

    # ── Internals ──────────────────────────────────────────────────────────

    def _invalidate(self) -> int:
        self._generation += 1
        return self._generation


def _hash_of(text: str) -> str:
    from ..pipeline import text_hash

    return text_hash(text)


# ── Saving is a service, not a widget method ───────────────────────────────


def save_revised(
    revised_text: str,
    destination: Path,
    source_path: Optional[Path],
    *,
    writer=None,
) -> Path:
    """Write the revised document to a new file, atomically, never over the source.

    Three properties, in order of how badly their absence would hurt:

    **The source is never the destination.** Checked on the resolved paths, so a
    relative path, a symlink or a different spelling of the same file is still
    refused. This is a refusal, not a warning with an override button — an
    overwrite feature deserves to be designed rather than arrived at.

    **The write is atomic.** Content goes to a temporary file beside the
    destination and is renamed over it only once it is completely written. A
    failure part-way through leaves the destination as it was, rather than
    truncated, which is the state that loses somebody's previous export.

    **The bytes are the pipeline's.** `revised_text` comes from `PreviewResult`,
    not from a text widget. A rendering bug must not be able to reach a file.
    """
    target = Path(destination)
    if source_path is not None:
        try:
            same = target.resolve(strict=False) == Path(source_path).resolve(strict=False)
        except OSError:  # pragma: no cover - platform-specific resolution failure
            same = target.absolute() == Path(source_path).absolute()
        if same:
            raise SaveError(
                "PlainSpeak does not overwrite the document it read. Choose a "
                "different destination — the original is left exactly as it was."
            )

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".plainspeak-partial")
    write = writer if writer is not None else _write_bytes

    try:
        write(temporary, revised_text.encode("utf-8"))
        os.replace(temporary, target)
    except Exception as error:  # noqa: BLE001 - re-raised as a domain error below
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:  # pragma: no cover - best effort only
            pass
        raise SaveError(f"the revised document could not be saved: {error}") from error

    return target


def _write_bytes(path: Path, payload: bytes) -> None:
    with open(path, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
