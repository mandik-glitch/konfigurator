#!/usr/bin/env python3
"""Nahraje hotove rendery (backups/2026-10-07_produkty_bez_obrazku/<id>_<1|2>.png) do galerie a nahledu produktu (bot4, Robert 2026-10-08).
Jen pro AKTIVNI produkty, ktere porad nemaji zadny obrazek; nic jineho nemeni (active se NEDOTYKA, thumbnail_file jen kdyz je NULL).
Pohled 1 = celni (sort_order -2, hlavni), pohled 2 = 3/4 (-1). Dlazdice 1024^2 pres _nahled_dlazdice. Spusteni jako root: --proved (bez toho jen vypis)."""
import os, shutil, sys, json
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts")); sys.path.insert(0, os.path.join(REPO, "api"))
import _env  # noqa: E402
os.environ.update(_env.load_env())
import _nahled_dlazdice as nd  # noqa: E402
from PIL import Image  # noqa: E402
VYST = os.path.join(REPO, "backups", "2026-10-07_produkty_bez_obrazku")
GAL = os.path.join(REPO, "webapp", "content-files", "gallery-items")
THU = os.path.join(REPO, "webapp", "katalog", "thumbnails")
proved = "--proved" in sys.argv
conn = _env.get_conn(); cur = conn.cursor()
cur.execute("""SELECT sp.id, sp.thumbnail_file FROM shop_products sp WHERE sp.active=1
  AND NOT EXISTS (SELECT 1 FROM shop_product_images i WHERE i.product_id=sp.id)
  AND NOT EXISTS (SELECT 1 FROM content_gallery_items g WHERE g.owner_type='product' AND g.owner_id=sp.id AND g.is_public=1)
  AND NOT EXISTS (SELECT 1 FROM product_turntable_frames f WHERE f.shop_product_id=sp.id AND f.is_active=1)""")
n = 0
for r in cur.fetchall():
    pid = r["id"]; zdroje = [os.path.join(VYST, "%d_%d.png" % (pid, k)) for k in (1, 2)]
    if not all(os.path.isfile(z) for z in zdroje):
        print("PRESKOCENO %d: chybi rendery" % pid); continue
    print(("NAHRAVAM" if proved else "BY NAHRAL"), pid); n += 1
    if not proved: continue
    for k, z in enumerate(zdroje, 1):
        fn = "product-%d_render-bez-obrazku-%d-t1024v2.jpg" % (pid, k)
        nd.uloz_dlazdici(z, os.path.join(GAL, fn))
        cur.execute("INSERT INTO content_gallery_items (owner_type,owner_id,filename,media_type,caption,is_public,sort_order) VALUES ('product',%s,%s,'image',%s,1,%s)",
                    (pid, fn, "Čelní pohled" if k == 1 else "Pohled zprava shora", -2 if k == 1 else -1))
        os.chown(os.path.join(GAL, fn), *[__import__("pwd").getpwnam("www-data").pw_uid] * 2)
    if not r["thumbnail_file"]:
        tf = os.path.join(THU, "product-%d.jpg" % pid)
        with Image.open(os.path.join(GAL, "product-%d_render-bez-obrazku-1-t1024v2.jpg" % pid)) as im:
            im.resize((512, 512), Image.LANCZOS).save(tf, "JPEG", quality=88)
        os.chown(tf, *[__import__("pwd").getpwnam("www-data").pw_uid] * 2)
        cur.execute("UPDATE shop_products SET thumbnail_file=%s WHERE id=%s AND thumbnail_file IS NULL", ("thumbnails/product-%d.jpg" % pid, pid))
    conn.commit()
print("produktu:", n)
