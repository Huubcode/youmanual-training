"""Localize all images in index.html — download to images/ and rewrite URLs."""
import hashlib
import re
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

HTML = Path("index.html")
IMG_DIR = Path("images")

URL_RE = re.compile(
    r'https?://[^\s"\'<>)]+?\.(?:png|jpg|jpeg|gif|webp|svg|ico)(?:\?[^\s"\'<>)]*)?',
    re.I,
)


def filename_for(url: str, basename_counts: Counter) -> str:
    path = urllib.parse.urlparse(url).path
    base = Path(path).name
    if basename_counts[base] <= 1:
        return base
    # collision — prefix with short hash of full URL
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f"{h}-{base}"


def main() -> None:
    html = HTML.read_text()
    urls = sorted(set(URL_RE.findall(html)))
    print(f"{len(urls)} unieke image-URLs gevonden")

    # compute basename collisions
    basename_counts = Counter(Path(urllib.parse.urlparse(u).path).name for u in urls)

    IMG_DIR.mkdir(exist_ok=True)

    mapping = {}  # remote URL -> local relative path
    failed = []
    for i, url in enumerate(urls, 1):
        fname = filename_for(url, basename_counts)
        dest = IMG_DIR / fname
        mapping[url] = f"images/{fname}"
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{i:3d}/{len(urls)}] skip (bestaat) {fname}")
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            dest.write_bytes(data)
            print(f"[{i:3d}/{len(urls)}] OK   {len(data):>8d} B  {fname}")
        except Exception as e:
            print(f"[{i:3d}/{len(urls)}] FAIL {url} -> {e}")
            failed.append(url)

    if failed:
        print(f"\n{len(failed)} downloads mislukt — sla HTML-rewrite over voor deze URLs")

    # rewrite HTML — longest URLs first to avoid partial-replace
    new_html = html
    replaced = 0
    for url in sorted(mapping, key=len, reverse=True):
        if url in failed:
            continue
        count = new_html.count(url)
        if count:
            new_html = new_html.replace(url, mapping[url])
            replaced += count

    HTML.write_text(new_html)
    print(f"\n{replaced} URL-occurrences vervangen in index.html")

    total = sum(p.stat().st_size for p in IMG_DIR.iterdir() if p.is_file())
    print(f"Totaal images/: {total / 1024 / 1024:.1f} MB in {len(list(IMG_DIR.iterdir()))} files")


if __name__ == "__main__":
    main()
