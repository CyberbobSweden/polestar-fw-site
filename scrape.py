#!/usr/bin/env python3
"""
Scrapar Polestars officiella Polestar 4 release-notes-sida och skriver
docs/data.json (versioner + ändringsloggar, nyast först). Körs av GitHub
Actions på schema – sidan i docs/ läser sedan JSON-filen.

Ingen inloggning krävs: detta är publik flott-data (vad Polestar släppt),
inte din specifika bils version.

Lokalt:  pip install httpx beautifulsoup4 && python scrape.py
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

SOURCE_URL = os.environ.get(
    "FLEET_SOURCE_URL",
    "https://www.polestar.com/us/manual/polestar-4/2025/software-updates/",
)
OUT = Path(__file__).with_name("docs") / "data.json"

_HEADING = re.compile(r"Updates?\s+[Ii]n\s+Software Version[:\s]+([^\n]+)")
_VERSION_NUM = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def version_tuple(v: str) -> list[int]:
    m = _VERSION_NUM.search(v or "")
    return [int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)] if m else [0, 0, 0]


def parse_versions(text: str) -> list[dict]:
    """Dela texten på versionsrubriker; allt fram till nästa rubrik = den versionens noteringar."""
    headings = list(_HEADING.finditer(text))
    out: list[dict] = []
    for i, h in enumerate(headings):
        version = h.group(1).strip().rstrip(":").strip()
        body_start = h.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[body_start:body_end]

        notes: list[str] = []
        for raw in body.splitlines():
            line = raw.strip().lstrip("-*•#").strip()
            # hoppa över tomrader, fotnoter och rena sub-rubriker som blir egna stycken
            if not line or re.fullmatch(r"\d+\.\s.*", raw.strip()):
                continue
            notes.append(line)
        out.append({"version": version, "num": version_tuple(version), "notes": notes})
    # nyast först
    out.sort(key=lambda x: x["num"], reverse=True)
    return out


def fetch(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (PolestarFwTracker/1.0)"}
    resp = httpx.get(url, timeout=25, follow_redirects=True, headers=headers)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser").get_text("\n")


def main() -> int:
    try:
        text = fetch(SOURCE_URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[fel] kunde inte hämta sidan: {exc}", file=sys.stderr)
        return 1

    versions = parse_versions(text)
    if not versions:
        print("[fel] inga versioner tolkades – sidan kan ha ändrat struktur", file=sys.stderr)
        return 1

    # bevara first_seen om vi redan har en gammal data.json
    prev = {}
    if OUT.exists():
        try:
            for v in json.loads(OUT.read_text(encoding="utf-8")).get("versions", []):
                prev[v["version"]] = v.get("first_seen")
        except (json.JSONDecodeError, OSError):
            pass

    today = datetime.now(timezone.utc).date().isoformat()
    for v in versions:
        v["first_seen"] = prev.get(v["version"]) or today

    payload = {
        "source": SOURCE_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latest": versions[0]["version"],
        "versions": versions,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] {len(versions)} versioner. Senaste: {versions[0]['version']} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
