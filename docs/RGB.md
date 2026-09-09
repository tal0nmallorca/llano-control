# RGB

Desde 0.8.2, el RGB guardado se aplica al iniciar, después de la operación inicial de RPM. También puede aplicarse mediante el botón Aplicar RGB. El control RGB conserva los campos del ventilador y del encendido general.

Formato observado: Feature 8 bytes, Report ID sin numerar. Se usa SET 80 00 00 00 00 00 00 7f y GET para consultar. El ajuste usa byte 0=00, bytes 1/2 del estado, byte 3=modo con bit 80 para RGB apagado, byte 4=color, byte 5=3-velocidad, byte 6=brillo, byte 7=complemento de suma. No se usa byte 0=01, que recupera el control del ventilador desde manual.

Modos: sólido 0, respiración 1, gradiente 2, persecución 3. Colores: rojo 0, azul 1, verde 2, lila 3, naranja 4. La API no acepta colores RGB arbitrarios. Brillo 0–255; animación 0–3 (0 es lenta, no detenida). Las combinaciones no capturadas individualmente usan los campos identificados; falta validación visual Linux.

La identidad se verifica nuevamente mediante ioctls después de abrir hidraw, junto con el hash del descriptor. Lecturas inválidas cancelan el ajuste. El proceso auxiliar está limitado a 8 segundos por la GUI; cada operación bloquea otras operaciones RGB de Llano Control. No coordina con MythCool: cerrar el software oficial antes de aplicar. El control del ventilador activo consulta el estado; el RGB se aplica una vez al inicio y después bajo demanda. Usa la regla udev específica del dispositivo ya instalada.

Validación: 16 órdenes RGB reproducidas byte por byte contra las capturas etiquetadas, pruebas de estado manual/apagado conservado, checksum, valores inválidos, framing de Feature sin ID, fallo de readback y perfiles antiguos/nativos. Ninguna prueba envía USB real.

Primera prueba en Linux: cerrar MythCool, conectar el Llano y aplicar un color con brillo visible. Confirmar visualmente efecto y conservación de velocidad del ventilador. El mensaje de éxito confirma coincidencia del estado USB, no una inspección visual de los LED.

Referencia API: https://www.kernel.org/doc/html/latest/hid/hidraw.html
