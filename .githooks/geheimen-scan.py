#!/usr/bin/env python3
"""geheimen-scan: blokkeert commits met letterlijke geheimen (SEC-INC-2026-017).

Gebruik:
  geheimen-scan.py            scan de staged inhoud (pre-commit)
  geheimen-scan.py --alle     scan alle getrackte bestanden (CI / nulmeting)

Toont nooit een waarde: alleen pad, regel, soort, lengte en sha256-prefix (8).

Wat telt als geheim:
  - JWT's (eyJ...), behalve een JWT met role=anon (die is publiek en zit by
    design in de browserbundel en in publieke storage-URL's)
  - Anthropic/OpenAI-achtige sleutels (sk-...), Stripe (sk_live_, rk_live_, whsec_)
  - ActiveCampaign API-key (72 hex), Google client-secret (GOCSPX-), Google API-key (AIza)
  - Telegram bot-token, GitHub-token (ghp_/gho_/github_pat_), Slack (xox?-), AWS (AKIA)
  - private keys (-----BEGIN ... PRIVATE KEY-----)

Uitzonderingen:
  - een regel met de tekst `geheimen-scan:negeer` wordt overgeslagen
  - een waarde met `xxxx` erin geldt als placeholder
  - nep-sleutels in tests: zet hun sha8 (uit de uitvoer) op een eigen regel in
    .githooks/geheimen-toegestaan.txt (nooit de waarde zelf)
  - SKIP_SECRET_CHECK=1 git commit ...  (noodgeval; meld het aan Alex)
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys

PATRONEN = [
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{16,}")),
    ("anthropic/openai-key", re.compile(r"sk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}")),
    ("stripe-key", re.compile(r"(?:sk|rk)_live_[A-Za-z0-9]{16,}")),
    ("stripe-webhook-secret", re.compile(r"whsec_[A-Za-z0-9]{24,}")),
    ("activecampaign-key", re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{72}(?![0-9a-fA-F])")),
    ("google-client-secret", re.compile(r"GOCSPX-[A-Za-z0-9_-]{20,}")),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("telegram-token", re.compile(r"(?<![0-9])[0-9]{8,10}:AA[A-Za-z0-9_-]{33}")),
    ("github-token", re.compile(r"(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}")),
    ("slack-token", re.compile(r"xox[abpr]-[A-Za-z0-9-]{20,}")),
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")),
]
NEGEER_MARKER = "geheimen-scan:negeer"
BINAIR = re.compile(r"\.(png|jpe?g|gif|webp|ico|pdf|zip|gz|tgz|woff2?|ttf|otf|eot|mp3|mp4|mov|docx?|xlsx?|pptx?|sqlite|db)$", re.I)
MAX_BYTES = 5_000_000


def toegestaan() -> set:
    top = git("rev-parse", "--show-toplevel").decode().strip() or "."
    pad = os.path.join(top, ".githooks", "geheimen-toegestaan.txt")
    try:
        with open(pad) as fh:
            return {r.split("#")[0].strip() for r in fh if r.split("#")[0].strip()}
    except OSError:
        return set()


def sha8(waarde: str) -> str:
    return hashlib.sha256(waarde.encode()).hexdigest()[:8]


def jwt_rol(token: str):
    try:
        deel = token.split(".")[1]
        deel += "=" * (-len(deel) % 4)
        return json.loads(base64.urlsafe_b64decode(deel)).get("role")
    except Exception:
        return None


def git(*args) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=False).stdout


def bestanden(alle: bool):
    if alle:
        uit = git("ls-files", "-z")
    else:
        uit = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [p.decode("utf-8", "replace") for p in uit.split(b"\0") if p]


def inhoud(pad: str, alle: bool):
    if alle:
        try:
            if os.path.getsize(pad) > MAX_BYTES:
                return None
            with open(pad, "rb") as fh:
                data = fh.read()
        except OSError:
            return None
    else:
        data = git("show", f":{pad}")
        if len(data) > MAX_BYTES:
            return None
    if b"\0" in data[:8000]:
        return None
    return data.decode("utf-8", "ignore")


def scan_tekst(tekst: str, vrij=frozenset()):
    """Geeft (regelnummer, soort, lengte, sha8) per vondst."""
    vondsten = []
    for nr, regel in enumerate(tekst.splitlines(), 1):
        if NEGEER_MARKER in regel:
            continue
        for soort, rx in PATRONEN:
            for m in rx.finditer(regel):
                waarde = m.group(0)
                if "xxxx" in waarde.lower() or sha8(waarde) in vrij:
                    continue
                if soort == "jwt":
                    rol = jwt_rol(waarde)
                    if rol == "anon":
                        continue
                    soort_hier = f"jwt(role={rol or 'onbekend'})"
                else:
                    soort_hier = soort
                vondsten.append((nr, soort_hier, len(waarde), sha8(waarde)))
    return vondsten


def main(argv):
    alle = "--alle" in argv
    totaal = 0
    vrij = toegestaan()
    for pad in bestanden(alle):
        if BINAIR.search(pad) or "/node_modules/" in f"/{pad}":
            continue
        tekst = inhoud(pad, alle)
        if tekst is None:
            continue
        for nr, soort, lengte, h in scan_tekst(tekst, vrij):
            print(f"GEHEIM? {pad}:{nr}  {soort}  len={lengte}  sha8={h}")
            totaal += 1
    if totaal:
        print("")
        print(f"geheimen-scan: {totaal} mogelijke geheim(en) gevonden. Haal de waarde uit de code en lees hem uit een env-variabele.")
        print("Vals alarm? Zet 'geheimen-scan:negeer' op die regel. Noodgeval: SKIP_SECRET_CHECK=1 (en meld het aan Alex).")
        if os.environ.get("SKIP_SECRET_CHECK") == "1" and not alle:
            print("SKIP_SECRET_CHECK=1: commit gaat toch door.")
            return 0
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
