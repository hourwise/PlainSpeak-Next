"""The PyPI release workflow keeps its fail-closed shape.

Publication uses Trusted Publishing: PyPI trusts `release.yml` in this
repository, deploying to the `pypi` environment. These tests keep the parts
that make that safe from quietly eroding — no stored token, the OIDC
permission only where the upload happens, publication only after the
certified artifacts have been verified, and nothing that runs on a push.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _load(name: str) -> dict:
    workflow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # YAML 1.1 reads the bare key `on` as the boolean true.
    workflow["on"] = workflow.pop(True, workflow.get("on"))
    return workflow


def test_the_release_runs_only_when_dispatched():
    """Nothing publishes on a push, a tag push or a pull request."""
    assert set(_load("release.yml")["on"]) == {"workflow_dispatch"}


def test_no_long_lived_pypi_credential_is_used():
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert "secrets." not in text
    assert not re.search(r"^\s*(password|user|username)\s*:", text, re.M)


def test_only_the_publish_job_can_mint_an_identity_token():
    workflow = _load("release.yml")
    assert workflow["permissions"] == {}
    jobs = workflow["jobs"]
    assert jobs["publish"]["permissions"] == {"id-token": "write"}
    assert all("id-token" not in (job.get("permissions") or {})
               for name, job in jobs.items() if name != "publish")
    assert "id-token" not in (_load("ci.yml").get("permissions") or {})


def test_publication_waits_for_verification_in_the_pypi_environment():
    publish = _load("release.yml")["jobs"]["publish"]
    assert publish["needs"] == "verify"
    assert publish["environment"]["name"] == "pypi"
    upload = [step["uses"] for step in publish["steps"] if "pypi-publish" in step.get("uses", "")]
    assert len(upload) == 1
    assert re.fullmatch(r"pypa/gh-action-pypi-publish@[0-9a-f]{40}", upload[0]), upload[0]


def test_verification_checks_every_identity_it_promises():
    """The checks the header of release.yml promises are all still there."""
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    for promise in (
        'REF_TYPE" = tag',                                  # dispatched on a tag
        'cat-file -t "refs/tags/$TAG")" = tag',             # annotated
        "merge-base --is-ancestor",                         # on main
        '.path == ".github/workflows/ci.yml"',               # the CI workflow
        'merge-base --is-ancestor "$CERTIFIED" "$GITHUB_SHA"',  # of this commit's history
        '"$CHANGED" != "RELEASE_READINESS.md"',            # differing only in the record
        "sha256sum --check --strict SHA256SUMS",            # certified checksums
        'headers["Name"] == distribution',                  # metadata identity
        'report["failed"] == 0',                            # certification passed
        "DISTRIBUTION/$VERSION/json",                       # not already on PyPI
    ):
        assert promise in text, promise
    assert "DISTRIBUTION: plainspeak-next" in text
