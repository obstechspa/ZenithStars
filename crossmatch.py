import csv, json, math
from collections import defaultdict

# ── Cargar catálogo existente
with open('catalog.json', encoding='utf-8') as f:
    existing = json.load(f)

print(f'Catálogo existente: {len(existing)} estrellas')
print(f'Vmag existente: {min(s["vmag"] for s in existing):.2f} - {max(s["vmag"] for s in existing):.2f}')

# ── Cargar HYG (ra en grados, dec en grados, mag = visual)
hyg_stars = []
with open('hygdata_v3.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            mag = float(row['mag'])
            ra  = float(row['ra'])
            dec = float(row['dec'])
            if mag < 0 or mag > 9.0:
                continue
            hyg_stars.append({
                'name': row['proper'].strip(),
                'hr':   ('HR ' + row['hr'])  if row['hr']  else '',
                'hd':   ('HD ' + row['hd'])  if row['hd']  else '',
                'hip':  ('HIP '+ row['hip']) if row['hip'] else '',
                'ra':   round(ra * 15.0, 6),   # horas -> grados
                'dec':  round(dec, 6),
                'vmag': round(mag, 2),
            })
        except Exception:
            pass

print(f'HYG filtrado (mag 0-9): {len(hyg_stars)} estrellas')

# ── Crossmatch por posición (tolerancia 0.05°)
TOL = 0.05

def ang_dist(ra1, dec1, ra2, dec2):
    cos_d = (
        math.sin(math.radians(dec1)) * math.sin(math.radians(dec2)) +
        math.cos(math.radians(dec1)) * math.cos(math.radians(dec2)) *
        math.cos(math.radians(ra1 - ra2))
    )
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_d))))

# Grid de 1° para acelerar búsqueda
grid = defaultdict(list)
for s in existing:
    key = (round(s['ra']), round(s['dec']))
    grid[key].append(s)

def find_match(ra, dec):
    for dr in [-1, 0, 1]:
        for dd in [-1, 0, 1]:
            for s in grid[(round(ra) + dr, round(dec) + dd)]:
                if ang_dist(ra, dec, s['ra'], s['dec']) < TOL:
                    return s
    return None

# Fusionar
merged = list(existing)
added = 0
for s in hyg_stars:
    if find_match(s['ra'], s['dec']) is None:
        merged.append(s)
        added += 1

print(f'Estrellas nuevas añadidas: {added}')
print(f'Total catálogo fusionado:  {len(merged)}')
print(f'Vmag fusionado: {min(s["vmag"] for s in merged):.2f} - {max(s["vmag"] for s in merged):.2f}')

print('\nDistribución por magnitud:')
for lo, hi in [(0, 2), (2, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 9.1)]:
    count = sum(1 for s in merged if lo <= s['vmag'] < hi)
    print(f'  mag {lo:.0f}-{hi:.0f}: {count}')

# Convertir a formato compacto: [ra, dec, vmag, name, ids]
compact = []
for s in merged:
    name = s.get('name') or ''
    ids  = ' · '.join(filter(None, [s.get('hr',''), s.get('hd',''), s.get('hip','')]))
    compact.append([s['ra'], s['dec'], s['vmag'], name, ids])

with open('catalog_full.json', 'w', encoding='utf-8') as f:
    json.dump(compact, f, separators=(',',':'), ensure_ascii=False)

import os
size = os.path.getsize('catalog_full.json')
print(f'\ncatalog_full.json guardado — {size/1024/1024:.1f} MB, formato compacto [ra,dec,vmag,name,ids]')
