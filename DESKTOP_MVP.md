# The desktop review application

Evidence, not a product tour. What was built, how it is arranged, what it
guarantees about your files, and what it does not do yet.

**PlainSpeak does not overwrite the document you open.** There is no Save
command — only Save As — and Save As refuses a destination that resolves to the
source. That is the single most important thing on this page.

## What it is

An adapter over the engine built in Phases 4 to 9, and nothing more. Every
decision it displays was made by the pipeline: which changes are mechanically
safe, which need a person, which the integrity firewall refused, what the style
layer observed, and what the revised document says. The window arranges those on
a screen and sends review decisions back through the Phase 9 contract.

```
document
    │
    ▼  pipeline: project · plan · measure · interpret · plan style changes
ReviewBundle          one immutable snapshot, one named profile
    │
    ▼  accept / reject
PreviewResult         revised text, plus where every change went
    │
    ▼  Save As
a new file
```

## Technology

Python and **PySide6 6.11.2** (Qt 6.11.2), Qt Widgets rather than QML. The
product is text, lists, splitters and review controls; Widgets express that
directly, Python calls the engine in-process, and there is no IPC bridge, no
duplicated model in another language and no browser runtime. There is no
Electron, Tauri, React, webview, Qt WebEngine or JavaScript anywhere.

Supported range is `PySide6>=6.8,<6.12`. The ceiling is the next minor: Qt for
Python has moved API between minors, and an untested minor is not a supported
one.

## Architecture

```
plainspeak/desktop/
    __init__.py     application identity; imports no Qt
    session.py      state machine, review decisions, save service — no Qt
    workers.py      QThreadPool / QRunnable analysis, generation tokens
    models.py       Qt view models over engine data
    main_window.py  layout, wiring, presentation
    app.py          entry point and --self-test
    selftest.py     packaged-runtime verification
```

Two boundaries hold, both enforced by tests rather than convention.

**Qt lives only in the desktop.** No engine layer imports PySide6 — checked
statically across `core`, `document`, `rules`, `integrity`, `morphology`,
`style`, `pipeline`, `reporting` and `adapters`, and again at runtime by
importing `plainspeak` in a subprocess and inspecting `sys.modules`. A lazy
import inside a function would pass the static check and still pull Qt in on the
first ordinary call.

**The desktop imports only `pipeline`.** Not `rules`, not `style`, not
`integrity`. Where something was missing, the answer was to widen the pipeline
facade — which is why `ReviewBundle`, `PreviewResult` and `engine_identities()`
exist.

That rule caught four real violations the moment it was written: the self-test
reaching into five packages to collect identities, the session importing
`document` for a hash function, the worker importing it for a type annotation.
All four were fixed by widening the facade.

The desktop also may not define a function that materialises text, maps a span
or plans anything — `serialise`, `apply_plan`, `propose_change`,
`map_to_source`, `integrity_check` and the rest are forbidden names inside
`desktop/`.

`session.py` contains no Qt at all. Everything worth asserting about state,
decisions and file safety is testable without an event loop or a display,
because a behaviour that can only be checked by driving a GUI is a behaviour
that will stop being checked.

## Workflow

**Open** — `.txt`, `.md`, `.markdown`. Anything else is refused by name with a
sentence explaining why. DOCX, PDF and HTML do load through the plain-text
degradation path, and analysing them that way is an honest fallback; presenting
a *revised* one would not be, because a reader would reasonably assume the
structure had survived.

**Analyse** — runs automatically on open and whenever the profile changes, on a
worker thread. The window never freezes, and a frozen window is
indistinguishable from a crashed one.

**Profile** — Natural, Plain, Technical, Government, Academic, in the pack's
canonical order. Natural is preselected. That is a *product* decision about a
combo box; every pipeline call still names its profile explicitly, and there is
no engine default.

**Review** — Accept and Reject on style suggestions, which build real Phase 9
review decisions bound to the plan hash. Safe fixes are already accepted by the
engine and are shown but not re-approved.

**Save As** — writes `PreviewResult.revised_text`, never the text widget's
contents.

## Review semantics

| badge | meaning | controls |
|---|---|---|
| `SAFE` | mechanically safe, already applied | none needed |
| `REVIEW` | awaiting your decision | Accept · Reject |
| `ACCEPTED` | you accepted it | Reject to change your mind |
| `REJECTED` | you rejected it; the original wording is kept | Accept to change your mind |
| `REFUSED` | PlainSpeak refused it | **none, by design** |

Rejecting removes the replacement from the preview and keeps the author's
wording. It does **not** remove the underlying diagnostic: the reader disagreed
about what to do, not about what was observed.

There is no **Accept All**. Explicit judgement is the entire point of a
review-required change, and bulk review should be designed after the individual
interaction has been used rather than before.

There is no **Override**. The refusals model exposes no editable and no
checkable flag, so there is nothing for a future override button to attach to.

## Session safety

**One immutable plan per session.** Accepting a suggestion selects among
decisions the engine already made and already bound to a plan hash. Nothing
re-plans, because re-planning would move proposal identifiers under somebody
halfway through reading them.

**Changing profile clears every decision** and re-analyses. Phase 9 already
makes this safe — proposal identifiers are scoped to the profile, so an
acceptance under Natural cannot be replayed under Technical — but silently
failing later would be a poor way to learn it. The status line says what
happened.

**Stale results are discarded.** Every analysis carries a generation token. The
session issues a new one whenever anything invalidates in-flight work, and
checks the document hash and profile as well. The brief's scenario — Natural
starts, the reader switches to Technical, Natural finishes last — is a test:
the Natural result is dropped, and the window does not end up showing Natural
results labelled Technical.

**One analysis at a time.** A dedicated single-thread pool makes that structural
rather than a convention. There is no cancellation: interrupting the engine
would require every layer it touches to be interruptible, and a superseded
analysis finishing harmlessly is cheaper and far more predictable.

States: `EMPTY → LOADED → ANALYZING → READY → REVIEWED → SAVED`, with `ERROR`
reachable from analysis and recoverable. `EMPTY → SAVE` is unreachable and
tested as such.

## File safety

| claim | how it is verified |
|---|---|
| Open never writes | the whole directory is snapshotted before and after |
| Analyse never writes | same snapshot |
| Accept/Reject never write | same snapshot |
| Save As is the only write path | same snapshot |
| Save As cannot target the source | resolved paths; `./doc.md` and `doc.md` are the same file |
| A failed write leaves the destination untouched | fault injected mid-write; previous contents asserted intact |
| A failed write leaves no partial file | fault injected at commit; directory asserted clean |
| Saving writes the engine's bytes | the revised widget is corrupted first; the saved file is unaffected |

The write goes to `<name>.plainspeak-partial` beside the destination and is
renamed over it only once complete. A half-written export destroys the previous
one and looks like a whole file, which is worse than no export.

## Worker and staleness design

```
GUI thread                      pool thread (one)
    │
 begin_analysis() → token
    │  AnalysisRequest(token, profile, document)
    ├──────────────────────────▶ build_review_bundle(...)
    │                                    │
    │◀──── AnalysisSuccess(token) ───────┘
    │
 runner drops it if token != current
 session drops it if hash or profile moved
    │
 apply on the GUI thread
```

Two checks rather than one, because they guard different things: the runner's
stops a superseded *request* being delivered, and the session's stops a
delivered result being applied to state that has moved since.

The worker touches no widget and holds no reference to one.

## Accessibility

Real labels with buddies on both panes. Accessible names on the profile
selector, both review buttons and both editors. Keyboard mnemonics on Accept and
Reject. `Ctrl+O` open, `Ctrl+Shift+S` save as, `Ctrl+R` analyse, `F6`/`F7`
previous and next change.

No status is carried by colour alone: every row has a word — `SAFE`, `REVIEW`,
`ACCEPTED`, `REJECTED`, `REFUSED` — and a longer accessible description a screen
reader speaks.

Native styling throughout. No stylesheet and no hard-coded colour anywhere in
`desktop/`, asserted by a test, so both light and dark system palettes work and
no bundled font is required.

Verified usable at 1024×768; splitters let both document panes and the review
panels resize.

## Two defects the tests found

**A thirty-second pause on every close.** `QThreadPool.waitForDone` waits for
pool threads to *expire*, not merely for work to finish, and the global pool's
default expiry is thirty seconds. In a suite that is thirty seconds per test; in
an application it is a window that will not go away. Fixed with a dedicated pool
with a short expiry, which also makes "one analysis at a time" structural.

**A modal dialog that blocked its own test permanently.** The
close-confirmation dialog cannot be answered from the thread it blocks. The
close decision is now split: `should_prompt_before_closing()` answers the
question without a dialog and is directly testable, and `confirm_discard()` is a
substitutable attribute so a test can drive the real `closeEvent`. The
alternative was a close path that went untested because it could not be reached.

## Deployment

`deploy/pysidedeploy.spec`, checked in, with no absolute paths — `pyside6-deploy
--init` writes a spec full of them, and a build that works only on the machine
that generated its configuration is not reproducible.

`--include-package-data=plainspeak` is the line the file exists for. The
syllable dictionary, 222 rule YAML files and five profile YAML files are not
Python modules, so a successful compile implies nothing about whether they came
along. A build without them launches, opens a document, loads no rules and
quietly gives different answers — the defect this project has shipped twice
already through `package-data`.

`tools/record_desktop_build.py` verifies the bundle contains that data and a
real executable, and writes a manifest with the executable's SHA-256.

### Build evidence

Both produced on candidate `5181f24a366f49870f105899280e32931698dde1`, CI run
33321453443, and both self-tested from a directory containing neither the
checkout nor the virtual environment.

| | Linux | Windows |
|---|---|---|
| bundle | 131 files, 162.0 MiB | 78 files, 80.8 MiB |
| executable | `PlainSpeak.dist/desktop_main.bin`, 17.4 MiB | `PlainSpeak.dist/desktop_main.exe`, 13.2 MiB |
| SHA-256 | `fdd72b0f7b71c985…` | `f76d33b7163f7d83…` |
| syllable dictionary | present | present |
| bundled rules | present | present |
| style profiles | present | present |
| self-test | OK | OK |

Both report ruleset 2026.3 / `7eddd0710ec1` / 222 rules / 8 style fixes,
integrity 2026.1, morphology 2026.1, style policy 2026.1, profile pack 2026.1
with all five profiles, and the **same** smoke output hash
`a70aa737f4a5b63a…` — which is the property that matters. The two executables
are different bytes, as executables built by different compilers on different
operating systems always are; what has to match is what they compute, and it
does.

### Six spec defects, each worth naming

Every one cost a full build cycle, and every one was findable from the
repository in under a second. They are now checked there, in
`tests/test_desktop_session.py`:

1. A comment before the first section. `pyside6-deploy` reads the spec through a
   strict `configparser` path and raised `MissingSectionHeaderError` before
   Nuitka ran at all.
2. `--include-package-data` did not carry the syllable dictionary. Nuitka does
   not treat a `.bin` as package data, so the build loaded 222 rules, reported
   every identity correctly, and would have silently used a vowel-counting
   heuristic for every readability metric. **The verifier caught this**, which is
   the entire reason it was written before the first build.
3. `--quiet` hid the real Windows error and left a bare non-zero exit.
4. `--company-name` without a version. Nuitka requires both on Windows.
5. `--file-description=PlainSpeak desktop review`. `extra_args` is split on
   whitespace, so Nuitka received three arguments, read two as positional, and
   died with "specify only one positional argument".
6. Windows standalone needs Nuitka's dependency walker, which it will not fetch
   without consent. An unattended build stops on a prompt nobody is there to
   answer and reports it as a capability problem.

The tests now assert that the spec parses, that every entry in `extra_args` is a
flag, that the dictionary is named explicitly, that no path is absolute, and
that no web or network Qt module is bundled.

`--self-test` checks every published identity, the syllable dictionary and the
exact output hash of a fixture carried inside the package, then exits. It runs
from a directory containing neither the checkout nor the virtual environment: a
build that finds the engine's data only because the source tree happens to be
nearby is a failed deployment.

## Development

```bash
pip install -e ".[desktop,dev]"
plainspeak-desktop
```

Or `python -m plainspeak.desktop.app`. Headless tests:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## Offline

No network on any path a person can reach. No update check, no analytics, no
crash upload, no remote fonts, no web content, no telemetry. Asserted at runtime
with sockets denied — plan, review, materialise, self-test — and statically: no
networking import anywhere in `desktop/`, and no `QtNetwork`, `QtWebEngine`,
`QtWebView` or `QtWebSockets`.

## Known limitations

- **No manual editing.** Both panes are read-only. Typed text would be text no
  rule proposed, no source mapping authorised, no integrity preflight validated
  and no proposal identifies, and the revised pane would stop being something
  the engine could vouch for.
- **Text and Markdown only.** Structured DOCX, PDF and HTML need an engine phase
  of their own, not a parser bolted onto GUI work.
- **No Accept All**, and none planned until the individual interaction has been
  used.
- **No profile creation or editing.** Bundled profiles only.
- **No change playback.** The optional animation was not built; the MVP was not
  worth delaying for it.
- **macOS packaging is deferred** — source and headless tests run there; there is
  no signed `.app`, no notarisation and no DMG.
- **No installer.** Portable directory bundles only.
- **No MCP server.** Desktop and MCP should consume the same pipeline, but
  building both adapters at once would make a failure harder to localise.
