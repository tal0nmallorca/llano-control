"""Presentation-only translations; profile and protocol identifiers stay unchanged."""
import json
import os
from pathlib import Path
import re
import tempfile

EN = {'Minimizar a bandeja': 'Minimize to tray',
 'Salir': 'Quit',
 'Buscando conexión USB…': 'Looking for USB connection…',
 'VID 374A    ·    PID B101    ·    Revisión por confirmar': 'VID 374A    ·    PID B101    ·    Revision '
                                                             'unconfirmed',
 'Encendido y RPM reales: no disponibles': 'Power state and actual RPM: unavailable',
 'Leyendo sensores…': 'Reading sensors…',
 'Objetivo manual · RPM': 'Manual target · RPM',
 'Solicitar encendido al aplicar': 'Request power on when applying',
 'Histéresis · °C': 'Hysteresis · °C',
 'AI: presets locales aproximados. Control físico pendiente.': 'AI: approximate local presets. Hardware '
                                                               'control pending.',
 'Speed Settings · curva y sensor CPU': 'Speed settings · curve and CPU sensor',
 'Iluminación': 'Lighting',
 'Perfiles y aplicación': 'Profiles and application',
 'Nombre de perfil': 'Profile name',
 'Guardar': 'Save',
 'Previsualizar': 'Preview',
 'Diagnóstico': 'Diagnostics',
 'Aplicar al Llano · protocolo pendiente': 'Apply to Llano · protocol pending',
 'Abrir al iniciar sesión': 'Start at login',
 'Los perfiles se guardan localmente. No se envían órdenes USB.': 'Profiles are saved locally. No USB '
                                                                  'commands are sent.',
 'Carga': 'Load',
 'Temperatura': 'Temperature',
 'Sin sensor': 'No sensor',
 'Sensor desconectado': 'Sensor disconnected',
 'Lectura no disponible': 'Reading unavailable',
 'No disponible': 'Unavailable',
 'Potencia no disponible': 'Power unavailable',
 'Memoria Intel: compartida con RAM · uso dedicado no expuesto': 'Intel memory: shared with RAM · dedicated '
                                                                 'usage not exposed',
 'Reloj memoria: ': 'Memory clock: ',
 'RAM GPU residente (clientes): ': 'Resident GPU RAM (clients): ',
 'cliente(s)': 'client(s)',
 'Suma por cliente accesible, no uso global; buffers compartidos pueden duplicarse. Solicitada: ': 'Sum of '
                                                                                                   'accessible '
                                                                                                   'clients, '
                                                                                                   'not '
                                                                                                   'global '
                                                                                                   'usage; '
                                                                                                   'shared '
                                                                                                   'buffers '
                                                                                                   'may be '
                                                                                                   'counted '
                                                                                                   'twice. '
                                                                                                   'Allocated: ',
 'Ahorro: 1 s visible / 2 s en bandeja · — = dato no disponible': 'Power saving: 1 s visible / 2 s in tray · '
                                                                  '— = unavailable',
 'Bandeja no disponible. La ventana seguirá abierta.': 'Tray unavailable. The window will stay open.',
 'La bandeja se desconectó; se ha restaurado la ventana.': 'The tray disconnected; the window has been '
                                                           'restored.',
 'No hay bandeja disponible; se muestra la ventana para poder acceder a la aplicación.': 'No tray available; '
                                                                                         'showing the window '
                                                                                         'so you can access '
                                                                                         'the application.',
 'No hay bandeja disponible. En Hyprland activa el módulo tray de Waybar. Dependencia: gir1.2-ayatanaappindicator3-0.1.': 'No '
                                                                                                                          'tray '
                                                                                                                          'available. '
                                                                                                                          'In '
                                                                                                                          'Hyprland '
                                                                                                                          'enable '
                                                                                                                          'the '
                                                                                                                          'Waybar '
                                                                                                                          'tray '
                                                                                                                          'module. '
                                                                                                                          'Dependency: '
                                                                                                                          'gir1.2-ayatanaappindicator3-0.1.',
 'Perfil guardado en este equipo. No aplicado al hardware.': 'Profile saved on this computer. Not applied to '
                                                             'hardware.',
 'Previsualización: ': 'Preview: ',
 ' RPM objetivo · temperatura ': ' RPM target · temperature ',
 ' °C · ninguna escritura USB': ' °C · no USB writes',
 'Sin objetivo calculable: apagado solicitado o sensor no disponible. Sin acción USB.': 'No target '
                                                                                        'available: power '
                                                                                        'off requested or '
                                                                                        'sensor unavailable. '
                                                                                        'No USB action.',
 'Curva local: 0–110 °C / 300–2800 RPM': 'Local curve: 0–110 °C / 300–2800 RPM',
 'USB conectado · identidad candidata': 'USB connected · candidate identity',
 'USB desconectado / no visible': 'USB disconnected / not visible',
 'Diagnóstico local: ': 'Local diagnostics: ',
 'No hay sesión gráfica disponible. Ejecuta la GUI dentro de Wayland/X11.': 'No graphical session available. '
                                                                            'Run the GUI inside Wayland/X11.',
 'Abrir Llano Control': 'Open Llano Control',
 'V12 Ultra: RPM no disponibles': 'V12 Ultra: RPM unavailable',
 'Formato de perfiles no compatible': 'Unsupported profile format',
 'Perfil activo inexistente': 'Active profile not found',
 'Valor fuera de rango ': 'Value out of range ',
 'Nombre de perfil inválido': 'Invalid profile name',
 'Modo o efecto desconocido': 'Unknown mode or effect',
 'Sensor inválido': 'Invalid sensor',
 'Color: usa #RRGGBB': 'Color: use #RRGGBB',
 'Curva: 2–32 puntos': 'Curve: 2–32 points',
 'Estado inválido': 'Invalid state',
 'Temperaturas deben ser crecientes y únicas': 'Temperatures must be increasing and unique',
 'Esperando dos lecturas de energía CPU': 'Waiting for two CPU energy readings',
 'El kernel no expone energía del paquete CPU (RAPL)': 'The kernel does not expose CPU package energy (RAPL)',
 'Potencia media del paquete CPU · RAPL (Δenergía / Δtiempo)': 'Average CPU package power · RAPL (Δenergy / '
                                                               'Δtime)',
 'Energía CPU no legible: comprueba permisos de lectura RAPL': 'CPU energy unreadable: check RAPL read '
                                                               'permissions',
 'Esperando la segunda lectura de energía CPU': 'Waiting for the second CPU energy reading',
 'Reiniciando medición tras pausa': 'Restarting measurement after pause',
 'Contador CPU reiniciado': 'CPU counter reset',
 'Sin sensor CPU compatible: coretemp, k10temp o zenpower': 'No supported CPU sensor: coretemp, k10temp or '
                                                            'zenpower',
 'Potencia SoC expuesta por amdgpu; en una APU incluye la CPU. VRAM y GTT son regiones distintas.': 'SoC '
                                                                                                    'power '
                                                                                                    'exposed '
                                                                                                    'by '
                                                                                                    'amdgpu; '
                                                                                                    'on an '
                                                                                                    'APU it '
                                                                                                    'includes '
                                                                                                    'the '
                                                                                                    'CPU. '
                                                                                                    'VRAM '
                                                                                                    'and GTT '
                                                                                                    'are '
                                                                                                    'separate '
                                                                                                    'regions.',
 'GPU AMD en reposo: no se consultan sensores para evitar despertarla.': 'AMD GPU asleep: skipping sensors '
                                                                         'to avoid waking it.',
 'coretemp / Package id 0 (no disponible)': 'coretemp / Package id 0 (unavailable)',
 ' (control térmico; puede incluir offset)': ' (thermal control; may include an offset)',
 'Clientes DRM accesibles de tu usuario; cobertura parcial. Memoria residente sumada: buffers compartidos entre clientes pueden contarse más de una vez.': 'DRM '
                                                                                                                                                           'clients '
                                                                                                                                                           'accessible '
                                                                                                                                                           'to '
                                                                                                                                                           'your '
                                                                                                                                                           'user; '
                                                                                                                                                           'partial '
                                                                                                                                                           'coverage. '
                                                                                                                                                           'Summed '
                                                                                                                                                           'resident '
                                                                                                                                                           'memory: '
                                                                                                                                                           'buffers '
                                                                                                                                                           'shared '
                                                                                                                                                           'between '
                                                                                                                                                           'clients '
                                                                                                                                                           'may '
                                                                                                                                                           'be '
                                                                                                                                                           'counted '
                                                                                                                                                           'more '
                                                                                                                                                           'than '
                                                                                                                                                           'once.',
 'Actividad fuera RC6': 'Activity outside RC6',
 'Actividad = tiempo fuera del reposo RC6; no es carga de motores GPU. Temperatura: no expuesta. Memoria compartida con RAM.': 'Activity '
                                                                                                                               '= '
                                                                                                                               'time '
                                                                                                                               'outside '
                                                                                                                               'RC6 '
                                                                                                                               'sleep; '
                                                                                                                               'not '
                                                                                                                               'GPU '
                                                                                                                               'engine '
                                                                                                                               'load. '
                                                                                                                               'Temperature: '
                                                                                                                               'not '
                                                                                                                               'exposed. '
                                                                                                                               'Memory '
                                                                                                                               'shared '
                                                                                                                               'with '
                                                                                                                               'RAM.',
 'Motor más ocupado': 'Busiest engine',
 ' Sin dos muestras de motores: el indicador usa actividad fuera RC6.': ' Without two engine samples: the '
                                                                        'indicator uses activity outside '
                                                                        'RC6.',
 'Sin sensor CPU compatible': 'No supported CPU sensor',
 'NVIDIA en reposo: no se consulta para evitar despertarla': 'NVIDIA asleep: skipping queries to avoid '
                                                             'waking it',
 'NVIDIA: el controlador no permite consultar la GPU': 'NVIDIA: the driver does not allow GPU queries',
 'NVIDIA: consulta no disponible o agotó el tiempo de espera': 'NVIDIA: query unavailable or timed out',
 'Frecuencia ': 'Frequency ',
 'Potencia': 'Power',
 'Idioma': 'Language',
 'Idioma guardado. Usa Salir y vuelve a abrir Llano Control para aplicar el cambio.': 'Language saved. Quit '
                                                                                      'and reopen Llano '
                                                                                      'Control to apply the '
                                                                                      'change.'}
ES = {'V12 Ultra Laptop Cooler': 'Base refrigeradora V12 Ultra',
 'Hardware Status': 'Estado del hardware',
 'RPM Mode': 'Modo de RPM',
 'AI Low': 'IA baja',
 'AI Medium': 'IA media',
 'AI High': 'IA alta',
 'Custom': 'Personalizado',
 'Low': 'Bajo',
 'Medium': 'Medio',
 'High': 'Alto',
 'RGB Lighting Control': 'Control de iluminación RGB',
 'Mode': 'Modo',
 'Brightness · %': 'Brillo · %',
 'Speed · %': 'Velocidad · %',
 'Solid Color': 'Color fijo',
 'Breathing Effect': 'Efecto respiración',
 'Color Gradient': 'Degradado de color',
 'Color Chase': 'Secuencia de colores'}
ES['Speed Settings · curva y sensor CPU'] = 'Ajustes de velocidad · curva y sensor CPU'
EN.update({'Rojo': 'Red', 'Azul': 'Blue', 'Verde': 'Green', 'Lila': 'Purple', 'Naranja': 'Orange', 'Brillo · 0–255': 'Brightness · 0–255', 'Velocidad · 0–3': 'Speed · 0–3', 'Velocidad 0: animación lenta. Colores predefinidos del dispositivo.': 'Speed 0: slow animation. Device preset colors.', 'Aplicar RGB': 'Apply RGB', 'RGB se aplica bajo demanda; no cambia RPM ni encendido general.': 'RGB applies on demand; it does not change RPM or device power.', 'Guardar conserva el perfil; Aplicar RGB envía la iluminación al dispositivo.': 'Save stores the profile; Apply RGB sends lighting settings to the device.', 'Aplicando RGB…': 'Applying RGB…', 'RGB confirmado por el dispositivo.': 'RGB confirmed by device.', 'Tiempo de espera agotado. Comprueba el dispositivo antes de reintentar.': 'Timed out. Check the device before retrying.', 'Error RGB: ': 'RGB error: '})
EN.update({'RPM mostradas: objetivos estimados, no tacómetro.': 'Displayed RPM: estimated targets, not tachometer readings.', 'Aplicar modo activa el control. Rangos RPM estimados; calibración pendiente en los extremos.': 'Apply mode enables control. RPM ranges are estimated; endpoint calibration is pending.', 'Aplicar modo y RPM': 'Apply mode and RPM', 'Detener control automático': 'Stop automatic control', 'Control del ventilador inactivo.': 'Fan control inactive.', 'Control detenido; se conserva la última velocidad.': 'Control stopped; last speed retained.', 'Aplicando consigna del ventilador…': 'Applying fan target…', 'Control pausado: ': 'Control paused: ', 'Control pausado: mando físico o dispositivo apagado.': 'Control paused: physical knob used or device powered off.', 'Dispositivo apagado; control automático detenido.': 'Device powered off; automatic control stopped.', 'Consigna confirmada: ': 'Target confirmed: ', 'CPU del sistema · automático': 'System CPU · automatic'})
EN.update({'Encender Llano': 'Power on Llano', 'Apagar Llano': 'Power off Llano', 'Control general: ventilador, RGB y pantalla.': 'Device power: fan, RGB and display.', 'Control automático pausado. Pulsa Aplicar modo para reanudar.': 'Automatic control paused. Click Apply mode to resume.', 'Cambiando encendido general…': 'Changing device power…', 'Llano encendido · estado USB confirmado.': 'Llano powered on · USB state confirmed.', 'Llano apagado · estado USB confirmado.': 'Llano powered off · USB state confirmed.', 'No se pudo confirmar el encendido: ': 'Could not confirm power state: '})
EN.update({'Encender/apagar Llano':'Toggle Llano power'})
EN.update({'Apagado':'Off','Encendido':'On','Estado confirmado; no se pudo guardar la posición.':'State confirmed; could not save the position.','Posición recordada; estado del dispositivo sin confirmar.':'Remembered position; device state not confirmed.'})
EN.update({'Temperatura para las RPM': 'Temperature for RPM control', 'GPU de control': 'GPU for control', 'GPU más caliente disponible': 'Hottest available GPU', 'CPU + GPU usa la mayor temperatura disponible.': 'CPU + GPU uses the highest available temperature.', 'Manual según temperatura · RPM como máximo': 'Temperature-based Manual · RPM as maximum', 'GPU no disponible': 'GPU unavailable', 'CPU + GPU · máxima': 'CPU + GPU · maximum', 'CPU · GPU sin temperatura': 'CPU · GPU temperature unavailable', 'GPU · CPU sin temperatura': 'GPU · CPU temperature unavailable'})
_PATTERN = re.compile('|'.join(re.escape(key) for key in sorted(EN, key=len, reverse=True)))

def settings_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'llano-control/settings.json'

def load_language():
    try:
        data = json.loads(settings_path().read_text())
        value = data.get('language') if isinstance(data, dict) else None
        return value if value in ('es', 'en') else 'es'
    except (OSError, ValueError):
        return 'es'

def save_language(language):
    if language not in ('es', 'en'):
        raise ValueError('Unsupported language')
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict): data = {}
    except (OSError, ValueError):
        data = {}
    data['language'] = language
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)

LANGUAGE = load_language()

class Translated(str):
    def __new__(cls, value, source):
        obj = super().__new__(cls, value)
        obj.source = source
        return obj

def source_text(text):
    return text.source if isinstance(text, Translated) else text

def set_language(language):
    global LANGUAGE
    if language not in ('es', 'en'): raise ValueError('Unsupported language')
    LANGUAGE = language

def t(text, language=None):
    if text is None: return None
    text = source_text(text)
    language = language or LANGUAGE
    if language == 'en':
        # A single pass also handles messages composed with readings and units.
        return Translated(_PATTERN.sub(lambda match: EN[match.group()], text), text)
    return Translated(ES.get(text, text), text)
