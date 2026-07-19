from __future__ import annotations

from types import SimpleNamespace

from modules.emby import Emby
from modules.emby_server import EmbyServer
from tests.conftest import FakeLogger


def test_find_item_assets_returns_six_values_without_square_art(tmp_path):
    emby = Emby.__new__(Emby)
    emby.asset_directory = [str(tmp_path)]
    emby.asset_folders = False
    emby.asset_depth = 0
    emby.create_asset_folders = False
    emby.dimensional_asset_rename = False

    result = emby.find_item_assets("One Piece")

    assert result == (None, None, None, None, None, "One Piece")


def test_convert_emby_to_plex_skips_non_media_items(monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr("modules.emby_server.logger", fake_logger)

    server = EmbyServer.__new__(EmbyServer)
    server.dirty_items = set()
    server.cached_plex_objects = {}

    result = server.convert_emby_to_plex(
        [
            {"Id": "1", "Name": "One Piece Das Strohhut Theater", "Type": "Folder"},
            {"Id": "2", "Name": "Root", "Type": "UserRootFolder"},
            {"Id": "3", "Name": "Collections", "Type": "CollectionFolder"},
            {"Id": "4", "Name": "Aggregate", "Type": "AggregateFolder"},
            {"Id": "5", "Name": "Manual Playlists", "Type": "ManualPlaylistsFolder"},
            {"Id": "6", "Name": "Playlists", "Type": "PlaylistsFolder"},
        ]
    )

    assert result == []
    assert fake_logger.error_messages == []
    assert len(fake_logger.debug_messages) == 6


def test_emby_search_filters_non_media_items(monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr("modules.emby_server.logger", fake_logger)

    server = EmbyServer.__new__(EmbyServer)
    server.emby_server_url = "http://emby"
    server.api_key = "api-key"
    server.headers = {}
    server.dirty_items = set()
    server.cached_plex_objects = {}

    response = SimpleNamespace(
        json=lambda: {
            "Items": [
                {"Id": "1", "Name": "Root", "Type": "UserRootFolder"},
                {"Id": "2", "Name": "Collections", "Type": "CollectionFolder"},
            ]
        },
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr("modules.emby_server.requests.get", lambda *args, **kwargs: response)

    result = server.search(title="Collections")

    assert result == []
    assert fake_logger.error_messages == []
    assert len(fake_logger.debug_messages) == 2
