"""
Jednorazovy import fotogalerie z logiman.cz - bot2, 2026-07-25.

Robert: "cerpej z fotogalerii logiman.cz rovnou tam nacucni ty obrazky".
Stahne vsechny obrazky z obou verejnych galerii na logiman.cz a ulozi je
pres gallery.import_image_from_url() (STEJNA SEO logika jako rucni admin
upload - viz gallery.py docstring).

Dedup: pokud se stejna zdrojova URL objevi na obou strankach (galerie
"Foto realizace stolu" duplikuje cast obsahu z "Foto vestavby dodavek" -
overeno rucne), obrazek se stahne jen JEDNOU, do kategorie stranky, na
ktere se objevil DRIV (poradi PAGES nize).

Spusteni: cd /opt/konfigurator/api && venv/bin/python3 import_logiman_gallery.py
"""
import hashlib
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# app.py cte DB/SMTP udaje jen z environment promennych (zadny
# python-dotenv), ktere za normalniho provozu nastavuje systemd
# (EnvironmentFile=/opt/konfigurator/api/.env) - pri primem spusteni
# tohoto skriptu (mimo gunicorn) je potreba .env nacist rucne PRED
# "import app", jinak app.py spadne zpet na sve zabudovane vychozi
# hodnoty (jina/neexistujici DB). .env obsahuje hodnoty s mezerami
# (napr. SMTP_FROM), takze ho nejde bezpecne "sourcovat" primo v bashi -
# parsujeme ho proto rucne (jen prvni "=" je oddelovac klice/hodnoty).
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

import app  # noqa: E402 - vedlejsi efekt: registruje vse vc. gallery.py
import gallery  # noqa: E402

PAGES = [
    ("https://www.logiman.cz/foto-vestavby-dodavek/", "vestavby_dodavek"),
    ("https://www.logiman.cz/foto-realizace-stolu/", "realizace_stolu"),
]

HREF_RE = re.compile(r'href="(/user/documents/upload/gallery/[^"]+?\.(?:jpg|jpeg|png|gif))"', re.IGNORECASE)
IMG_RE = re.compile(
    r'src="(https://cdn\.myshoptet\.com/usr/www\.logiman\.cz/user/documents/upload/gallery/[^"]+?)"',
    re.IGNORECASE,
)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (konfigurator-gallery-import)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def unescape_url(u):
    return u.replace("&amp;", "&")


def collect_urls_for_page(page_url):
    html = fetch(page_url)
    urls = set()
    for h in HREF_RE.findall(html):
        urls.add("https://www.logiman.cz" + unescape_url(h))
    for src in IMG_RE.findall(html):
        name = src.rsplit("/", 1)[-1]
        if "_small." not in name.lower():
            continue
        full_name = re.sub(r"_small\.", ".", name, flags=re.IGNORECASE)
        urls.add("https://www.logiman.cz/user/documents/upload/gallery/" + unescape_url(full_name))
    return urls


def main():
    seen = set()
    plan = []
    for page_url, category in PAGES:
        urls = collect_urls_for_page(page_url)
        print(f"{category}: {len(urls)} kandidatnich URL na strance {page_url}")
        new_here = 0
        for u in sorted(urls):
            if u in seen:
                continue
            seen.add(u)
            plan.append((category, u))
            new_here += 1
        print(f"{category}: {new_here} novych (po odstraneni duplicit sdilenych s jinou kategorii)")
        time.sleep(0.3)

    print(f"CELKEM K IMPORTU: {len(plan)}")

    limit = os.environ.get("GALLERY_IMPORT_LIMIT")
    if limit:
        plan = plan[: int(limit)]
        print(f"(GALLERY_IMPORT_LIMIT={limit} - omezeno na prvnich {len(plan)})")

    conn = app.get_conn()
    created, failed, skipped_dupe = 0, 0, 0
    fail_list = []
    seen_hashes = {}  # content md5 -> filename uz ulozeny (dedup napric obema strankami,
                       # kdyz stejna fotka ma na kazde strance jinak prefixovany nazev)
    try:
        with conn.cursor() as cur:
            for i, (category, url) in enumerate(plan, 1):
                try:
                    data = gallery.fetch_url_bytes(url)
                    digest = hashlib.md5(data).hexdigest()
                    if digest in seen_hashes:
                        skipped_dupe += 1
                        print(f"[{i}/{len(plan)}] DUPE {category:20s} {url} (stejny obsah jako {seen_hashes[digest]})")
                        continue
                    orig_name = url.rsplit("/", 1)[-1].split("?")[0]
                    new_id, filename = gallery.save_gallery_bytes(cur, category, data, orig_name, url)
                    seen_hashes[digest] = filename
                    created += 1
                    print(f"[{i}/{len(plan)}] OK   {category:20s} {filename}")
                except Exception as e:
                    failed += 1
                    fail_list.append((category, url, str(e)))
                    print(f"[{i}/{len(plan)}] FAIL {category:20s} {url} -> {e}")
        conn.commit()
    finally:
        conn.close()

    print(f"\nHOTOVO: created={created} failed={failed} skipped_dupe(stejny obsah)={skipped_dupe}")
    if fail_list:
        print("Neuspesne:")
        for cat, url, err in fail_list:
            print(f"  {cat}: {url} ({err})")


if __name__ == "__main__":
    main()
