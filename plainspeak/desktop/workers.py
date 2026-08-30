"""Running the engine off the GUI thread, and discarding work that has aged out.

Analysis of a long document takes seconds. Doing it on the GUI thread freezes
the window, and a frozen window is indistinguishable from a crashed one.

The design is deliberately the small one. A `QThreadPool` and a `QRunnable`,
immutable input in, immutable result out, and no widget touched from the worker
— results come back as a signal and are applied on the GUI thread. There is no
cancellation: interrupting the engine mid-analysis would need every layer it
touches to be interruptible, and the phase does not need it. A superseded
analysis is allowed to finish and its result is thrown away.

Which makes the generation token the load-bearing part. Every request carries
one, the session hands out a new one whenever anything invalidates in-flight
work, and a result whose token no longer matches is discarded. Without it, a
slow analysis under one profile can land after a fast one under another and
quietly replace it — the window would show technical results labelled natural,
and nothing would look wrong.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ..pipeline import Document
from ..pipeline.review import ReviewBundle, build_review_bundle


@dataclass(frozen=True)
class AnalysisRequest:
    """Immutable input to one analysis. Crosses the thread boundary by value."""

    generation: int
    profile_id: str
    document: Document


@dataclass(frozen=True)
class AnalysisSuccess:
    generation: int
    profile_id: str
    bundle: ReviewBundle


@dataclass(frozen=True)
class AnalysisFailure:
    generation: int
    profile_id: str
    message: str


class _Signals(QObject):
    """Signals live on a QObject; QRunnable is not one."""

    finished = Signal(object)


class AnalysisTask(QRunnable):
    """One analysis, run on a pool thread.

    Touches no widget and holds no reference to one. It calls the pipeline,
    wraps the outcome — success or failure — and emits it. Deciding what to do
    with the result, including whether it is still wanted, happens on the GUI
    thread.
    """

    def __init__(self, request: AnalysisRequest, builder: Optional[Callable] = None) -> None:
        super().__init__()
        self.request = request
        self.signals = _Signals()
        self._builder = builder if builder is not None else build_review_bundle
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:  # pragma: no cover - exercised through AnalysisRunner
        request = self.request
        try:
            bundle = self._builder(request.document, request.profile_id)
        except Exception as error:  # noqa: BLE001 - reported, never raised into Qt
            self.signals.finished.emit(
                AnalysisFailure(
                    generation=request.generation,
                    profile_id=request.profile_id,
                    message=_readable(error),
                )
            )
            return
        self.signals.finished.emit(
            AnalysisSuccess(
                generation=request.generation,
                profile_id=request.profile_id,
                bundle=bundle,
            )
        )


class AnalysisRunner(QObject):
    """Starts analyses and reports their results, one at a time.

    "One at a time" is a promise about *results*, not about threads. Starting a
    new analysis marks the previous generation stale; if the old one is still
    running it finishes harmlessly and its result is dropped when it arrives.
    That is cheaper and far more predictable than trying to interrupt an engine
    that was never written to be interrupted.
    """

    completed = Signal(object)

    def __init__(self, parent: Optional[QObject] = None, pool: Optional[QThreadPool] = None) -> None:
        super().__init__(parent)
        if pool is None:
            # A dedicated pool rather than the global one, for two reasons.
            #
            # One thread makes "one analysis at a time" structural instead of a
            # convention: a second request cannot start early even if some future
            # code path forgets to check.
            #
            # And a short expiry keeps shutdown quick. `waitForDone` waits for
            # pool threads to *expire*, not merely for work to finish, so the
            # global pool's thirty-second default turns every close into a
            # thirty-second pause — which in a test suite is thirty seconds per
            # test, and in an application is a window that will not go away.
            pool = QThreadPool(self)
            pool.setMaxThreadCount(1)
            pool.setExpiryTimeout(100)
        self._pool = pool
        self._current: Optional[int] = None

    @property
    def current_generation(self) -> Optional[int]:
        return self._current

    def start(self, request: AnalysisRequest, builder: Optional[Callable] = None) -> None:
        self._current = request.generation
        task = AnalysisTask(request, builder)
        task.signals.finished.connect(self._deliver)
        self._pool.start(task)

    @Slot(object)
    def _deliver(self, outcome: Any) -> None:
        """Drop anything that has been superseded, then hand the rest on.

        The session checks staleness again, against the document hash and the
        profile as well as the token. Two checks rather than one because they
        guard different things: this one stops a superseded *request* from being
        delivered at all, and the session's stops a delivered result from being
        applied to state that has moved since.
        """
        if outcome.generation != self._current:
            return
        self.completed.emit(outcome)

    def wait(self, milliseconds: int = 30_000) -> bool:
        """Block until the pool is idle. For tests and for shutdown."""
        return self._pool.waitForDone(milliseconds)


def _readable(error: Exception) -> str:
    """A message a person can act on, never a traceback.

    Tracebacks belong in a log. A dialog showing one tells the reader nothing
    they can do and hides the one sentence that would have.
    """
    text = str(error).strip()
    return text if text else f"{type(error).__name__} while analysing the document"
