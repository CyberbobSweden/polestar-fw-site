# Polestar 4 — Firmware-tracker (GitHub Pages)

En liten, gratis sida som visar vilka mjukvaruversioner Polestar släppt till
Polestar 4, med ändringsloggar. Den hämtar Polestars **officiella** release
notes automatiskt och kräver ingen server och ingen inloggning.

**Så funkar det:** GitHub Actions kör `scrape_api.py` var 6:e timme → läser
Volvo/Polestars in-car content-API (samma JSON som matar bilens "Software
updates"-skärm) → sparar `docs/data.json` → den statiska sidan visar datan.
Ingen server, ingen inloggning.

> Den här källan ligger **före** den publika manualsidan — den visade 4.2.14
> medan webbsidan fortfarande toppade på 4.2.11.

```
repo/
├─ scrape_api.py             # läser in-car JSON-API:t (primär)
├─ scrape.py                 # äldre HTML-skrapa (reserv)
├─ requirements.txt
├─ docs/
│  ├─ index.html             # själva sidan (GitHub Pages servar denna)
│  └─ data.json              # genereras av scrapern
└─ .github/workflows/update.yml   # schemalägger scrapern
```

### Om API-URL:en

Endpointen ser ut så här:
```
https://incar.volvocars.com/api/in-car-support-content/next/polestar/assets/content/814/UNTIL/26160/en-GB/<hash>.json
```
- `814` = modellkod (Polestar 4)
- `UNTIL/26160` = CMS-innehållsversion (ökar för varje release)
- `<hash>` = innehållets hash (byts för varje release)
- `en-GB` = språk (byt mot `sv-SE` för svenska)

Både UNTIL-numret och hashen ändras när Polestar publicerar en ny version.
`scrape_api.py` försöker därför först **upptäcka aktuell URL** automatiskt ur
den publika manualsidans källkod (`discover_url()`), och faller annars tillbaka
på URL:en i `DEFAULT_URL`. Vill du låsa en URL: sätt miljövariabeln `INCAR_URL`.

## Testa lokalt först (valfritt)

```bash
pip install httpx beautifulsoup4
python scrape.py                 # skriver docs/data.json
cd docs && python -m http.server # öppna http://localhost:8000
```

## Lägg upp som sida på GitHub — steg för steg

1. **Skapa ett repo** på github.com (t.ex. `polestar4-firmware`). Publikt går bra.
2. **Ladda upp filerna.** Antingen via webben (knappen *Add file → Upload files*,
   dra in hela mappen) eller via terminal:
   ```bash
   git init
   git add .
   git commit -m "Polestar 4 firmware-tracker"
   git branch -M main
   git remote add origin https://github.com/DITT-NAMN/polestar4-firmware.git
   git push -u origin main
   ```
3. **Aktivera GitHub Pages:** repo → **Settings → Pages**.
   Under *Build and deployment* välj **Source: Deploy from a branch**,
   **Branch: `main`**, mapp: **`/docs`**. Spara.
4. **Aktivera Actions:** gå till fliken **Actions**, godkänn att workflows får
   köra. Öppna *"Update Polestar 4 firmware data"* och tryck **Run workflow** en
   gång för att fylla `data.json` direkt (annars väntar den till nästa schemalagda körning).
5. Klart. Din sida ligger på:
   ```
   https://DITT-NAMN.github.io/polestar4-firmware/
   ```
   (Kan ta någon minut första gången.)

## Vill du ha svenska release notes?

Polestar har en svensk variant av sidan. Sätt en miljövariabel i workflowen, eller
ändra default-URL:en överst i `scrape.py` från `/us/` till `/se/`:
```
https://www.polestar.com/se/manual/polestar-4/2025/software-updates/
```

## Få en notis när ny version släpps

Sidan visar alltid det senaste, men vill du ha en push kan du lägga till ett steg
i `update.yml` som postar till t.ex. [ntfy.sh](https://ntfy.sh) när `data.json`
ändrats. Säg till så lägger jag in det.

## Din egen bils version (inte bara flottan)

Den här sidan visar vad Polestar **släppt** — inte vilken version just din bil kör.
Det senare kräver inloggning (Polestar ID) via `pypolestar` och passar bäst att
köra privat (lokalt eller med GitHub Actions *secrets*), eftersom det inte ska
ligga publikt. Filerna `polestar_fw_tracker.py` / `polestar_tracker_backend.py`
gör det. På Polestar 4 kan API-inloggningen vara petig (kinesisk plattform,
ev. PKCE-auth) — fungerar den inte direkt går flott-sidan ändå.

---
Datan kommer från Polestars officiella manual. Detta projekt är inte anslutet
till Polestar.
