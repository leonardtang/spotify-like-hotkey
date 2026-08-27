import json
import unittest
from unittest import mock

import spotify_like


class SpotifyLikeTests(unittest.TestCase):
    @mock.patch("spotify_like.api_request")
    def test_current_track(self, request):
        request.return_value = (
            200,
            {
                "item": {
                    "type": "track",
                    "uri": "spotify:track:abc",
                    "name": "The Song",
                    "artists": [{"name": "The Artist"}],
                },
                "context": {
                    "type": "playlist",
                    "uri": "spotify:playlist:list1",
                },
            },
        )
        self.assertEqual(
            spotify_like.current_track("token"),
            ("spotify:track:abc", "The Song", "The Artist", "list1"),
        )

    @mock.patch("spotify_like.api_request")
    def test_rejects_non_track(self, request):
        request.return_value = (
            200,
            {
                "item": {
                    "type": "episode",
                    "uri": "spotify:episode:abc",
                    "name": "Episode",
                }
            },
        )
        with self.assertRaises(spotify_like.SpotifyError):
            spotify_like.current_track("token")

    @mock.patch("spotify_like.urllib.request.urlopen")
    def test_form_request(self, urlopen):
        response = mock.MagicMock()
        response.read.return_value = json.dumps({"access_token": "token"}).encode()
        urlopen.return_value = response
        self.assertEqual(
            spotify_like.form_request("https://example.test", {"a": "b"}),
            {"access_token": "token"},
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.data, b"a=b")

    @mock.patch("spotify_like.api_request")
    def test_playlist_contains_follows_pages(self, request):
        request.side_effect = [
            (200, {"items": [], "next": "https://next.test"}),
            (
                200,
                {
                    "items": [{"item": {"uri": "spotify:track:current"}}],
                    "next": None,
                },
            ),
        ]
        self.assertTrue(
            spotify_like.playlist_contains("list1", "spotify:track:current", "token")
        )
        self.assertEqual(request.call_count, 2)

    @mock.patch("spotify_like.playlist_contains", return_value=False)
    @mock.patch("spotify_like.playlist_info", return_value="My Playlist")
    @mock.patch("spotify_like.remember_playlist_addition")
    @mock.patch("spotify_like.api_request", return_value=(201, {"snapshot_id": "s1"}))
    def test_adds_missing_track_to_source_playlist(
        self, request, remember, _info, _contains
    ):
        self.assertEqual(
            spotify_like.add_to_source_playlist(
                "spotify:track:current", "token", "list1"
            ),
            ("added", "My Playlist"),
        )
        self.assertEqual(request.call_args.kwargs["method"], "POST")
        self.assertEqual(
            request.call_args.kwargs["payload"], {"uris": ["spotify:track:current"]}
        )
        remember.assert_called_once_with(
            "spotify:track:current", "list1", "My Playlist"
        )

    @mock.patch("spotify_like.playlist_contains", return_value=False)
    @mock.patch("spotify_like.playlist_info", return_value="Their Playlist")
    @mock.patch("spotify_like.remember_playlist_addition")
    @mock.patch(
        "spotify_like.api_request",
        side_effect=spotify_like.SpotifyError("Spotify API error 403.", status_code=403),
    )
    def test_reports_uneditable_source_playlist(
        self, _request, remember, _info, _contains
    ):
        self.assertEqual(
            spotify_like.add_to_source_playlist(
                "spotify:track:current", "token", "list1"
            ),
            ("uneditable", "Their Playlist"),
        )
        remember.assert_not_called()

    @mock.patch("spotify_like.playlist_contains")
    @mock.patch(
        "spotify_like.playlist_info",
        side_effect=spotify_like.SpotifyError("Spotify API error 403.", status_code=403),
    )
    def test_reports_uneditable_playlist_when_its_name_is_private(
        self, _info, contains
    ):
        self.assertEqual(
            spotify_like.add_to_source_playlist(
                "spotify:track:current", "token", "list1"
            ),
            ("uneditable", None),
        )
        contains.assert_not_called()

    @mock.patch("spotify_like.notify")
    @mock.patch("builtins.print")
    @mock.patch(
        "spotify_like.add_to_source_playlist",
        return_value=("uneditable", "Their Playlist"),
    )
    @mock.patch("spotify_like.is_liked", return_value=False)
    @mock.patch("spotify_like.access_token", return_value="token")
    @mock.patch(
        "spotify_like.current_track",
        return_value=("spotify:track:current", "The Song", "The Artist", "list1"),
    )
    @mock.patch("spotify_like.api_request", return_value=(200, None))
    def test_likes_track_when_source_playlist_is_uneditable(
        self, _request, _track, _token, _liked, _add, _print, notify
    ):
        spotify_like.like_current()
        self.assertEqual(
            notify.call_args_list[-1],
            mock.call("Liked “The Song”; you can’t edit “Their Playlist”"),
        )

    @mock.patch("spotify_like.notify")
    @mock.patch("builtins.print")
    @mock.patch(
        "spotify_like.remove_recorded_playlist_additions", return_value=([], 0)
    )
    @mock.patch("spotify_like.is_liked", return_value=True)
    @mock.patch("spotify_like.access_token", return_value="token")
    @mock.patch(
        "spotify_like.current_track",
        return_value=("spotify:track:current", "The Song", "The Artist", None),
    )
    @mock.patch("spotify_like.api_request", return_value=(200, None))
    def test_same_command_unlikes_liked_track(
        self, request, _track, _token, _liked, _remove, _print, notify
    ):
        spotify_like.like_current()
        self.assertEqual(request.call_args.kwargs["method"], "DELETE")
        self.assertEqual(
            notify.call_args_list[-1], mock.call("Unliked “The Song” — The Artist")
        )

    @mock.patch("spotify_like.save_playlist_additions")
    @mock.patch(
        "spotify_like.playlist_additions",
        return_value={
            "spotify:track:current": [
                {"playlist_id": "list1", "playlist_name": "My Playlist"}
            ]
        },
    )
    @mock.patch("spotify_like.api_request", return_value=(200, {"snapshot_id": "s2"}))
    def test_removes_only_recorded_playlist_addition(self, request, _load, save):
        result = spotify_like.remove_recorded_playlist_additions(
            "spotify:track:current", "token"
        )
        self.assertEqual(result, (["My Playlist"], 0))
        self.assertEqual(request.call_args.kwargs["method"], "DELETE")
        self.assertEqual(
            request.call_args.kwargs["payload"],
            {"items": [{"uri": "spotify:track:current"}]},
        )
        save.assert_called_once_with({})


if __name__ == "__main__":
    unittest.main()
