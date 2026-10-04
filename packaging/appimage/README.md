# AppImage packaging

Build on Linux x86_64 with Python 3, apt-get/apt-cache, dpkg-deb, fakeroot, curl, binutils, squashfs-tools, desktop-file-utils, patchelf and strace:

```sh
packaging/appimage/build.sh
```

Output is in `dist/`, with a SHA-256 sidecar. The script checks the pinned appimage-builder 1.1.0 binary hash. Its obsolete, unused apt-key prerequisite is removed in the extracted builder. Ubuntu Noble package signatures are checked by apt using the Ubuntu archive key. The recipe includes Python 3.12, GTK4, GTK3/Ayatana, icons and fonts; host GPU drivers are not included. Cairo rendering avoids requiring a bundled OpenGL driver.

The build checks imports, the embedded image and a separate GTK3 process. Run a graphical test with a display available:

```sh
LLANO_TEST_DISPLAY=1 APPIMAGE_EXTRACT_AND_RUN=1 dist/*.AppImage self-test
```

`self-test` never creates the main cooler application and never opens a USB device. The ordinary GUI does apply saved hardware settings at startup. The AppImage has been smoke-tested on PikaOS; other distributions still need validation.

The GitHub Actions workflow tests and builds on Ubuntu 24.04, runs the graphical smoke test in Xvfb and stores a workflow artifact. On release publication it additionally attaches the AppImage and checksum to that release. A manual workflow run builds an artifact without publishing it.

Keep the AppImage at a stable path when using login autostart. The application's autostart entry uses `$APPIMAGE`, not the temporary mounted AppDir. Profiles remain in the standard XDG configuration directory. The device-specific udev rule and host graphics drivers remain external system requirements.
