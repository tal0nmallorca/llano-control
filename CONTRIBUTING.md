# Contributing

Please describe the problem, Linux distribution, app version and affected hardware in an issue. Remove serial numbers, usernames, personal paths and unrelated USB traffic from logs before sharing them.

Run `python3 -m unittest discover -s tests -v` before submitting a change. Tests need system PyGObject/GTK/Cairo and PyYAML (see README). They must use fixtures or mocked transports, never real HID writes.

For protocol changes, include a minimal annotated capture and explain the user action, bytes observed, expected state and physical result. Do not infer new commands from unrelated hardware. Preserve fields outside the requested change and retain descriptor checks, checksums, timeouts and device locking.

Keep Spanish and English interface strings synchronized. Changes to tray behavior should retain the reduced sensor/UI work while hidden. Contributions to code and documentation use the project's MIT license; third-party artwork retains its own rights.
