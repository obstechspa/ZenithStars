"""El ASCOM Chooser se abre detrás del navegador: _raise_own_window lo pone al frente.

Necesita un escritorio de Windows (crea una ventana tkinter de prueba):
    ZS_GUI_TESTS=1 python -m unittest tests.test_chooser_window
"""
import os
import sys
import threading
import unittest


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('ZS_GUI_TESTS') == '1',
                     'solo Windows con escritorio (ZS_GUI_TESTS=1)')
class TestRaiseChooser(unittest.TestCase):
    def test_window_becomes_topmost(self):
        import ctypes
        import tkinter as tk
        from zenithstars.mount import _raise_own_window

        title = 'Prueba Chooser ZenithStars'
        root = tk.Tk()
        root.title(title)
        root.geometry('300x80')
        user32 = ctypes.windll.user32
        out = {}

        def start():
            out['thread'] = threading.Thread(target=_raise_own_window,
                                             args=('Chooser', threading.Event()), daemon=True)
            out['thread'].start()
            root.after(1000, check)

        def check():
            hwnd = user32.FindWindowW(None, title)
            out['topmost'] = bool(user32.GetWindowLongW(hwnd, -20) & 0x8)   # WS_EX_TOPMOST
            root.destroy()

        root.after(300, start)
        root.mainloop()
        self.assertTrue(out['topmost'])
        self.assertFalse(out['thread'].is_alive())


if __name__ == '__main__':
    unittest.main()
