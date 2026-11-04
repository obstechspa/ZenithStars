"""Búsqueda por banda de altitud (monturas alt-az: evitar el cenit)."""
import unittest
from datetime import datetime, timezone
from pathlib import Path

from zenithstars import astro
from zenithstars.catalog import Catalog

ROOT = Path(__file__).resolve().parent.parent
SITE = dict(lat=-30.47, lon=-70.76, t=datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc))


class TestBand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = Catalog.from_json(ROOT / 'catalog_full.json')

    def band(self, **kw):
        args = dict(alt_min=70, alt_max=85, alt_pref=80, mag_min=6, mag_max=8, min_alt=30, **SITE)
        args.update(kw)
        return self.cat.band_candidates(**args)

    def test_filters_altitude_and_magnitude(self):
        r = self.band()
        self.assertGreater(r['n_in_radius'], 100)
        for s in r['stars']:
            self.assertTrue(70 - 1e-6 <= s['alt'] <= 85 + 1e-6, s)
            self.assertTrue(6 <= s['vmag'] <= 8, s)

    def test_altitude_matches_full_computation(self):
        # el prefiltro por producto punto con el cenit J2000 debe coincidir con alt/az de la fecha
        jd, lst = astro.julian_date(SITE['t']), astro.lst(SITE['t'], SITE['lon'])
        for s in self.band(alt_min=40, alt_max=88)['stars'][:50]:
            ra, dec = astro.precess(s['ra2000'], s['dec2000'], jd)
            alt, az = astro.altaz(lst - ra, dec, SITE['lat'])
            self.assertAlmostEqual(alt, s['alt'], places=2)

    def test_best_is_isolated_and_closest_to_preferred(self):
        r = self.band(az_ref=None)
        best = r['stars'][r['best']]
        self.assertTrue(best['best'] and best['isolated'] and best['above_limit'])
        self.assertLess(abs(best['alt'] - 80), 1.0)
        scores = [s['sep'] for s in r['stars']]
        self.assertEqual(scores, sorted(scores))

    def test_azimuth_reference_pulls_best_towards_it(self):
        for az in (0, 90, 180, 270):
            r = self.band(az_ref=az)
            best = r['stars'][r['best']]
            self.assertLess(abs((best['az'] - az + 180) % 360 - 180), 15, (az, best))

    def test_band_below_limit_has_no_best(self):
        r = self.band(alt_min=10, alt_max=25, alt_pref=20)
        self.assertTrue(r['stars'])
        self.assertIsNone(r['best'])
        self.assertFalse(any(s['above_limit'] for s in r['stars']))


if __name__ == '__main__':
    unittest.main()
