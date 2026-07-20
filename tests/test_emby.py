from __future__ import annotations

from types import SimpleNamespace

from modules.emby import Emby
from modules.emby_server import EmbyServer
from modules.poster import ImageData
from tests.conftest import FakeLogger


def test_emby_collection_display_name_uses_historical_prefix():
    emby = Emby.__new__(Emby)
    emby.mc_type = "emby"
    emby.name = "Filme"
    emby.type = "Movie"
    emby.is_movie = True
    emby.is_show = False

    assert emby.get_collection_display_name("IMDb Beliebt") == "🎥 Filme IMDb Beliebt"
    assert emby.get_collection_display_name("🎥 Filme IMDb Beliebt") == "🎥 Filme IMDb Beliebt"
    assert emby.get_collection_base_name("🎥 Filme IMDb Beliebt") == "IMDb Beliebt"


def test_emby_collection_display_name_uses_series_prefix_for_anime():
    emby = Emby.__new__(Emby)
    emby.mc_type = "emby"
    emby.name = "Animes"
    emby.type = "Show"
    emby.is_movie = False
    emby.is_show = True

    assert emby.get_collection_display_name("MyAnimeList Saison") == "📺 Animes MyAnimeList Saison"


def test_emby_collection_filter_choices_include_display_and_base_names():
    emby = Emby.__new__(Emby)
    emby.mc_type = "emby"
    emby.name = "Filme"
    emby.type = "Movie"
    emby.lib_type = "movie"
    emby.is_movie = True
    emby.is_show = False
    emby.EmbyServer = SimpleNamespace(is_in_filtertype=lambda tag, libtype: True)
    emby.get_all_collections = lambda label=None: [
        SimpleNamespace(ratingKey="10", title="🎥 Filme IMDb Beliebt"),
        SimpleNamespace(ratingKey="11", title="Legacy Collection"),
    ]

    choices = emby.get_tags("collection")
    choices_by_title = {choice.title: choice.key for choice in choices}

    assert choices_by_title["🎥 Filme IMDb Beliebt"] == "10"
    assert choices_by_title["IMDb Beliebt"] == "10"
    assert choices_by_title["Legacy Collection"] == "11"


def test_validate_image_size_accepts_valid_local_image(tmp_path):
    from PIL import Image

    image_path = tmp_path / "poster.png"
    Image.new("RGB", (2, 3), color="red").save(image_path)

    emby = Emby.__new__(Emby)
    image = ImageData("asset_directory", str(image_path), is_url=False)

    assert emby.validate_image_size(image) is True


def test_validate_image_size_rejects_corrupt_local_image(tmp_path, monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr("modules.library.logger", fake_logger)

    image_path = tmp_path / "poster.png"
    image_path.write_text("not an image")

    emby = Emby.__new__(Emby)
    image = ImageData("asset_directory", str(image_path), is_url=False)

    assert emby.validate_image_size(image) is False
    assert fake_logger.error_messages


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
