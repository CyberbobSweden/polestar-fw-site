#!/usr/bin/env python3
"""
Polestar 4 firmware-scraper — JSON-API-version
==============================================
Läser Volvo/Polestars in-car content-API (samma JSON som matar bilens
"Software updates"-skärm och den publika manualsidan). Fördelar mot att
skrapa HTML:

  * Strukturerad JSON — inga rubrik-regexar som kan gå sönder.
  * Ligger FÖRE den publika webbsidan (visar t.ex. 4.2.14 medan sidan toppar 4.2.11).
  * Innehåller feature-/validity-flaggor (MU-koder) som förklarar varför olika
    bilar/marknader/modellår ser olika noteringar.

Skriver docs/data.json (versioner + ändringsloggar, nyast först).

OM URL:EN: endpointen ser ut så här —
  https://incar.volvocars.com/api/in-car-support-content/next/polestar/assets/content/814/UNTIL/26160/en-GB/<hash>.json
  • 814          = modellkod (Polestar 4)
  • UNTIL/26160  = CMS-innehållsversion (ökar för varje release)
  • <hash>       = innehållets hash (ändras för varje release)
Både UNTIL-numret och hashen byts när en ny version publiceras, så för att
alltid få den senaste behöver man upptäcka aktuell URL (se discover_url()
nedan – best effort). Sätt INCAR_URL som miljövariabel för att låsa en URL.

Lokalt:  pip install httpx && python scrape_api.py
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# URL:en du hittade. Byt en-GB mot sv-SE för svenska, eller sätt INCAR_URL.
DEFAULT_URL = os.environ.get(
    "INCAR_URL",
    "https://incar.volvocars.com/api/in-car-support-content/next/polestar/"
    "assets/content/814/UNTIL/26160/en-GB/9a8324b083b45de341e8b1f7dc762135.json",
)
# Publika manualsidan – används av discover_url() för att hitta aktuell API-URL.
MANUAL_PAGE = os.environ.get(
    "MANUAL_PAGE_URL",
    "https://www.polestar.com/us/manual/polestar-4/2026/software-updates/",
)
OUT = Path(__file__).with_name("docs") / "data.json"
_TITLE_VER = re.compile(r"Software Version[:\s]+([^\n]+)")
_VERSION_NUM = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def version_tuple(v: str) -> list[int]:
    m = _VERSION_NUM.search(v or "")
    return [int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)] if m else [0, 0, 0]


def collect_text(node, bag: list[str]) -> None:
    """Plockar rekursivt ut all listItem-/paragraf-text ur den nästlade rich-text-strukturen."""
    if node is None:
        return
    if isinstance(node, str):
        return  # ren text hanteras av föräldern
    if isinstance(node, list):
        for n in node:
            collect_text(n, bag)
        return
    if isinstance(node, dict):
        ntype = node.get("type")
        children = node.get("children")
        if ntype in ("listItem", "paragraph"):
            text = flatten_text(children).strip()
            if text:
                bag.append(text)
            # nästlade underlistor fångas ändå nedan
        if ntype != "title":  # hoppa över rubriken, den blir versionsnamnet
            collect_text(children, bag)


def flatten_text(node) -> str:
    """Slår ihop endast direkt textinnehåll (inte nästlade listItem) till en sträng."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(flatten_text(n) for n in node if isinstance(n, str)
                         or (isinstance(n, dict) and n.get("type") == "text"))
    if isinstance(node, dict):
        if node.get("type") == "text":
            return flatten_text(node.get("children"))
        if node.get("type") in ("unorderedList",):
            return ""  # underlistor hanteras separat av collect_text
        return ""
    return ""


def title_of(seg: dict) -> str | None:
    for child in seg.get("children", []) if isinstance(seg.get("children"), list) else []:
        if isinstance(child, dict) and child.get("type") == "title":
            return flatten_text(child.get("children"))
    return None


def parse_api(data: dict) -> list[dict]:
    doc = data.get("releaseNotesDocument", {})
    grouped: dict[str, dict] = {}

    for seg in doc.get("body", []):
        if not isinstance(seg, dict) or seg.get("subtype") != "release-notes":
            continue
        sw = seg.get("softwareVersion")
        if not sw:
            continue
        cms = seg.get("cmsSoftwareVersion", 0)
        # Gruppera på det stabila softwareVersion-fältet; rubriken ger ev. ett snyggare visningsnamn
        title = title_of(seg) or ""
        m = _TITLE_VER.search(title)
        display = m.group(1).strip() if m else None

        notes: list[str] = []
        collect_text(seg.get("children"), notes)

        key = sw  # stabil nyckel, t.ex. "4.2.9"
        if key not in grouped:
            grouped[key] = {"version": display or f"P{sw}", "num": version_tuple(display or sw),
                            "cms": cms, "notes": []}
        elif display and not grouped[key].get("_titled"):
            grouped[key]["version"] = display
            grouped[key]["num"] = version_tuple(display)
        if display:
            grouped[key]["_titled"] = True
        grouped[key]["cms"] = max(grouped[key]["cms"], cms)
        for n in notes:
            if n not in grouped[key]["notes"]:
                grouped[key]["notes"].append(n)

    for g in grouped.values():
        g.pop("_titled", None)

    versions = list(grouped.values())
    versions.sort(key=lambda x: x["cms"], reverse=True)  # cmsSoftwareVersion är monotont
    return versions


def discover_url() -> str | None:
    """Best effort: leta upp aktuell incar-API-URL i den publika manualsidans källkod."""
    try:
        html = httpx.get(MANUAL_PAGE, timeout=20, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"}).text
    except Exception:
        return None
    m = re.search(r"https://incar\.volvocars\.com/[^\s\"'<>]+?\.json", html)
    return m.group(0) if m else None


def fetch_json(url: str) -> dict:
    r = httpx.get(url, timeout=25, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.json()


def main() -> int:
    url = discover_url() or DEFAULT_URL
    try:
        data = fetch_json(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[fel] kunde inte hämta API: {exc}", file=sys.stderr)
        return 1

    versions = parse_api(data)
    if not versions:
        print("[fel] inga versioner i svaret", file=sys.stderr)
        return 1

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
        "source": url,
        "latest": data.get("untilSoftwareVersion") or versions[0]["version"],
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "versions": versions,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] {len(versions)} versioner. Senaste: {payload['latest']} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
