# Changelog

## 0.8.3

- Resolve saved CPU sensor paths after Linux renumbers hwmon devices at reboot.
- Keep the same physical device and temperature channel; reject ambiguous replacements.
- Restore dynamic fan curves when the previous CPU sensor path has moved.

## 0.8.2

- Save current settings and the displayed GPU when hiding to tray or exiting, without redundant writes.
- Apply the saved RPM profile after startup sensor delivery, then apply RGB after the USB operation completes.
- Preserve the last valid profile if saving fails or edits are invalid; do not repeatedly retry failed USB operations.

## 0.8.1

- Keep background fan-control cycles from flashing Apply buttons or status text.
- Queue explicit actions while a background USB operation finishes.
- Include CPU, selected GPU and combined temperature control for fan profiles.
- Include capture-backed RGB, device power and fan controls; RPM calibration remains experimental.
- Provide live Spanish/English switching, tray startup and reduced background telemetry work.
