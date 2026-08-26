#!/bin/zsh
set -euo pipefail

rm -rf "$HOME/.local/share/spotify-like-hotkey"
rm -rf "$HOME/Library/Services/Toggle Current Spotify Song.workflow"
rm -rf "$HOME/Library/Services/Add Current Spotify Song to Liked Songs.workflow"
rm -rf "$HOME/.config/spotify-like-hotkey"
rm -rf "$HOME/.local/state/spotify-like-hotkey"
/usr/bin/security delete-generic-password -a "$USER" -s com.spotify-like-hotkey.oauth >/dev/null 2>&1 || true
print "Removed Spotify Like Hotkey. The global shortcut entry can be removed in System Settings > Keyboard > Keyboard Shortcuts > Services."
