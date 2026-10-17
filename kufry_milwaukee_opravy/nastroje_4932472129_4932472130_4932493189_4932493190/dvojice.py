#!/usr/bin/env python3
"""IoU a trojice foto | model | překryv. Použití: dvojice.py <foto.jpg> <model.png> <maska.png> <výstup.png> [json_vystup]
IoU: obrys fotografie = jas < 245 (jako v kontrole John v6, bez vyplňování děr), obrys modelu = tmavé pixely siluetového renderu."""
import sys, json
import numpy as np
from PIL import Image, ImageDraw
foto, model, maska, out = sys.argv[1:5]
F = Image.open(foto).convert('RGB'); M = Image.open(model).convert('RGB'); S = Image.open(maska).convert('L')
if M.size != F.size: M = M.resize(F.size)
if S.size != F.size: S = S.resize(F.size)
fm = np.array(F.convert('L')) < 245
mm = np.array(S) < 128
I = (fm & mm).sum(); U = (fm | mm).sum(); iou = I / U
ov = np.array(F).astype(float) * 0.55 + 70
ov[fm & ~mm] = [255, 40, 40]      # jen fotka (červená)
ov[~fm & mm] = [40, 90, 255]      # jen model (modrá)
ov = Image.fromarray(ov.astype(np.uint8))
W, H = F.size
o = Image.new('RGB', (W * 3, H), (255, 255, 255)); o.paste(F, (0, 0)); o.paste(M, (W, 0)); o.paste(ov, (2 * W, 0))
d = ImageDraw.Draw(o); d.text((8, 8), 'foto', fill=(255, 0, 255)); d.text((W + 8, 8), 'model', fill=(255, 0, 255)); d.text((2 * W + 8, 8), f'IoU {iou:.4f}  (cervena: jen foto, modra: jen model)', fill=(255, 0, 255))
o.save(out)
if len(sys.argv) > 5: json.dump({'iou': round(float(iou), 4), 'px_jen_foto': int((fm & ~mm).sum()), 'px_jen_model': int((~fm & mm).sum())}, open(sys.argv[5], 'w'))
print(f'IoU {iou:.4f} jen_foto {(fm & ~mm).sum()} jen_model {(~fm & mm).sum()}')
