#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
version=$(PYTHONPATH="$root" python3 -c 'from llano_control import __version__;print(__version__)')
tools_dir="$root/build/appimage-tools"
mkdir -p "$tools_dir" "$root/dist"
work=$(mktemp -d "$root/build/appimage-work.XXXXXX")
trap 'rm -rf "$work"' EXIT
builder="$tools_dir/appimage-builder-1.1.0.AppImage"
if [ ! -f "$builder" ]; then
  curl -fL --retry 3 https://github.com/AppImageCrafters/appimage-builder/releases/download/v1.1.0/appimage-builder-1.1.0-x86_64.AppImage -o "$builder"
fi
printf '%s  %s\n' 4b4f99cae9291d78ba12dbdabca7c0a67c72aa61eb2e5d424089171a9485e96f "$builder" | sha256sum -c -
chmod +x "$builder"
(cd "$tools_dir" && "$builder" --appimage-extract >/dev/null)
# 1.1.0 checks for apt-key but never uses it. Modern apt removed that binary.
sed -i 's/"apt-key", //' "$tools_dir/squashfs-root/usr/lib/python3.8/site-packages/appimagebuilder/modules/deploy/apt/venv.py"
cp -r "$root/llano_control" "$root/packaging" "$root/LICENSE" "$root/NOTICE.md" "$work/"
(cd "$work" && APP_VERSION="$version" "$tools_dir/squashfs-root/AppRun" --recipe packaging/appimage/AppImageBuilder.yml --skip-test)
asset="Llano-Control-$version-x86_64.AppImage"
cp "$work/$asset" "$root/dist/$asset"
chmod +x "$root/dist/$asset"
(cd "$root/dist" && sha256sum "$asset" > "$asset.sha256")
APPIMAGE_EXTRACT_AND_RUN=1 "$root/dist/$asset" self-test
