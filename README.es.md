# Llano Control

Aplicación nativa GTK4 para el **Llano V12 Ultra** en Linux, desarrollada en PikaOS con Hyprland. Controla iluminación y perfiles térmicos del ventilador, y muestra sensores de CPU/GPU desde la ventana o la bandeja.

[English](README.md) · [Protocolo](docs/PROTOCOL.md) · [Fuentes de temperatura](docs/TEMPERATURAS.md)

**Versión 0.8.1 — soporte de hardware experimental.** Las órdenes HID proceden de capturas de MythCool en Windows. Las pruebas automáticas verifican los bytes y el manejo de estados; faltan validación física completa en Linux y calibración de los extremos de RPM. Las RPM mostradas son objetivos estimados, no lecturas de tacómetro. Proyecto independiente, sin afiliación oficial con Llano.

## Funciones

- RGB: encendido, cuatro efectos, cinco colores, brillo 0–255 y velocidad 0–3.
- Interruptor general con posición recordada y confirmación del estado USB.
- Manual fijo o térmico, IA baja/media/alta y curvas personalizadas.
- Control por CPU, una GPU elegida o la mayor temperatura disponible de CPU/GPU.
- Sensores Intel, NVIDIA y AMD según hardware, controlador y permisos.
- Español/inglés al instante; inicio minimizado y autostart opcional.
- Consultas cada segundo visible y cada dos segundos en bandeja. NVIDIA suspendida no se consulta.

| Modo | Rango objetivo estimado |
| --- | --- |
| IA baja | 300–1000 RPM |
| IA media | 600–2000 RPM |
| IA alta | 1000–2800 RPM |
| Manual | Fijo o de 300 hasta el máximo elegido |
| Personalizado | Curva editable entre 300 y 2800 RPM |

Las curvas IA suben entre 30 y 90 °C, en pasos de 100 RPM. La calibración observada es 40% → 1300 RPM, 50% → 1550 RPM y 60% → 1800 RPM. El resto del rango es una extrapolación experimental.

## Instalación

En PikaOS/Debian/Ubuntu, Python 3.10+ y las bibliotecas del sistema:

```sh
sudo apt install python3 python3-gi python3-cairo python3-gi-cairo \
  gir1.2-gtk-4.0 gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

Descarga o clona el repositorio y, desde su carpeta:

```sh
python3 install.py
~/.local/bin/llano-control gui
```

No requiere compilación ni paquetes pip. Se instala en `~/.local/share/llano-control` con un lanzador en `~/.local/bin` y una entrada en el menú. Conserva los perfiles. Para actualizar, vuelve a ejecutar el instalador. En otras distribuciones instala los paquetes equivalentes.

Para la bandeja necesitas un anfitrión AppIndicator/StatusNotifier; en Hyprland puedes habilitar el módulo `tray` de Waybar. Sin bandeja se muestra la ventana. NVIDIA usa opcionalmente `nvidia-smi` del controlador.

### Permisos USB

Conecta alimentación y cable USB de datos. Comprueba el dispositivo con `./llano-control probe`: se admite `374a:b101` y el descriptor HID identificado. Para ese dispositivo instala la regla específica:

```sh
sudo install -m 0644 packaging/70-llano-control.rules.example /etc/udev/rules.d/70-llano-control.rules
sudo udevadm control --reload-rules
```

Desconecta y vuelve a conectar el cable USB. Ejecuta la aplicación con tu usuario normal.

## Uso

Cierra MythCool antes de aplicar ajustes. Elige fuente de temperatura, GPU y modo, y pulsa **Aplicar modo y RPM**. En CPU + GPU se usa la mayor lectura disponible; si una falta, el estado indica cuál se está usando. GPU exclusiva se pausa si su tarjeta no tiene temperatura.

**Aplicar RGB** conserva ventilador y encendido. **Guardar** conserva el perfil, sin aplicarlo. El interruptor general pausa la curva; tras encender pulsa Aplicar modo para reanudarla. **Detener control automático** conserva la última velocidad.

El control activo funciona también en bandeja, como máximo cada cinco segundos, y evita reescribir consignas iguales. El mando físico, apagado, pérdida del sensor o errores USB pausan el control sin reintentos continuos. Al abrir la aplicación se restauran los ajustes, pero no se aplica automáticamente una curva ni se enciende el cooler.

Perfiles, idioma y posición confirmada se guardan en `~/.config/llano-control/`, respetando `XDG_CONFIG_HOME`. La imagen está incrustada; no se descarga al iniciar.

## Pruebas y contribuciones

```sh
sudo apt install python3-yaml
python3 -m unittest discover -s tests -v
```

Hay 111 pruebas sin escrituras USB reales. Se incluyen datos HID mínimos para comparar mensajes; se excluyen capturas completas, registros del equipo y copias de Bottles. Las herramientas opcionales de captura requieren tshark/dumpcap; la prueba experimental de Soda requiere PyYAML. [Capturas](docs/CAPTURE.md) · [Contribuir](CONTRIBUTING.md).

Código bajo licencia [MIT](LICENSE). La imagen del producto y las marcas quedan excluidas de esa licencia: [NOTICE](NOTICE.md).
