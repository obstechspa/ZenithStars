"""Catálogo y selección de estrellas para colimar.

El catálogo es el mismo `catalog_full.json` de v1 (HYG v3 + BSC, J2000,
V ≤ 9.0). La búsqueda se hace en J2000: la dirección pedida (alt, az) se lleva
a AR/Dec de la fecha y se des-precesa, y como la precesión es una rotación la
distancia angular no cambia. Solo los candidatos se precesan a la fecha para
calcular su altura y azimut.

"Aislada" = sin otra estrella del catálogo más brillante que `vmag + iso_dmag`
a menos de `iso_arcmin`. El catálogo llega solo a V = 9, así que vecinas más
débiles no se ven: aislada significa "sin vecinas brillantes conocidas".
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from . import astro


class Catalog:
    def __init__(self, stars: list):
        # stars = [[ra_deg, dec_deg, vmag, name, ids], ...] (formato de v1)
        self.stars = stars
        self.vectors = [astro.unit_vector(s[0], s[1]) for s in stars]
        self._grid = defaultdict(list)          # celdas de 1°×1° en (dec, ra)
        for i, s in enumerate(stars):
            self._grid[(math.floor(s[1]), math.floor(s[0]) % 360)].append(i)

    @classmethod
    def from_json(cls, path: Path) -> 'Catalog':
        with open(path, encoding='utf-8') as f:
            return cls(json.load(f))

    def __len__(self):
        return len(self.stars)

    def neighbours(self, i: int, radius_deg: float):
        """Índices a menos de radius_deg (<1°) de la estrella i, sin incluirla."""
        ra, dec = self.stars[i][0], self.stars[i][1]
        cos_r = math.cos(radius_deg * astro.DEG)
        vx, vy, vz = self.vectors[i]
        cos_dec = math.cos(min(89.0, abs(dec) + 1) * astro.DEG)
        span = 180 if abs(dec) > 85 else math.ceil(radius_deg / cos_dec) + 1
        d0, r0 = math.floor(dec), math.floor(ra)
        for dd in (-1, 0, 1):
            for dr in range(-span, span + 1):
                for j in self._grid.get((d0 + dd, (r0 + dr) % 360), ()):
                    if j == i:
                        continue
                    wx, wy, wz = self.vectors[j]
                    if vx * wx + vy * wy + vz * wz >= cos_r:
                        yield j

    def candidates(self, *, lat: float, lon: float, t: datetime,
                   alt: float, az: float, radius: float = 15.0,
                   mag_min: float = 5.0, mag_max: float = 9.0,
                   min_alt: float = 0.0, iso_arcmin: float = 3.0,
                   iso_dmag: float = 2.0, limit: int = 300) -> dict:
        """Estrellas cerca de (alt, az), ordenadas por distancia; la primera
        aislada sobre min_alt se marca como 'best'."""
        jd = astro.julian_date(t)
        lst_deg = astro.lst(t, lon)
        ra_now, dec_now = astro.radec_of_altaz(alt, az, lat, lst_deg)
        tx, ty, tz = astro.unit_vector(*astro.unprecess(ra_now, dec_now, jd))
        cos_r = math.cos(radius * astro.DEG)
        pmat = astro.precession_matrix(jd)

        hits = []
        for i, (s, (x, y, z)) in enumerate(zip(self.stars, self.vectors)):
            if mag_min <= s[2] <= mag_max:
                c = x * tx + y * ty + z * tz
                if c >= cos_r:
                    hits.append((c, i))
        hits.sort(reverse=True)

        out = []
        for c, i in hits:
            s = self.stars[i]
            ra_d, dec_d = astro.from_vector(astro.rotate(pmat, self.vectors[i]))
            s_alt, s_az = astro.altaz(lst_deg - ra_d, dec_d, lat)
            if s_alt < 0:
                continue
            out.append(self._describe(i, s_alt, s_az, c, min_alt, iso_arcmin, iso_dmag))
            if len(out) >= limit:
                break

        best = next((k for k, r in enumerate(out) if r['isolated'] and r['above_limit']), None)
        if best is not None:
            out[best]['best'] = True
        return {'lst': lst_deg, 'target_ra': ra_now, 'target_dec': dec_now,
                'best': best, 'stars': out, 'n_in_radius': len(hits)}

    def band_candidates(self, *, lat: float, lon: float, t: datetime,
                        alt_min: float, alt_max: float, alt_pref: float,
                        az_ref: float | None = None,
                        mag_min: float = 5.0, mag_max: float = 9.0,
                        min_alt: float = 0.0, iso_arcmin: float = 3.0,
                        iso_dmag: float = 2.0, limit: int = 300) -> dict:
        """Estrellas con altura entre alt_min y alt_max, ordenadas por cercanía
        a la altura preferida; la primera aislada sobre min_alt es 'best'.

        Con az_ref (p. ej. el azimut actual de la montura) se ordena por
        distancia angular al punto (alt_pref, az_ref): la elegida queda a la
        altura preferida y con el slew más corto. Sin az_ref, solo por
        |alt - alt_pref|.

        Pensado para monturas alt-az, que no conviene llevar al cenit: cerca de
        90° el eje de azimut tiene que girar cada vez más rápido para seguir.
        """
        jd = astro.julian_date(t)
        lst_deg = astro.lst(t, lon)
        # cenit en J2000: sin(alt) de cada estrella = producto punto con él
        # (la precesión es una rotación, el producto punto no cambia)
        zx, zy, zz = astro.unit_vector(*astro.unprecess(lst_deg, lat, jd))
        s_lo, s_hi = math.sin(alt_min * astro.DEG), math.sin(alt_max * astro.DEG)
        pmat = astro.precession_matrix(jd)

        hits = []
        for i, (s, (x, y, z)) in enumerate(zip(self.stars, self.vectors)):
            if mag_min <= s[2] <= mag_max and s_lo <= x * zx + y * zy + z * zz <= s_hi:
                ra_d, dec_d = astro.from_vector(astro.rotate(pmat, self.vectors[i]))
                s_alt, s_az = astro.altaz(lst_deg - ra_d, dec_d, lat)
                if az_ref is None:
                    score = abs(s_alt - alt_pref)
                else:   # la separación en el cielo es la misma en (az, alt) que en (ra, dec)
                    score = astro.separation(az_ref, alt_pref, s_az, s_alt)
                hits.append((score, i, s_alt, s_az))
        hits.sort()

        out = []
        for score, i, s_alt, s_az in hits[:limit]:
            r = self._describe(i, s_alt, s_az, 1.0, min_alt, iso_arcmin, iso_dmag)
            r['sep'] = round(score, 3)
            out.append(r)

        best = next((k for k, r in enumerate(out) if r['isolated'] and r['above_limit']), None)
        if best is not None:
            out[best]['best'] = True
        return {'lst': lst_deg, 'best': best, 'stars': out, 'n_in_radius': len(hits)}

    def _describe(self, i, s_alt, s_az, cos_sep, min_alt, iso_arcmin, iso_dmag) -> dict:
        s = self.stars[i]
        near = None
        for j in self.neighbours(i, iso_arcmin / 60.0):
            o = self.stars[j]
            if o[2] < s[2] + iso_dmag and (near is None or o[2] < near[1]):
                near = (astro.separation(s[0], s[1], o[0], o[1]) * 60.0, o[2])
        return {
            'index': i,
            'name': s[3] or (s[4].split(' · ')[0] if s[4] else f'#{i}'),
            'ids': s[4], 'vmag': s[2], 'ra2000': s[0], 'dec2000': s[1],
            'alt': round(s_alt, 3), 'az': round(s_az, 3),
            'sep': round(math.acos(max(-1.0, min(1.0, cos_sep))) / astro.DEG, 3),
            'above_limit': s_alt >= min_alt,
            'isolated': near is None,
            'neighbour': None if near is None else
                         {'sep_arcmin': round(near[0], 2), 'vmag': near[1]},
            'best': False,
        }
