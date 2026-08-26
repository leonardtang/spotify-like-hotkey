#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
install_dir="$HOME/.local/share/spotify-like-hotkey"
service_dir="$HOME/Library/Services"
service_name="Toggle Current Spotify Song.workflow"

if [[ $# -ne 1 ]]; then
  print -u2 "Usage: $0 SPOTIFY_CLIENT_ID"
  exit 2
fi

build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
notifier_app="$build_dir/Spotify Like.app"

"$script_dir/build_notifier.sh" "$notifier_app"

mkdir -p "$install_dir" "$service_dir"
install -m 755 "$script_dir/spotify_like.py" "$install_dir/spotify_like.py"
/usr/bin/ditto "$notifier_app" "$install_dir/Spotify Like.app"
rm -rf "$service_dir/$service_name"
cp -R "$script_dir/$service_name" "$service_dir/$service_name"
/usr/bin/python3 "$install_dir/spotify_like.py" configure "$1"

# Make the newly installed Quick Action visible to the Services menu immediately.
/System/Library/CoreServices/pbs -flush en >/dev/null 2>&1 || true
/System/Library/CoreServices/pbs -update en >/dev/null 2>&1 || true

defaults write -g NSUserKeyEquivalents -dict-add \
  "Toggle Current Spotify Song" -string '@^~l'

print "Installed global shortcut: Control-Option-Command-L"
print "Now authorizing Spotify (your browser will open)…"
/usr/bin/python3 "$install_dir/spotify_like.py" auth
print "Done. If the shortcut is not active immediately, quit and reopen the current app."
