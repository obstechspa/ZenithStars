"""Al llegar al objetivo la montura tiene que quedar trackeando (salvo abort)."""
import threading
import time
import unittest

from zenithstars.mount import Mount


class FakeMount(Mount):
    """Slew de `duration` s; con drops_tracking imita drivers que apagan el
    tracking al terminar el movimiento."""

    def __init__(self, duration=0.3, drops_tracking=True, can_async=True):
        super().__init__()
        self.ARRIVAL_POLL_S = 0.02
        self.props = {'AtPark': False, 'Slewing': False, 'Tracking': False,
                      'CanSetTracking': True, 'CanSlewAsync': can_async}
        self.duration, self.drops_tracking = duration, drops_tracking
        self.tracking_writes = []

    def get(self, prop):
        return self.props[prop]

    def put(self, prop, value):
        self.props[prop] = value
        if prop == 'Tracking':
            self.tracking_writes.append(value)

    def call(self, method, *args):
        if method in ('SlewToCoordinatesAsync', 'SlewToCoordinates'):
            self.props['Slewing'] = True
            done = threading.Event()

            def finish():
                time.sleep(self.duration)
                if self.props['Slewing']:          # no abortado
                    self.props['Slewing'] = False
                    if self.drops_tracking:
                        self.props['Tracking'] = False
                done.set()
            threading.Thread(target=finish, daemon=True).start()
            if method == 'SlewToCoordinates':
                done.wait()
        elif method == 'AbortSlew':
            self.props['Slewing'] = False
            self.props['Tracking'] = False         # como PWI4

    def wait_arrival(self, timeout=3):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.arrival and self.arrival['state'] != 'moving':
                return self.arrival
            time.sleep(0.02)
        return self.arrival


class TestTrackingOnArrival(unittest.TestCase):
    def test_tracking_restored_after_arrival(self):
        m = FakeMount()
        self.assertEqual(m.slew(17.8, -30.5), ['tracking encendido'])
        a = m.wait_arrival()
        self.assertEqual(a['state'], 'arrived')
        self.assertTrue(a['tracking'])
        self.assertTrue(m.props['Tracking'])
        self.assertIn('se volvió a encender', a['note'])

    def test_no_note_when_driver_keeps_tracking(self):
        m = FakeMount(drops_tracking=False)
        m.slew(17.8, -30.5)
        a = m.wait_arrival()
        self.assertEqual((a['state'], a['tracking'], a['note']), ('arrived', True, ''))

    def test_sync_slew_also_restores_tracking(self):
        m = FakeMount(can_async=False)
        m.slew(17.8, -30.5)
        a = m.wait_arrival()
        self.assertEqual((a['state'], a['tracking']), ('arrived', True))

    def test_abort_does_not_restart_tracking(self):
        m = FakeMount(duration=1.0)
        m.slew(17.8, -30.5)
        time.sleep(0.1)
        m.abort()
        time.sleep(0.3)                            # más que varios ciclos del vigilante
        self.assertEqual(m.arrival['state'], 'aborted')
        self.assertFalse(m.props['Tracking'])
        self.assertEqual(m.tracking_writes, [True])   # solo el encendido previo al slew

    def test_new_slew_supersedes_previous_watcher(self):
        m = FakeMount(duration=0.3)
        m.slew(17.8, -30.5)
        m.props['Slewing'] = False                 # el primero "termina" sin pasar por finish
        m.slew(18.0, -30.0)
        a = m.wait_arrival()
        self.assertEqual((a['seq'], a['state']), (2, 'arrived'))


if __name__ == '__main__':
    unittest.main()
