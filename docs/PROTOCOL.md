# Llano V12 Ultra: protocolo observado en capturas etiquetadas

Fecha del análisis: 2026-09-09. Se han leído los 29 PCAPNG, no solo las anotaciones. El repositorio incluye los eventos HID mínimos en `tests/fixtures/usb-events.csv`; las capturas completas y registros privados no se distribuyen. Las anotaciones originales se usaron como evidencia aportada: sus observaciones físicas no pueden comprobarse mediante el PCAP por sí solo.

## Verificación independiente

Las 29 capturas identifican VID 374a, PID b101 en el descriptor del paquete 2, bus 1 y dirección 9. Todos los paquetes tienen estado USB correcto. Se extrajeron 958 reportes (consultas SET, ajustes SET y respuestas GET), todos de 8 bytes y todos con suma módulo 256 igual a 255. Los 75 ajustes distintos de la consulta periódica tienen confirmación USB correcta. Los números de paquete y datos de ajuste coinciden con las anotaciones. La captura 50 no contiene una orden de 300 a 400 RPM.

## Transporte

Interfaz 0, Feature Report sin ID numerado. SET_REPORT: bmRequestType=0x21, bRequest=0x09, wValue=0x0300, wIndex=0, wLength=8. GET_REPORT: bmRequestType=0xa1, bRequest=0x01, mismos wValue, wIndex y wLength.

Consulta observada: SET `80 00 00 00 00 00 00 7f`, luego GET de 8 bytes, aproximadamente cada segundo. Se describe lo que hace MythCool; el transporte Linux está implementado, con validación física pendiente. No confundir estos 8 bytes sobre USB con el posible prefijo de Report ID requerido por una API hidraw/hidapi.

## Campos (offsets desde cero)

| Byte | Asociación respaldada | Alcance |
| --- | --- | --- |
| 0, envíos | 00 actualización; 01 asociado a confirmación/recuperación del control PC; 80 consulta | 01 permite salir de manual en la captura 56; no se conoce toda su semántica |
| 0, respuestas | 80 normal; 88 manual físico | Par 55/56 y observaciones del registro respaldan bit 08 de manual |
| 1 | Porcentaje de consigna/estado de velocidad | Curvas planas 40, 50, 60 producen 28, 32, 3c; no es un tacómetro |
| 2 | 00 encendido general, 01 apagado general | Par 60/61, con confirmación física registrada de ventilador, RGB y pantalla |
| 3 | Modo RGB 00 sólido, 01 respiración, 02 gradiente, 03 persecución; bit 80 apaga RGB | Modos 30–33; apagado/encendido 10/11 probado con modo 03 |
| 4 | Color predefinido: rojo 00, azul 01, verde 02, lila 03, naranja 04 | Selecciones explícitas en modo sólido, capturas 40–44; no extrapolar a colores RGB arbitrarios |
| 5 | Velocidad de animación: UI 3→00, 2→01, 1→02, 0→03 | Capturas 22–24. El registro indica que 0 sigue animando, más despacio |
| 6 | Brillo: 255→ff, 127→7f | Par 20/21; otros valores aparecen en capturas anteriores sin etiquetas precisas |
| 7 | `(255 - sum(bytes[0:7])) & 255` | Cumple los 958 reportes nuevos y los 525 de las capturas antiguas |

Los ajustes transmiten el bloque completo. El controlador obtiene y conserva los campos ajenos al cambio solicitado. No enviar un paquete fijo de RGB que accidentalmente sobrescriba la velocidad o el encendido. No convertir una respuesta 88 directamente en una orden.

## Velocidad, curvas y control físico

El registro aporta estos puntos de observación física:

| Consigna | Pantalla del Llano |
| ---: | ---: |
| 40 % | 1300 RPM |
| 50 % | 1550 RPM |
| 60 % | 1800 RPM |

Son compatibles con RPM=300+25*p en este intervalo. Hay puntos adicionales de perfiles automáticos compatibles, pero sin sincronización exacta. Esto no valida una conversión general en 300–2800 RPM. En manual físico, el estado final 01 corresponde a una observación de 300 RPM, lo que exige tratar el extremo inferior por separado. Falta probar 0/1 %, 4 %, 96 % y 100 % con lectura física antes de garantizar pasos de 100 RPM en todo el rango. No etiquetar RPM calculadas como medidas.

En 55, el mando físico cambia respuestas 80→88 y reduce el porcentaje; las actualizaciones 00 del PC siguen llegando cada cinco segundos, pero no recuperan el control. En 56, los envíos 01 preceden a la vuelta 88→80 y al retorno a 40 % / 1300 RPM. El software Linux debe respetar el modo físico y recuperar el control solo por acción explícita del usuario.

Low/Medium/High y Custom producen porcentajes periódicos, no identificadores exclusivos de perfil ni tablas completas de curva en estas capturas. Esto respalda implementar las curvas en Linux. No prueba que el hardware no admita otros comandos ni almacenamiento de curvas.

El apagado general conserva el porcentaje en el estado: no mostrar esa consigna como ventilador girando cuando byte 2 es 01. Tras encender, el registro físico de 1525 RPM no coincide temporalmente con el último reporte 56 %; no asignar esa lectura a ese paquete.

## Implementación y validación pendiente

El controlador Linux implementa consultas, lectura-modificación-escritura y comprobación del estado devuelto. Identifica VID/PID e interfaz, verifica el descriptor HID, valida checksum y serializa operaciones con un bloqueo. Las pruebas usan eventos capturados y transportes simulados; no envían USB real.

Las asociaciones están respaldadas por capturas Windows y por las acciones/observaciones del registro. Falta confirmar físicamente los efectos de las órdenes Linux, recuperación desde manual y calibración de los extremos. Las RPM calculadas son estimaciones, no lecturas de tacómetro. Desde 0.8.2 el inicio aplica automáticamente el perfil de RPM guardado y, después, el RGB; no se reintenta continuamente una operación fallida.
