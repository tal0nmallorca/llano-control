# Fuentes de temperatura · 0.8.0

En el panel de modos, Temperatura para las RPM permite seleccionar CPU, GPU o CPU + GPU. GPU de control permite elegir una GPU concreta mediante su identificador o la GPU más caliente disponible. Es independiente de la GPU seleccionada en el monitor. Guardar conserva estos ajustes por perfil; Aplicar modo activa una copia de los ajustes actuales.

CPU usa la temperatura del monitor del sistema (coretemp Package id 0 para Intel o el sensor AMD correspondiente), salvo que se haya seleccionado explícitamente otro sensor en el editor de curva. GPU utiliza la muestra de la tarjeta elegida; con selección automática, toma el máximo de las GPU con temperatura válida. CPU + GPU toma el máximo de las dos temperaturas. Si solo está disponible una, se usa esa y la etiqueta de control indica cuál falta. En GPU exclusiva no se sustituye una tarjeta explícita desconectada por otra. Si no hay temperatura utilizable, el control térmico se pausa y conserva la última consigna.

IA Baja/Media/Alta conservan rangos 300–1000 / 600–2000 / 1000–2800 RPM y curvas 30–90 °C. Personalizado usa sus puntos. Manual según temperatura hace que Manual recorra 300 RPM a 30 °C hasta el valor de RPM elegido a 90 °C. Desmarcar esa opción recupera Manual fijo, independiente de temperatura. En el editor la opción térmica está marcada por defecto para perfiles que no la guardaban; no se modifica el disco ni el hardware hasta Guardar o Aplicar, respectivamente.

La gráfica, la previsualización y el control usan la misma curva y fuente. Histéresis y pasos de 100 RPM se mantienen. Las temperaturas GPU proceden de las muestras existentes, también en bandeja; no se añade ninguna consulta a NVIDIA ni se despierta una GPU suspendida. En modo combinado se usa CPU si la GPU suspendida no aporta temperatura. No se añaden consultas de carga, frecuencia ni memoria en bandeja.

Las RPM siguen siendo consignas estimadas a partir del porcentaje USB, no lecturas de tacómetro. La selección de temperatura es lógica del PC; no se inventan nuevos comandos HID.

Validación: 121 pruebas pasan. Se comprueban selección CPU/GPU/máximo, tarjeta específica ausente, sensores inválidos, fallback combinado, sensor CPU explícito, todas las curvas, Manual térmico/fijo y perfiles antiguos. La confirmación física de los rangos extremos de RPM sigue pendiente.
