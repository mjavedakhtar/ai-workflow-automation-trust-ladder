"""Allow-list script linter. Default-deny; model intent is irrelevant."""

from __future__ import annotations

import re

ALLOWED = {
    "get-process",
    "get-service",
    "get-netfirewallprofile",
    "set-netfirewallprofile",
    "test-path",
    "write-output",
    "get-filehash",
    "start-mpwdo",
    "update-mpsignature",
    "isolate-endpoint",
    "get-backup",
    "restore-backup",
}

FORBIDDEN = [
    "remove-item",
    "format-volume",
    "rm -rf",
    "del /",
    "reg delete",
    "stop-computer",
    "clear-disk",
    "format.com",
    "cipher /w",
    "invoke-expression",
    "iex ",
    "downloadstring",
    "start-bitstransfer",
]


def lint(script: str) -> dict:
    text = script or ""
    lowered = text.lower()
    for token in FORBIDDEN:
        if token in lowered:
            return {
                "passed": False,
                "blocked_token": token,
                "detail": f"Allow-list check BLOCKED — forbidden command `{token}`.",
            }
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]+", text)
    cmdlets = [t for t in tokens if "-" in t]
    unknown = [c for c in cmdlets if c.lower() not in ALLOWED and c.lower() not in {f.replace(" ", "") for f in FORBIDDEN}]
    # Isolation/restore are executed via adapters, not free-form scripts. Empty script is fine.
    if not text.strip():
        return {"passed": True, "blocked_token": None, "detail": "No script — adapter-only actions."}
    if unknown:
        return {
            "passed": False,
            "blocked_token": unknown[0],
            "detail": f"Allow-list check BLOCKED — `{unknown[0]}` is not on the certified allow-list.",
        }
    return {"passed": True, "blocked_token": None, "detail": "Allow-list check PASSED."}
