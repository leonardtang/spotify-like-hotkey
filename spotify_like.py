#!/usr/bin/env python3
"""Save the current Spotify desktop track on macOS."""

import argparse
import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


APP_ID = "com.spotify-like-hotkey"
KEYCHAIN_SERVICE = APP_ID + ".oauth"
CONFIG_DIR = Path.home() / ".config" / "spotify-like-hotkey"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_DIR = Path.home() / ".local" / "state" / "spotify-like-hotkey"
STATE_FILE = STATE_DIR / "playlist_additions.json"
NOTIFIER_STATUS_FILE = STATE_DIR / "notifier-status.txt"
NOTIFIER_APP = Path.home() / ".local" / "share" / "spotify-like-hotkey" / "Spotify Like.app"
REDIRECT_URI = "http://127.0.0.1:8989/callback"
SCOPE = " ".join(
    (
        "user-library-modify",
        "user-library-read",
        "user-read-playback-state",
        "playlist-read-private",
        "playlist-read-collaborative",
        "playlist-modify-public",
        "playlist-modify-private",
    )
)


class SpotifyError(RuntimeError):
    pass


def notify(message, title="Spotify Like"):
    native_notifier = NOTIFIER_APP / "Contents" / "MacOS" / "SpotifyLikeNotifier"
    if native_notifier.exists():
        try:
            notification_status = NOTIFIER_STATUS_FILE.read_text().strip()
        except FileNotFoundError:
            notification_status = ""
        authorized = notification_status in {
            "authorization=2",
            "authorization=3",
            "authorization=4",
        }
        if authorized:
            subprocess.Popen(
                [
                    "/usr/bin/open",
                    "-g",
                    "-n",
                    "-a",
                    str(NOTIFIER_APP),
                    "--args",
                    title,
                    message,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        if notification_status in {"", "authorization=0"}:
            subprocess.Popen(
                [
                    "/usr/bin/open",
                    "-n",
                    "-a",
                    str(NOTIFIER_APP),
                    "--args",
                    title,
                    message,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    script = (
        "on run argv\n"
        "display notification (item 2 of argv) with title (item 1 of argv)\n"
        "end run"
    )
    subprocess.Popen(
        ["/usr/bin/osascript", "-e", script, "--", title, message],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def keychain_read():
    result = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            os.environ.get("USER", ""),
            "-s",
            KEYCHAIN_SERVICE,
            "-w",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SpotifyError("The saved Spotify authorization is invalid; run auth again.") from exc


def keychain_write(token):
    encoded = json.dumps(token, separators=(",", ":"))
    result = subprocess.run(
        [
            "/usr/bin/security",
            "add-generic-password",
            "-U",
            "-a",
            os.environ.get("USER", ""),
            "-s",
            KEYCHAIN_SERVICE,
            "-w",
            encoded,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SpotifyError("Could not save Spotify authorization in macOS Keychain.")


def client_id_from_config():
    env_value = os.environ.get("SPOTIFY_CLIENT_ID")
    if env_value:
        return env_value.strip()
    try:
        return json.loads(CONFIG_FILE.read_text())["client_id"].strip()
    except (FileNotFoundError, KeyError, json.JSONDecodeError, AttributeError):
        raise SpotifyError(
            "Spotify Client ID is not configured. Run: spotify_like.py configure CLIENT_ID"
        )


def configure(client_id):
    if not client_id.strip():
        raise SpotifyError("Client ID cannot be empty.")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"client_id": client_id.strip()}, indent=2) + "\n")
    CONFIG_FILE.chmod(0o600)


def playlist_additions():
    try:
        value = json.loads(STATE_FILE.read_text())
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_playlist_additions(value):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    STATE_FILE.chmod(0o600)


def remember_playlist_addition(track_uri, playlist_id, playlist_name):
    additions = playlist_additions()
    records = additions.setdefault(track_uri, [])
    if not any(record.get("playlist_id") == playlist_id for record in records):
        records.append({"playlist_id": playlist_id, "playlist_name": playlist_name})
        save_playlist_additions(additions)


def form_request(url, fields):
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(request, timeout=15).read())


def authorize():
    client_id = client_id_from_config()
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    response = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_error(404)
                return
            response.update({k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()})
            ok = response.get("state") == state and "code" in response
            body = (
                "Spotify authorization complete. You can close this tab."
                if ok
                else "Spotify authorization failed. Return to Terminal for details."
            ).encode()
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": state,
    }
    server = HTTPServer(("127.0.0.1", 8989), CallbackHandler)
    server.timeout = 180
    print("Opening Spotify authorization in your browser…")
    webbrowser.open("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params))
    server.handle_request()
    server.server_close()

    if response.get("state") != state:
        raise SpotifyError("Authorization state did not match or the request timed out.")
    if "code" not in response:
        raise SpotifyError("Spotify authorization was denied: " + response.get("error", "unknown error"))
    token = form_request(
        "https://accounts.spotify.com/api/token",
        {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": response["code"],
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )
    token["expires_at"] = int(time.time()) + int(token["expires_in"]) - 60
    token["client_id"] = client_id
    keychain_write(token)
    print("Authorized. The shortcut can now save tracks and update source playlists.")


def access_token():
    token = keychain_read()
    if not token:
        raise SpotifyError("Spotify is not authorized. Run: spotify_like.py auth")
    if int(token.get("expires_at", 0)) > int(time.time()):
        return token["access_token"]
    if not token.get("refresh_token"):
        raise SpotifyError("Spotify authorization expired. Run auth again.")
    refreshed = form_request(
        "https://accounts.spotify.com/api/token",
        {
            "client_id": token.get("client_id") or client_id_from_config(),
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        },
    )
    refreshed.setdefault("refresh_token", token["refresh_token"])
    refreshed["expires_at"] = int(time.time()) + int(refreshed["expires_in"]) - 60
    refreshed["client_id"] = token.get("client_id") or client_id_from_config()
    keychain_write(refreshed)
    return refreshed["access_token"]


def current_track(token):
    status, playback = api_request("https://api.spotify.com/v1/me/player", token)
    if status == 204 or not playback:
        raise SpotifyError("Nothing is playing in Spotify.")
    item = playback.get("item") or {}
    uri = item.get("uri", "")
    if item.get("type") != "track" or not uri.startswith("spotify:track:"):
        raise SpotifyError("The current Spotify item is not a saveable track.")
    name = item.get("name") or "Unknown track"
    artist = ", ".join(
        value.get("name", "") for value in item.get("artists", []) if value.get("name")
    ) or "Unknown artist"
    context = playback.get("context") or {}
    context_uri = context.get("uri", "")
    playlist_id = None
    if context.get("type") == "playlist" and context_uri.startswith("spotify:playlist:"):
        playlist_id = context_uri.removeprefix("spotify:playlist:")
    return uri, name, artist, playlist_id


def api_request(url, token, method="GET", payload=None, retries=1):
    headers = {"Authorization": "Bearer " + token}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        if exc.code == 429 and retries:
            delay = min(int(exc.headers.get("Retry-After", "1")), 10)
            time.sleep(delay)
            return api_request(url, token, method, payload, retries - 1)
        try:
            detail = json.loads(exc.read()).get("error", {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            detail = ""
        raise SpotifyError(f"Spotify API error {exc.code}" + (f": {detail}" if detail else ".")) from exc


def playlist_info(playlist_id, token):
    encoded_id = urllib.parse.quote(playlist_id, safe="")
    status, playlist = api_request(
        f"https://api.spotify.com/v1/playlists/{encoded_id}?fields=name", token
    )
    if status != 200 or not playlist:
        raise SpotifyError("Could not read the source playlist.")
    return playlist.get("name") or "source playlist"


def playlist_contains(playlist_id, track_uri, token):
    encoded_id = urllib.parse.quote(playlist_id, safe="")
    query = urllib.parse.urlencode(
        {"limit": 100, "fields": "next,items(item(uri))"}
    )
    url = f"https://api.spotify.com/v1/playlists/{encoded_id}/items?{query}"
    while url:
        status, page = api_request(url, token)
        if status != 200 or not page:
            raise SpotifyError("Could not inspect the source playlist.")
        for entry in page.get("items", []):
            item = entry.get("item") or entry.get("track") or {}
            if item.get("uri") == track_uri:
                return True
        url = page.get("next")
    return False


def add_to_source_playlist(track_uri, token, playlist_id):
    if not playlist_id:
        return None
    name = playlist_info(playlist_id, token)
    if playlist_contains(playlist_id, track_uri, token):
        return "already", name
    encoded_id = urllib.parse.quote(playlist_id, safe="")
    status, _ = api_request(
        f"https://api.spotify.com/v1/playlists/{encoded_id}/items",
        token,
        method="POST",
        payload={"uris": [track_uri]},
    )
    if status != 201:
        raise SpotifyError(f"Spotify returned unexpected playlist status {status}.")
    remember_playlist_addition(track_uri, playlist_id, name)
    return "added", name


def remove_recorded_playlist_additions(track_uri, token):
    additions = playlist_additions()
    records = additions.get(track_uri, [])
    removed_names = []
    failed_records = []
    for record in records:
        playlist_id = record.get("playlist_id", "")
        if not playlist_id:
            continue
        encoded_id = urllib.parse.quote(playlist_id, safe="")
        try:
            status, _ = api_request(
                f"https://api.spotify.com/v1/playlists/{encoded_id}/items",
                token,
                method="DELETE",
                payload={"items": [{"uri": track_uri}]},
            )
            if status != 200:
                raise SpotifyError(f"Spotify returned playlist status {status}.")
            removed_names.append(record.get("playlist_name") or "source playlist")
        except (SpotifyError, urllib.error.URLError):
            failed_records.append(record)
    if failed_records:
        additions[track_uri] = failed_records
    else:
        additions.pop(track_uri, None)
    save_playlist_additions(additions)
    return removed_names, len(failed_records)


def is_liked(track_uri, token):
    query = urllib.parse.urlencode({"uris": track_uri})
    status, result = api_request(
        "https://api.spotify.com/v1/me/library/contains?" + query, token
    )
    if status != 200 or not isinstance(result, list) or len(result) != 1:
        raise SpotifyError("Could not check whether the current track is liked.")
    return bool(result[0])


def like_current():
    token = access_token()
    uri, name, artist, playlist_id = current_track(token)
    notify(f"Updating “{name}”…")
    query = urllib.parse.urlencode({"uris": uri})
    if is_liked(uri, token):
        status, _ = api_request(
            "https://api.spotify.com/v1/me/library?" + query,
            token,
            method="DELETE",
        )
        if status not in (200, 204):
            raise SpotifyError(f"Spotify returned unexpected status {status}.")
        removed, failed = remove_recorded_playlist_additions(uri, token)
        if removed and not failed:
            playlists = ", ".join(f"“{item}”" for item in removed)
            message = f"Unliked “{name}” and removed it from {playlists}"
        elif failed:
            message = f"Unliked “{name}”; couldn’t remove it from every saved playlist"
        else:
            message = f"Unliked “{name}” — {artist}"
        notify(message)
        print(message)
        return
    status, _ = api_request(
        "https://api.spotify.com/v1/me/library?" + query, token, method="PUT"
    )
    if status not in (200, 204):
        raise SpotifyError(f"Spotify returned unexpected status {status}.")
    playlist_result = add_to_source_playlist(uri, token, playlist_id)
    if playlist_result and playlist_result[0] == "added":
        message = f"Liked “{name}” and added it to “{playlist_result[1]}”"
    elif playlist_result:
        message = f"Liked “{name}”; it’s already in “{playlist_result[1]}”"
    else:
        message = f"Liked “{name}” — {artist}"
    notify(message)
    print(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    config_parser = subparsers.add_parser("configure", help="save a Spotify app Client ID")
    config_parser.add_argument("client_id")
    subparsers.add_parser("auth", help="authorize access to Liked Songs")
    subparsers.add_parser("like", help="toggle the current Spotify track's liked state")
    args = parser.parse_args()
    try:
        if args.command == "configure":
            configure(args.client_id)
            print(f"Saved Client ID in {CONFIG_FILE}")
        elif args.command == "auth":
            authorize()
        else:
            like_current()
    except (SpotifyError, urllib.error.URLError) as exc:
        message = str(exc.reason) if isinstance(exc, urllib.error.URLError) else str(exc)
        notify(message, "Spotify Like failed")
        print("Error: " + message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
