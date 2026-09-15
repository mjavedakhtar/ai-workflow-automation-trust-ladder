"""Optional ATT&CK refresh from the official MITRE GitHub repo only.

This is allow-listed, size-capped, and writes a local cache. It does not scrape
arbitrary websites or send tenant data anywhere.
"""

from __future__ import annotations

import json
import ssl
import urllib.request
from pathlib import Path

ALLOWED = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/index.json"
MAX_BYTES = 2_000_000
OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "mitre_cache.json"


def main() -> None:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        ALLOWED,
        headers={"User-Agent": "trust-ladder-dev/1.0 (allowlisted MITRE index fetch)"},
        method="GET",
    )
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        if resp.status != 200:
            raise SystemExit(f"unexpected status {resp.status}")
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise SystemExit("response too large — aborting")
    payload = json.loads(data.decode())
    OUT.write_text(json.dumps({"source": ALLOWED, "index_keys": list(payload)[:20]}, indent=2))
    print(f"Wrote {OUT} (index ping only; T1486 excerpt remains vendored in mitre_t1486.json)")


if __name__ == "__main__":
    main()
