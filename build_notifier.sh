#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}

if [[ $# -ne 1 ]]; then
  print -u2 "Usage: $0 OUTPUT_APP"
  exit 2
fi

for tool in swiftc lipo sips iconutil codesign; do
  command -v "$tool" >/dev/null || {
    print -u2 "Missing required macOS tool: $tool"
    exit 1
  }
done

output_app=$1
if [[ -e "$output_app" ]]; then
  print -u2 "Output already exists: $output_app"
  exit 1
fi

contents="$output_app/Contents"
resources="$contents/Resources"
macos="$contents/MacOS"
icon_work=$(mktemp -d)
trap 'rm -rf "$icon_work"' EXIT
iconset="$icon_work/SpotifyLike.iconset"

mkdir -p "$resources" "$macos" "$iconset"
cp "$script_dir/notifier/Info.plist" "$contents/Info.plist"

for architecture in arm64 x86_64; do
  swiftc "$script_dir/notifier/notifier.swift" \
    -target "$architecture-apple-macosx13.0" \
    -o "$icon_work/SpotifyLikeNotifier-$architecture" \
    -framework Cocoa \
    -framework UserNotifications
done
lipo -create \
  "$icon_work/SpotifyLikeNotifier-arm64" \
  "$icon_work/SpotifyLikeNotifier-x86_64" \
  -output "$macos/SpotifyLikeNotifier"

for specification in \
  '16 icon_16x16.png' \
  '32 icon_16x16@2x.png' \
  '32 icon_32x32.png' \
  '64 icon_32x32@2x.png' \
  '128 icon_128x128.png' \
  '256 icon_128x128@2x.png' \
  '256 icon_256x256.png' \
  '512 icon_256x256@2x.png' \
  '512 icon_512x512.png' \
  '1024 icon_512x512@2x.png'; do
  size=${specification%% *}
  filename=${specification#* }
  sips -z "$size" "$size" "$script_dir/assets/spotify-like-icon.png" \
    --out "$iconset/$filename" >/dev/null
done

iconutil -c icns "$iconset" -o "$resources/SpotifyLike.icns"
codesign --force --deep --sign - "$output_app" >/dev/null
codesign --verify --deep --strict "$output_app"

print "Built $output_app"
