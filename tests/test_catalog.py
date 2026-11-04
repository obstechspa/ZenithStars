import unittest
from datetime import datetime, timezone
from pathlib import Path

from zenithstars import astro
from zenithstars.catalog import Catalog

ROOT = Path(__file__).resolve().parent.parent
T = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
SITE = dict(lat=-30.4705, lon=-70.765, t=T)


class TestCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = Catalog.from_json(ROOT / 'catalog_full.json')

    def test_candidates_respect_filters(self):
        r = self.cat.candidates(**SITE, alt=90, az=0, radius=10, mag_min=6, mag_max=8, min_alt=30)
        self.assertGreater(len(r['stars']), 10)
        seps = [s['sep'] for s in r['stars']]
        self.assertEqual(seps, sorted(seps))
        for s in r['stars']:
            self.assertTrue(6 <= s['vmag'] <= 8 and s['sep'] <= 10 and s['alt'] >= 0)
        b = r['stars'][r['best']]
        self.assertTrue(b['isolated'] and b['above_limit'] and b['best'])

    def test_alt_matches_independent_computation(self):
        r = self.cat.candidates(**SITE, alt=50, az=135, radius=5, min_alt=0)
        for s in r['stars'][:20]:
            ra, dec = astro.precess(s['ra2000'], s['dec2000'], astro.julian_date(T))
            alt, az = astro.altaz(astro.lst(T, SITE['lon']) - ra, dec, SITE['lat'])
            self.assertAlmostEqual(s['alt'], alt, places=2)
            # la distancia a la dirección pedida, recalculada en horizontales
            d = astro.separation(az, alt, 135, 50)
            self.assertAlmostEqual(s['sep'], d, places=2)

    def test_isolation_finds_known_pair(self):
        # buscar un par real: la primera estrella con vecina brillante a <3'
        r = self.cat.candidates(**SITE, alt=60, az=0, radius=30, iso_arcmin=3, iso_dmag=2)
        pair = next(s for s in r['stars'] if not s['isolated'])
        self.assertLess(pair['neighbour']['sep_arcmin'], 3)
        self.assertLess(pair['neighbour']['vmag'], pair['vmag'] + 2)
        self.assertNotEqual(r['best'], r['stars'].index(pair))


if __name__ == '__main__':
    unittest.main()
