# Spotify Like Hotkey

A tiny, local macOS utility that toggles the currently playing Spotify track with one shortcut.

If the track came from an editable playlist, liking it also adds it to that playlist. Unliking removes only playlist entries that this utility previously added.

## Keyboard shortcut

> **⌃ ⌥ ⌘ L** — **Control + Option + Command + L**

Press once to like the current track. Press the same shortcut again to unlike it.

## Requirements

- macOS 13 or newer
- Spotify Premium
- Python 3.9 or newer (provided by Xcode Command Line Tools)
- Xcode Command Line Tools (`xcode-select --install`)

## Install

1. Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. In the app settings, add this exact redirect URI:

   ```text
   http://127.0.0.1:8989/callback
   ```

3. Clone and install:

   ```sh
   git clone https://github.com/leonardtang/spotify-like-hotkey.git
   cd spotify-like-hotkey
   ./install.sh YOUR_SPOTIFY_CLIENT_ID
   ```

4. Approve Spotify access in the browser and allow notifications when macOS asks.

The installer builds the notification helper locally, installs a macOS Quick Action, and assigns **Control–Option–Command–L**. To choose another shortcut, open **System Settings → Keyboard → Keyboard Shortcuts → Services → General**.

## Behavior

- Tracks played from an editable playlist are added to that playlist when liked.
- Unliking removes a track from playlists only when this utility added it there.
- Notifications appear immediately and remove themselves after six seconds.
- Podcasts, audiobooks, and other non-track items are left unchanged.

## Privacy and permissions

- Spotify OAuth uses Authorization Code with PKCE.
- The callback server listens only on `127.0.0.1` and only during sign-in.
- OAuth tokens are stored in macOS Keychain.
- Playlist bookkeeping stays in a local file on your Mac.
- The shortcut does not control Spotify or the frontmost app through macOS Automation.
- There is no hosted service, analytics, or third-party data collection.

Each user supplies their own Spotify Client ID. A client secret is neither requested nor stored.

## Troubleshooting

- **No banner appears:** turn off Focus/Do Not Disturb and allow **Spotify Like** in **System Settings → Notifications**.
- **The shortcut does nothing:** quit and reopen the current app, then confirm the shortcut under **Keyboard Shortcuts → Services → General**.
- **Nothing is playing:** start a regular music track in Spotify and try again.
- **Authorization fails:** verify that the redirect URI in Spotify exactly matches `http://127.0.0.1:8989/callback`, then run:

  ```sh
  ~/.local/share/spotify-like-hotkey/spotify_like.py auth
  ```

## Update

Pull the latest version and rerun the installer with the same Spotify Client ID:

```sh
git pull --ff-only
./install.sh YOUR_SPOTIFY_CLIENT_ID
```

## Uninstall

```sh
./uninstall.sh
```

## Development

Run the test suite:

```sh
python3 -m unittest discover -s tests -v
```

Build the notification helper without installing it:

```sh
./build_notifier.sh "/tmp/Spotify Like.app"
```

The project uses Python's standard library and native macOS frameworks; it has no package dependencies.

## License

[MIT](LICENSE). Spotify Like Hotkey is unofficial and is not affiliated with or endorsed by Spotify.
