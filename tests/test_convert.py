"""Tests for modules/convert.py — ID lookups across sources."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import modules.builder  # noqa: F401


class TestConvert:
    @pytest.fixture
    def adapter(self):
        from modules.convert import Convert

        c = Convert.__new__(Convert)
        c.requests = MagicMock()
        c.cache = MagicMock()
        c.tmdb = MagicMock()
        return c

    def test_tmdb_to_imdb_cache_hit(self, adapter):
        adapter.cache.query_imdb_to_tmdb_map.return_value = ("tt999", False)
        assert adapter.tmdb_to_imdb(550, is_movie=True, fail=False) == "tt999"

    def test_imdb_to_tmdb_cache_hit(self, adapter):
        adapter.cache.query_imdb_to_tmdb_map.return_value = (550, False, None)
        tmdb_id, _ = adapter.imdb_to_tmdb("tt123", fail=False)
        assert tmdb_id == 550

    def test_tmdb_to_tvdb_cache_hit(self, adapter):
        adapter.cache.query_tmdb_to_tvdb_map.return_value = (368207, False)
        assert adapter.tmdb_to_tvdb(550, fail=False) == 368207

    def test_tvdb_to_tmdb_cache_hit(self, adapter):
        adapter.cache.query_tmdb_to_tvdb_map.return_value = (550, False)
        assert adapter.tvdb_to_tmdb(368207, fail=False) == 550

    def test_hama_suffix_extracts_trailing_id(self):
        from modules.convert import Convert

        assert Convert._hama_suffix("anidb-12345") == "12345"
        assert Convert._hama_suffix("tvdb-67890") == "67890"
        # Hama also has an 'aNNN' anidb format the call sites peel a prefix off later;
        # _hama_suffix just returns everything after the first dash unchanged.
        assert Convert._hama_suffix("anidb-a987") == "a987"

    def test_hama_suffix_raises_on_malformed_id(self):
        from modules.convert import Convert
        from modules.util import MappingConvertError

        with pytest.raises(MappingConvertError, match="Malformed Hama ID 'anidb'"):
            Convert._hama_suffix("anidb")

    def test_invalid_numeric_imdb_cache_value_is_removed(self, adapter):
        item = MagicMock(ratingKey="6120269", guid="6120269", title="Pokémon Chronicles - The Legend of Thunder")
        library = MagicMock(is_movie=True, is_show=False, is_other=False)
        adapter.cache.query_guid_map.return_value = ([295613], ["295613"], "movie", False)

        media_type, media_ids, imdb_ids = adapter.get_id(item, library, provider_ids=["295613", None, "295613"])

        assert (media_type, media_ids, imdb_ids) == ("movie", [295613], [])
        adapter.cache.update_guid_map.assert_called_once_with("6120269", "295613", None, True, "movie")

    def test_movie_with_only_tmdb_never_uses_tmdb_as_imdb(self, adapter):
        adapter.cache = None
        adapter.tmdb.convert_from.return_value = None
        item = MagicMock(ratingKey="6120269", guid="6120269", title="Pokémon Chronicles - The Legend of Thunder")
        library = MagicMock(is_movie=True, is_show=False, is_other=False)

        media_type, media_ids, imdb_ids = adapter.get_id(item, library, provider_ids=[None, None, "295613"])

        assert (media_type, media_ids, imdb_ids) == ("movie", [295613], [])

    def test_valid_movie_provider_ids_keep_documented_types(self, adapter):
        adapter.cache = None
        item = MagicMock(ratingKey="1", guid="1", title="Movie")
        library = MagicMock(is_movie=True, is_show=False, is_other=False)

        assert adapter.get_id(item, library, provider_ids=["tt1234567", None, "550"]) == ("movie", [550], ["tt1234567"])

    def test_valid_series_provider_ids_keep_documented_types(self, adapter):
        adapter.cache = None
        item = MagicMock(ratingKey="2", guid="2", title="Series")
        library = MagicMock(is_movie=False, is_show=True, is_other=False)

        assert adapter.get_id(item, library, provider_ids=["tt7654321", "81189", None]) == ("show", [81189], ["tt7654321"])
