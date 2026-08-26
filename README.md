# Spotify Like Hotkey

A small macOS utility that toggles the currently playing Spotify track with **Control–Option–Command–L**.

When liking a track, the utility also adds it to the active playlist when that playlist is editable and does not already contain the track. When unliking, it removes only playlist entries previously added by this utility.

## Requirements

- macOS
- Spotify Premium account
- Python 3.9 or newer
- Xcode Command Line Tools (`xcode-select --install`)

## Install

1. Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and enable the Web API.
2. Add this exact redirect URI:

   ```text
   http://127.0.0.1:8989/callback
   ```

3. Clone this repository and run:

   ```sh
   ./install.sh YOUR_SPOTIFY_CLIENT_ID
   ```

4. Approve Spotify authorization in the browser and allow notifications when macOS asks.

The installer builds the native notification helper locally, installs a macOS Quick Action, and assigns **Control–Option–Command–L**. Change the shortcut in **System Settings → Keyboard → Keyboard Shortcuts → Services → General**.

## How it works

- Spotify's Web API supplies the current playback state and updates Liked Songs.
- If playback came from an editable playlist, the API adds or removes the track there as appropriate.
- OAuth uses Authorization Code with PKCE. The localhost listener runs only during authorization.
- OAuth tokens are stored in macOS Keychain.
- Playlist additions made by the utility are tracked locally so they can be reversed safely.

The shortcut does not control Spotify or the frontmost app through macOS Automation. There is no hosted service, analytics, or third-party data collection. Each user supplies their own Spotify Client ID.

## Development

Run the tests:

```sh
python3 -m unittest discover -s tests -v
```

Build the notification app without installing it:

```sh
./build_notifier.sh "/tmp/Spotify Like.app"
```

The project uses only Python's standard library and macOS system frameworks.

## Uninstall

```sh
./uninstall.sh
```

## License

[MIT](LICENSE). This is an unofficial project and is not affiliated with or endorsed by Spotify.
