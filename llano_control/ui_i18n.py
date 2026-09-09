"""Refresh presentation properties in place, without rebuilding editable widgets."""
import weakref
from gi.repository import Gtk
from .i18n import t, source_text

_widgets = weakref.WeakSet()

def bind(widget, method, text):
    if not hasattr(widget, '_translations'):
        widget._translations = {}
    widget._translations[method] = source_text(text)
    _widgets.add(widget)
    getattr(widget, method)(t(source_text(text)))

def refresh():
    for widget in list(_widgets):
        for method, text in widget._translations.items():
            getattr(widget, method)(t(text))

class Label(Gtk.Label):
    def __init__(self, **kwargs):
        text = kwargs.pop('label', '')
        super().__init__(**kwargs)
        self.set_text(text)

    def set_text(self, text):
        self._remember('set_text', text)
        translated=t(source_text(text))
        if self.get_text()!=translated: Gtk.Label.set_text(self, translated)

    def set_tooltip_text(self, text):
        self._remember('set_tooltip_text', text)
        translated=t(source_text(text))
        if self.get_tooltip_text()!=translated: Gtk.Label.set_tooltip_text(self, translated)

    def _remember(self, method, text):
        if not hasattr(self, '_translations'): self._translations = {}
        self._translations[method] = source_text(text)
        _widgets.add(self)

def button(widget_type, **kwargs):
    text = kwargs.pop('label', None)
    widget = widget_type(**kwargs)
    if text is not None: bind(widget, 'set_label', text)
    return widget

class ComboBoxText(Gtk.ComboBoxText):
    def __init__(self):
        super().__init__()
        self._translations = {'translate_rows': None}
        self._row_sources = []
        _widgets.add(self)

    def append(self, identifier, text):
        self._row_sources.append(source_text(text))
        Gtk.ComboBoxText.append(self, identifier, t(source_text(text)))

    def remove_all(self):
        self._row_sources.clear()
        Gtk.ComboBoxText.remove_all(self)

    def translate_rows(self, _=None):
        # Update display text only: preserve IDs, selection and change handlers.
        for row, text in zip(self.get_model(), self._row_sources):
            row[0] = t(text)
