"""Read-only packaging checks: never instantiate the cooler application."""
import json
import os
import subprocess
import sys


def run():
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, Gdk, GLib
    import cairo
    from .product_image import image_bytes
    texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_bytes()))
    if texture.get_width() < 1:
        raise RuntimeError('Product image could not be decoded')
    # GTK3 must stay in a separate process, exactly as the tray helper does.
    code = '''import gi, cairo
 gi.require_version('Gtk','3.0')
 gi.require_version('AyatanaAppIndicator3','0.1')
 from gi.repository import Gtk, AyatanaAppIndicator3
 print('GTK3 tray dependencies OK')
'''.replace('\n ', '\n')
    subprocess.run([sys.executable, '-c', code], check=True, timeout=15)
    if os.environ.get('LLANO_TEST_DISPLAY') == '1':
        Gtk.init()
        if Gdk.Display.get_default() is None:
            raise RuntimeError('No test display')
        window = Gtk.Window(title='Llano Control packaging test')
        window.set_child(Gtk.Label(label='GTK4 AppImage smoke test'))
        loop = GLib.MainLoop()
        window.present()
        GLib.timeout_add(300, lambda: (loop.quit(), False)[1])
        loop.run()
        window.destroy()
    print(json.dumps({'python': sys.version.split()[0], 'gtk': Gtk.get_major_version(),
                      'image': True, 'tray_import': True, 'usb_writes': False}))
    return 0
