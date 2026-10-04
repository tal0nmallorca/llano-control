# Automatic cooler power-off / Apagado automático

| Environment | Detection | Validation |
| --- | --- | --- |
| Modern logind (systemd or compatible provider) | PrepareForShutdownWithMetadata, poweroff or power-off; delay inhibitor | PikaOS connection checked; unit tests; physical shutdown pending |
| Older systemd, or systemd without logind | JobNew for poweroff.target, verified JobType=start | Mocked tests only; best effort before session teardown |
| Non-systemd without compatible logind (OpenRC, runit, etc.) | Explicit power-off CLI hook configured by administrator | CLI unit test only; no init-specific integration installed |

Reboot, halt, kexec, soft-reboot, logout, suspend and generic shutdown.target never trigger the automatic off. No names are guessed. There is no polling or additional resident process. Modern systems use the early logind notification; the older-system fallback is later and cannot guarantee USB access before teardown. A vanished or unverifiable job is ignored. Forced shutdown, process crashes, a stopped app or USB errors can prevent delivery.

The GUI saves the profile, stops its controller, drains pending operations and sends the existing verified USB power-off command. The temporary off does not replace the saved profile. Keep the GUI running in the tray for automatic detection. Restart the app after installing updates.

## Other init systems

`llano-control power-off` (or `./Llano-Control-VERSION-x86_64.AppImage power-off`) sends the verified off command without opening a GUI. This is a building block, not automatic init integration. A distribution-specific hook must stop the GUI and wait for all its USB workers to exit first, then run this command while USB and the installation are still available, with the same user's runtime directory and device permissions. Do not run it alongside an active temperature controller, which could turn the cooler on again. Do not place it in a generic logout/reboot hook. Profiles are not changed. Return code 0 means the device confirmed off; errors return nonzero. Do not add sudo or root execution by default.

## Español

Se admiten ambos valores de apagado: poweroff y power-off. En sistemas modernos se usa logind; en systemd antiguo hay una alternativa que verifica poweroff.target. Esta última llega más tarde y requiere validación física por distribución. En otros sistemas existe el comando power-off para una integración específica; no se instala automáticamente. Antes de usarlo en un script, hay que cerrar la GUI y esperar a que termine, para que su control de temperatura no vuelva a encender el cooler. No se activa con reinicio, cierre de sesión o suspensión.

La compatibilidad depende de las interfaces disponibles, no del nombre de la distribución. No se ha probado físicamente en todas las distribuciones. El AppImage publicado sigue siendo x86_64 y no se reconstruye automáticamente al editar el código local.

References: https://github.com/systemd/systemd/blob/v261/src/login/logind-action.c and https://www.freedesktop.org/wiki/Software/systemd/dbus/
