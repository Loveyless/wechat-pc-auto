#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TAURI_CONFIG="$ROOT_DIR/src-tauri/tauri.conf.json"

read_json_field() {
  python3 - "$1" "$2" <<'PY2'
import json, sys
path = sys.argv[1]
field = sys.argv[2]
value = json.loads(open(path, 'r', encoding='utf-8').read())
for part in field.split('.'):
    value = value[part]
print(value)
PY2
}

APP_NAME="$(read_json_field "$TAURI_CONFIG" productName)"
APP_IDENTIFIER="${APP_IDENTIFIER:-$(read_json_field "$TAURI_CONFIG" identifier)}"
APP_VERSION="$(read_json_field "$TAURI_CONFIG" version)"
SIGN_IDENTITY="${SIGN_IDENTITY:--}"
APP_PATH="$ROOT_DIR/src-tauri/target/release/bundle/macos/${APP_NAME}.app"
DMG_DIR="$ROOT_DIR/src-tauri/target/release/bundle/dmg"
DMG_PATH="$DMG_DIR/${APP_NAME}_${APP_VERSION}_aarch64.dmg"

cd "$ROOT_DIR"

echo "==> Building macOS app bundle"
pnpm tauri build --bundles app

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH" >&2
  exit 1
fi

echo "==> Re-signing app with stable identifier: $APP_IDENTIFIER"
rm -rf "$APP_PATH/Contents/_CodeSignature"
while IFS= read -r -d '' bin; do
  codesign --force --sign "$SIGN_IDENTITY" --identifier "$APP_IDENTIFIER" "$bin"
done < <(find "$APP_PATH/Contents/MacOS" -type f -perm -111 -print0)
codesign --force --sign "$SIGN_IDENTITY" --identifier "$APP_IDENTIFIER" "$APP_PATH"

codesign --verify --deep --verbose=2 "$APP_PATH"
codesign -dv --verbose=4 "$APP_PATH" 2>&1 | sed -n '1,24p'

echo "==> Creating DMG"
mkdir -p "$DMG_DIR"
rm -f "$DMG_PATH"
tmpdir="$(mktemp -d /tmp/wechat-pc-auto-release.XXXXXX)"
trap 'rm -rf "$tmpdir"' EXIT
ln -s /Applications "$tmpdir/Applications"
cp -R "$APP_PATH" "$tmpdir/${APP_NAME}.app"
hdiutil create -volname "$APP_NAME" -srcfolder "$tmpdir" -ov -format UDZO "$DMG_PATH"

echo "==> Done"
echo "APP: $APP_PATH"
echo "DMG: $DMG_PATH"
