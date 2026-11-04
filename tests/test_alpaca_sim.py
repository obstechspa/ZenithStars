"""Integración contra un simulador Alpaca (OmniSim). Se salta si no hay uno:
    ZS_ALPACA_URL=http://127.0.0.1:5000 python -m unittest tests.test_alpaca_sim
"""
import os
import time
import unittest

from zenithstars import astro
from zenithstars.mount import AlpacaMount, MountError

URL = os.environ.get('ZS_ALPACA_URL')


@unittest.skipUnless(URL, 'ZS_ALPACA_URL no definido')
class TestAlpacaSim(unittest.TestCase):
    def setUp(self):
        self.m = AlpacaMount(URL, int(os.environ.get('ZS_ALPACA_DEVICE', 0)))
        self.m.connect()
        if self.m.get('AtPark'):
            self.m.call('Unpark')

    def wait(self, timeout=90):
        t0 = time.time()
        while self.m.get('Slewing') and time.time() - t0 < timeout:
            time.sleep(0.5)

    def test_slew_lands_on_sent_coordinates(self):
        lat, lon = self.m.get('SiteLatitude'), self.m.get('SiteLongitude')
        t = astro.utcnow()
        ra, dec = astro.radec_of_altaz(70, 200, lat, astro.lst(t, lon))
        self.m.slew(ra / 15, dec)
        self.wait()
        err = astro.separation(self.m.get('RightAscension') * 15, self.m.get('Declination'), ra, dec)
        self.assertLess(err * 3600, 10)
        self.assertTrue(self.m.get('Tracking'))

    def test_refuses_while_parked(self):
        self.m.call('Park')
        self.wait()
        with self.assertRaisesRegex(MountError, 'estacionada'):
            self.m.slew(1.0, -30.0)
        self.m.call('Unpark')


if __name__ == '__main__':
    unittest.main()
