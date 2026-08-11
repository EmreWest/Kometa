from __future__ import annotations

import os
from types import SimpleNamespace

from PIL import Image

from modules.emby import Emby, normalize_collection_poster
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


def test_normalize_collection_poster_contains_wide_transparent_image():
    source = Image.new("RGBA", (400, 100), color=(255, 0, 0, 128))

    result = normalize_collection_poster(source)

    assert result.size == (1000, 1500)
    assert result.mode == "RGBA"
    assert result.getchannel("A").getbbox() == (0, 625, 1000, 875)
    assert result.getpixel((500, 750)) == (255, 0, 0, 128)
    assert result.getpixel((500, 100)) == (0, 0, 0, 0)


def test_normalize_collection_poster_scales_two_by_three_image_to_target():
    source = Image.new("RGB", (200, 300), color=(255, 0, 0))

    result = normalize_collection_poster(source)

    assert result.size == (1000, 1500)
    assert result.getbbox() == (0, 0, 1000, 1500)


def test_prepare_collection_poster_preserves_selected_asset_identity(tmp_path):
    source_path = tmp_path / "poster.jpg"
    Image.new("RGB", (800, 400), color=(255, 0, 0)).save(source_path)
    source = ImageData("asset_directory", str(source_path), prefix="Collection's ", is_url=False)
    emby = Emby.__new__(Emby)
    emby.normalize_emby_collection_posters = True

    prepared, cleanup_path = emby.prepare_collection_poster(source)
    try:
        with Image.open(prepared.location) as normalized:
            assert normalized.size == (1000, 1500)
        assert prepared.attribute == "asset_directory"
        assert prepared.is_poster is True
        assert prepared.is_logo is False
        assert prepared.compare == f"{source.compare}:emby-collection-poster:1000x1500"
    finally:
        os.remove(cleanup_path)


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


def test_emby_provider_ids_reject_numeric_imdb_id(monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr("modules.emby_server.logger", fake_logger)
    server = EmbyServer.__new__(EmbyServer)
    server.get_item = lambda _: {"Type": "Movie", "ProviderIds": {"Tmdb": "295613", "Imdb": "295613"}}
    item = SimpleNamespace(ratingKey="6120269", title="Pokémon Chronicles - The Legend of Thunder")

    assert server.get_provider_ids(item) == [None, None, 295613]
    assert any("invalid IMDb ID '295613'" in message for message in fake_logger.warning_messages)


class CollectionMetadataServer:
    def __init__(self, items):
        self.items = items
        self.update_calls = []
        self.create_calls = []

    def get_item(self, item_id):
        return self.items[str(item_id)]

    def update_item(self, item_id, payload):
        item = self.items[str(item_id)]
        item.update(payload)
        if "ForcedSortName" in payload:
            item["SortName"] = payload["ForcedSortName"]
        self.update_calls.append((str(item_id), dict(payload)))
        return SimpleNamespace(status_code=204)

    def invalidate_collection_cache(self, *args):
        pass

    def create_collection(self, *args, **kwargs):
        self.create_calls.append((args, kwargs))
        raise AssertionError("existing collections must not be recreated")


def _collection_metadata_emby(specs):
    items = {
        str(index): {
            "Id": str(index),
            "Name": display_name,
            "SortName": display_name,
            "Overview": f"Summary {index}",
            "ImageTags": {"Primary": f"poster-{index}"},
        }
        for index, (display_name, _) in enumerate(specs, start=1)
    }
    server = CollectionMetadataServer(items)
    emby = Emby.__new__(Emby)
    emby.EmbyServer = server
    collections = [
        SimpleNamespace(
            ratingKey=str(index),
            title=display_name,
            titleSort=display_name,
            summary=f"Summary {index}",
            contentRating=None,
            _items=[f"member-{index}"],
        )
        for index, (display_name, _) in enumerate(specs, start=1)
    ]
    return emby, server, collections


def test_emby_collection_sort_names_keep_separator_and_section_order():
    specs = [
        ("🎥 Filme Rangliste Sammlungen", "!020_!Rangliste Sammlungen"),
        ("🎥 Filme IMDb Beliebt", "!020_010IMDb Beliebt"),
        ("🎥 Filme Genre Sammlungen", "!030_!Genre Sammlungen"),
        ("🎥 Filme Action", "!030_010Action"),
    ]
    emby, _, collections = _collection_metadata_emby(specs)

    for collection, (_, sort_title) in zip(collections, specs):
        assert emby.update_collection_metadata(collection, sort_title=sort_title) is True

    assert [collection.title for collection in sorted(collections, key=lambda value: value.titleSort)] == [name for name, _ in specs]
    assert [collection.titleSort for collection in collections] == [sort_title for _, sort_title in specs]
    assert all("🎥 Filme" not in collection.titleSort for collection in collections)


def test_existing_emby_collection_sort_update_is_in_place_and_idempotent():
    specs = [("🎥 Filme IMDb Beliebt", "!020_010IMDb Beliebt")]
    emby, server, collections = _collection_metadata_emby(specs)
    collection = collections[0]
    original_members = collection._items
    original_artwork = dict(server.items["1"]["ImageTags"])

    assert emby.update_collection_metadata(collection, sort_title=specs[0][1]) is True
    assert emby.update_collection_metadata(collection, sort_title=specs[0][1]) is True

    assert server.update_calls == [("1", {"ForcedSortName": "!020_010IMDb Beliebt"})]
    assert server.create_calls == []
    assert collection.ratingKey == "1"
    assert collection._items is original_members
    assert server.items["1"]["ImageTags"] == original_artwork
    assert server.items["1"]["SortName"] == "!020_010IMDb Beliebt"
