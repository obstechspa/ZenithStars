import math
import unittest
from datetime import datetime, timezone

from zenithstars import astro


class TestAstro(unittest.TestCase):
    def test_gmst_meeus_12b(self):
        # 1987-04-10 19:21:00 UT → 8h34m57.0896s
        g = astro.gmst(datetime(1987, 4, 10, 19, 21, tzinfo=timezone.utc))
        self.assertAlmostEqual(g / 15 * 3600, (8 * 3600 + 34 * 60 + 57.0896), delta=0.01)

    def test_precession_meeus_21b(self):
        # θ Persei J2000 → 2028-11-13.19, con movimiento propio aplicado a mano
        jd = 2462088.69
        yrs = (jd - astro.JD_J2000) / 365.25
        ra0 = (2 + 44 / 60 + (11.986 + 0.03425 * yrs) / 3600) * 15
        de0 = 49 + 13 / 60 + (42.48 - 0.0895 * yrs) / 3600
        ra, de = astro.precess(ra0, de0, jd)
        self.assertLess(astro.separation(ra, de, (2 + 46 / 60 + 11.331 / 3600) * 15,
                                         49 + 20 / 60 + 54.54 / 3600) * 3600, 0.05)
        r2, d2 = astro.unprecess(ra, de, jd)
        self.assertLess(astro.separation(r2, d2, ra0, de0) * 3600, 1e-6)

    def test_mount_systems(self):
        t = datetime(2026, 11, 4, tzinfo=timezone.utc)
        self.assertEqual(astro.to_mount_system(10.0, -30.0, 2, t), (10.0, -30.0))
        jnow = astro.to_mount_system(10.0, -30.0, 1, t)
        sep = astro.separation(10.0, -30.0, *jnow)
        self.assertTrue(0.3 < sep < 0.4, sep)                 # ~50"/año × 26.8 años

    def test_zenith_and_roundtrip(self):
        ra, dec = astro.radec_of_altaz(90, 0, -30.47, 123.4)
        self.assertAlmostEqual(dec, -30.47, places=9)
        self.assertAlmostEqual(ra, 123.4, places=9)
        for alt, az in [(45, 0), (30, 90), (60, 200), (10, 300)]:
            ra, dec = astro.radec_of_altaz(alt, az, -30.0, 77.0)
            a2, z2 = astro.altaz(77.0 - ra, dec, -30.0)
            self.assertAlmostEqual(a2, alt, places=8)
            self.assertAlmostEqual((z2 - az + 180) % 360 - 180, 0, places=8)

    def test_azimuth_convention(self):
        # desde el hemisferio sur, una estrella al este del meridiano (HA<0) tiene az ~90
        alt, az = astro.altaz(-60, 0.0, -30.0)
        self.assertTrue(60 < az < 120, az)
        self.assertTrue(math.isclose(astro.altaz(0, -30.0, -30.0)[0], 90.0))


if __name__ == '__main__':
    unittest.main()
