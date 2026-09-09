"""GTK3 indicator helper; isolated from the application's GTK4 process."""
from i18n import t, set_language
import json
import sys
import threading
import gi
gi.require_version('Gtk','3.0')
gi.require_version('AyatanaAppIndicator3','0.1')
from gi.repository import Gtk, GLib, AyatanaAppIndicator3 as Indicator


def emit(event, **values):
    try: print(json.dumps({'event': event, **values}), flush=True)
    except BrokenPipeError: Gtk.main_quit()


def main():
    if not Gtk.init_check()[0]: return 1
    indicator=Indicator.Indicator.new('llano-control','utilities-system-monitor',Indicator.IndicatorCategory.HARDWARE)
    indicator.set_status(Indicator.IndicatorStatus.ACTIVE)
    indicator.set_title('Llano Control')
    menu=Gtk.Menu()
    show=Gtk.MenuItem(label=t('Abrir Llano Control')); show.connect('activate',lambda *_: emit('show')); menu.append(show)
    menu.append(Gtk.SeparatorMenuItem())
    rows=[]
    for label in ('CPU: — °C','GPU: — °C'):
        item=Gtk.MenuItem(label=t(label)); item.set_sensitive(False); menu.append(item); rows.append(item)
    menu.append(Gtk.SeparatorMenuItem())
    quit_item=Gtk.MenuItem(label=t('Salir')); quit_item.connect('activate',lambda *_: emit('quit')); menu.append(quit_item)
    menu.show_all(); indicator.set_menu(menu); indicator.set_secondary_activate_target(show)
    indicator.connect('connection-changed',lambda _,connected: emit('connection',connected=connected))
    emit('connection',connected=indicator.get_property('connected'))

    last_indicator=[None]

    def set_label(item,text):
        if item.get_label()!=text: item.set_label(text)

    def update(data):
        if data.get('quit'): Gtk.main_quit(); return False
        if data.get('language') in ('es','en'): set_language(data['language'])
        set_label(show,t('Abrir Llano Control')); set_label(quit_item,t('Salir'))
        cpu,gpu=data.get('cpu'),data.get('gpu')
        def display(value):
            return '—' if value is None else str(round(value))
        set_label(rows[0],'CPU: '+display(cpu)+' °C')
        set_label(rows[1],'GPU: '+display(gpu)+' °C · '+t(data.get('gpu_name','No disponible')))
        text='CPU '+display(cpu)+'° · GPU '+display(gpu)+'° · V12 — RPM'
        if text!=last_indicator[0]:
            indicator.set_label(text,'CPU 100° · GPU 100° · V12 2800 RPM')
            indicator.set_icon_full('utilities-system-monitor',text)
            last_indicator[0]=text
        return False

    def read_input():
        try:
            for line in sys.stdin:
                try: data=json.loads(line)
                except ValueError: continue
                GLib.idle_add(update,data)
        finally: GLib.idle_add(Gtk.main_quit)
    threading.Thread(target=read_input,daemon=True).start()
    Gtk.main(); return 0

if __name__=='__main__': sys.exit(main())
