#!/usr/bin/env python3
"""Synct de trainingsdatums op de statische You.Manual-salespage vanuit de
centrale datumbron (https://youmanual.talentfirst.nl/api/trainingsdata, die
op zijn beurt de Plug & Pay-checkout leest — de enige plek waar Huub datums
beheert).

Draait dagelijks via cron op de VPS. Faalt de bron of de parse, dan blijft
het bestand ONAANGEROERD (laatste bekende datums blijven staan) en loggen we.
"""

import json
import re
import sys
import urllib.request
from datetime import datetime

BRON = "https://youmanual.talentfirst.nl/api/trainingsdata"
DOEL = "/srv/youmanual-training/index.html"
LOG = "/var/log/trainingsdatums-sync.log"


def log(msg: str) -> None:
    regel = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(regel)
    try:
        with open(LOG, "a") as f:
            f.write(regel + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        with urllib.request.urlopen(BRON, timeout=30) as r:
            data = json.load(r)
    except Exception as e:  # noqa: BLE001 — elke bron-fout = niets doen
        log(f"FOUT bron ophalen: {e} — bestand onaangeroerd")
        return 1

    datums = data.get("datums") or []
    eerst = data.get("eerstvolgende")
    sluit = data.get("inschrijvingSluit")
    if not datums or not eerst or not sluit:
        log("FOUT geen (volledige) datums in bron — bestand onaangeroerd")
        return 1

    lang_alle = " · ".join(d["lang"] for d in datums)

    html = open(DOEL, encoding="utf-8").read()
    origineel = html

    # 1. Aanmeldsectie: "<strong>Eerstvolgende training:</strong> 27 augustus 2026"
    html = re.sub(
        r"(<strong>Eerstvolgende training(?:en)?:</strong> )[^<]+",
        r"\g<1>" + lang_alle,
        html,
    )
    # 2. Hero-microtekst + countdown-kop: "Eerstvolgende training: ..."
    html = re.sub(
        r"(Eerstvolgende training: )[^<]+",
        r"\g<1>" + eerst["lang"],
        html,
    )
    # 3. "Volgende datum: ..."
    html = re.sub(
        r"(Volgende datum: )[^<]+",
        r"\g<1>" + lang_alle,
        html,
    )
    # 4. Countdown-doel (2 dagen vóór de training, 23:59)
    html = re.sub(
        r'data-ct-dt="[^"]*"',
        f'data-ct-dt="{sluit}"',
        html,
    )

    if html == origineel:
        log(f"OK geen wijzigingen (eerstvolgende: {eerst['lang']})")
        return 0

    open(DOEL, "w", encoding="utf-8").write(html)
    log(f"OK bijgewerkt → eerstvolgende: {eerst['lang']}; alle: {lang_alle}; sluit: {sluit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
