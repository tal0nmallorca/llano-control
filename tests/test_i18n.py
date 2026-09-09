import json
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
from llano_control import i18n
from llano_control.core import MODES, EFFECTS

class LanguageTests(unittest.TestCase):
    def test_english_composed_readings(self):
        self.assertEqual(i18n.t('Frecuencia 1200 MHz  ·  Potencia SoC 12.3 W','en'), 'Frequency 1200 MHz  ·  Power SoC 12.3 W')
        self.assertEqual(i18n.t('Previsualización: 1300 RPM objetivo · temperatura 55 °C · ninguna escritura USB','en'), 'Preview: 1300 RPM target · temperature 55 °C · no USB writes')
    def test_catalog_and_hardware_identifiers(self):
        for source, target in i18n.EN.items():
            self.assertEqual(i18n.t(source,'en'), target)
        for name in ('coretemp / Package id 0','Intel Arc A770','AMD Radeon RX 7800 XT','0000:00:02.0'):
            self.assertEqual(i18n.t(name,'en'),name)
        self.assertIsNone(i18n.t(None,'en'))
    def test_spanish_modes_and_effects(self):
        for value in MODES+EFFECTS:
            self.assertIsInstance(i18n.t(value,'es'),str)
        self.assertEqual(i18n.t('Solid Color','es'),'Color fijo')
        self.assertEqual(EFFECTS[0],'Solid Color')
    def test_persistence_and_invalid_settings(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ',XDG_CONFIG_HOME=folder):
            self.assertEqual(i18n.load_language(),'es')
            i18n.save_language('en')
            self.assertEqual(i18n.load_language(),'en')
            path=i18n.settings_path()
            path.write_text('{"language":"en","other":123}')
            i18n.save_language('es')
            self.assertEqual(json.loads(path.read_text())['other'],123)
            for invalid in ('bad json','[]','{"language":"xx"}'):
                path.write_text(invalid)
                self.assertEqual(i18n.load_language(),'es')
            with self.assertRaises(ValueError): i18n.save_language('xx')
    def test_selection_saves_and_refreshes_in_place(self):
        from llano_control.gui import App
        app=SimpleNamespace(message=Mock(),cpu_gauges=[Mock()],gpu_gauges=[Mock()],
                            graph=Mock(),send_tray=Mock(),last_tray_data={'cpu':53},
                            fields={'rpm':1234},name='Unsaved profile')
        widget=Mock(); widget.get_active_id.return_value='en'
        with patch('llano_control.gui.save_language') as save, patch('llano_control.gui.ui_i18n.refresh') as refresh, patch.object(i18n,'LANGUAGE','es'):
            App.change_language(app,widget)
            self.assertEqual(i18n.LANGUAGE,'en')
        save.assert_called_once_with('en'); refresh.assert_called_once()
        app.send_tray.assert_called_once_with({'cpu':53})
        app.graph.queue_draw.assert_called_once()
        self.assertEqual(app.fields,{'rpm':1234})
        self.assertEqual(app.name,'Unsaved profile')
        app.message.set_text.assert_not_called()

    def test_repeated_translation_keeps_original_source(self):
        with patch.object(i18n,'LANGUAGE','es'):
            text=i18n.t('Solid Color')
            self.assertEqual(text,'Color fijo')
            i18n.set_language('en')
            self.assertEqual(i18n.t(text),'Solid Color')
            text=i18n.t('Frecuencia 1234 MHz')
            i18n.set_language('es')
            self.assertEqual(i18n.t(text),'Frecuencia 1234 MHz')

    def test_bound_properties_and_combo_rows_refresh(self):
        from llano_control import ui_i18n
        class Widget:
            def set_label(self,text): self.text=text
        w=Widget()
        with patch.object(i18n,'LANGUAGE','es'):
            ui_i18n.bind(w,'set_label','Salir')
            for language,expected in [('en','Quit'),('es','Salir'),('en','Quit')]:
                i18n.set_language(language); ui_i18n.refresh()
                self.assertEqual(w.text,expected)
            rows=[['Color fijo','Solid Color'],['Secuencia de colores','Color Chase']]
            combo=SimpleNamespace(get_model=lambda:rows,_row_sources=['Solid Color','Color Chase'])
            ui_i18n.ComboBoxText.translate_rows(combo)
            self.assertEqual(rows,[['Solid Color','Solid Color'],['Color Chase','Color Chase']])

    def test_failed_save_does_not_change_running_language(self):
        from llano_control.gui import App
        app=SimpleNamespace(message=Mock()); widget=Mock()
        widget.get_active_id.return_value='en'
        with patch('llano_control.gui.save_language',side_effect=OSError('Read only')), patch.object(i18n,'LANGUAGE','es'):
            App.change_language(app,widget)
            self.assertEqual(i18n.LANGUAGE,'es')
        app.message.set_text.assert_called_once()
