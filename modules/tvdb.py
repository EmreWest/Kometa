import re
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

from lxml import html
from lxml.etree import ParserError
from requests.exceptions import MissingSchema, RequestException

from modules import util
from modules.util import Failed

logger = util.logger


class NotFound(Failed):
    """Raised when TVDb gives a definitive HTTP 4xx for a resource - i.e. TVDb itself confirms there is nothing at this ID."""


class Unavailable(Failed):
    """Raised when TVDb never returned usable content after retries were exhausted (e.g. repeated 202/empty-body); not a confirmed absence like NotFound."""


class TVDbServerError(Exception):
    """Raised for 5xx responses from TVDb; not a Failed subclass so tenacity's retry_if_not_exception_type(Failed) will retry it."""


builders = ["tvdb_list", "tvdb_list_details", "tvdb_movie", "tvdb_movie_details", "tvdb_show", "tvdb_show_details"]
base_url = "https://www.thetvdb.com"
alt_url = "https://thetvdb.com"
urls = {
    "list": f"{base_url}/lists/",
    "alt_list": f"{alt_url}/lists/",
    "series": f"{base_url}/series/",
    "alt_series": f"{alt_url}/series/",
    "movies": f"{base_url}/movies/",
    "alt_movies": f"{alt_url}/movies/",
    "series_id": f"{base_url}/dereferrer/series/",
    "movie_id": f"{base_url}/dereferrer/movie/",
}
language_translation = {
    "ab": "abk",
    "aa": "aar",
    "af": "afr",
    "ak": "aka",
    "sq": "sqi",
    "am": "amh",
    "ar": "ara",
    "an": "arg",
    "hy": "hye",
    "as": "asm",
    "av": "ava",
    "ae": "ave",
    "ay": "aym",
    "az": "aze",
    "bm": "bam",
    "ba": "bak",
    "eu": "eus",
    "be": "bel",
    "bn": "ben",
    "bi": "bis",
    "bs": "bos",
    "br": "bre",
    "bg": "bul",
    "my": "mya",
    "ca": "cat",
    "ch": "cha",
    "ce": "che",
    "ny": "nya",
    "zh": "zho",
    "cv": "chv",
    "kw": "cor",
    "co": "cos",
    "cr": "cre",
    "hr": "hrv",
    "cs": "ces",
    "da": "dan",
    "dv": "div",
    "nl": "nld",
    "dz": "dzo",
    "en": "eng",
    "eo": "epo",
    "et": "est",
    "ee": "ewe",
    "fo": "fao",
    "fj": "fij",
    "fi": "fin",
    "fr": "fra",
    "ff": "ful",
    "gl": "glg",
    "ka": "kat",
    "de": "deu",
    "el": "ell",
    "gn": "grn",
    "gu": "guj",
    "ht": "hat",
    "ha": "hau",
    "he": "heb",
    "hz": "her",
    "hi": "hin",
    "ho": "hmo",
    "hu": "hun",
    "ia": "ina",
    "id": "ind",
    "ie": "ile",
    "ga": "gle",
    "ig": "ibo",
    "ik": "ipk",
    "io": "ido",
    "is": "isl",
    "it": "ita",
    "iu": "iku",
    "ja": "jpn",
    "jv": "jav",
    "kl": "kal",
    "kn": "kan",
    "kr": "kau",
    "ks": "kas",
    "kk": "kaz",
    "km": "khm",
    "ki": "kik",
    "rw": "kin",
    "ky": "kir",
    "kv": "kom",
    "kg": "kon",
    "ko": "kor",
    "ku": "kur",
    "kj": "kua",
    "la": "lat",
    "lb": "ltz",
    "lg": "lug",
    "li": "lim",
    "ln": "lin",
    "lo": "lao",
    "lt": "lit",
    "lu": "lub",
    "lv": "lav",
    "gv": "glv",
    "mk": "mkd",
    "mg": "mlg",
    "ms": "msa",
    "ml": "mal",
    "mt": "mlt",
    "mi": "mri",
    "mr": "mar",
    "mh": "mah",
    "mn": "mon",
    "na": "nau",
    "nv": "nav",
    "nd": "nde",
    "ne": "nep",
    "ng": "ndo",
    "nb": "nob",
    "nn": "nno",
    "no": "nor",
    "ii": "iii",
    "nr": "nbl",
    "oc": "oci",
    "oj": "oji",
    "cu": "chu",
    "om": "orm",
    "or": "ori",
    "os": "oss",
    "pa": "pan",
    "pi": "pli",
    "fa": "fas",
    "pl": "pol",
    "ps": "pus",
    "pt": "por",
    "qu": "que",
    "rm": "roh",
    "rn": "run",
    "ro": "ron",
    "ru": "rus",
    "sa": "san",
    "sc": "srd",
    "sd": "snd",
    "se": "sme",
    "sm": "smo",
    "sg": "sag",
    "sr": "srp",
    "gd": "gla",
    "sn": "sna",
    "si": "sin",
    "sk": "slk",
    "sl": "slv",
    "so": "som",
    "st": "sot",
    "es": "spa",
    "su": "sun",
    "sw": "swa",
    "ss": "ssw",
    "sv": "swe",
    "ta": "tam",
    "te": "tel",
    "tg": "tgk",
    "th": "tha",
    "ti": "tir",
    "bo": "bod",
    "tk": "tuk",
    "tl": "tgl",
    "tn": "tsn",
    "to": "ton",
    "tr": "tur",
    "ts": "tso",
    "tt": "tat",
    "tw": "twi",
    "ty": "tah",
    "ug": "uig",
    "uk": "ukr",
    "ur": "urd",
    "uz": "uzb",
    "ve": "ven",
    "vi": "vie",
    "vo": "vol",
    "wa": "wln",
    "cy": "cym",
    "wo": "wol",
    "fy": "fry",
    "xh": "xho",
    "yi": "yid",
    "yo": "yor",
    "za": "zha",
    "zu": "zul",
}


class TVDbObj:
    def __init__(self, tvdb, tvdb_id, is_movie=False, ignore_cache=False):
        self._tvdb = tvdb
        self.tvdb_id = tvdb_id
        self.is_movie = is_movie
        self.ignore_cache = ignore_cache
        expired = None
        data = None
        if self._tvdb.cache and not ignore_cache:
            data, expired = self._tvdb.cache.query_tvdb(tvdb_id, is_movie, self._tvdb.expiration)
        if expired or not data:
            item_url = f"{urls['movie_id' if is_movie else 'series_id']}{tvdb_id}"
            try:
                data = self._tvdb.get_request(item_url)
            except NotFound:
                raise NotFound(f"TVDb Error: No {'Movie' if is_movie else 'Series'} found for TVDb ID: {tvdb_id} at {item_url}")
            except Unavailable:
                # Already has its own accurate message - don't relabel it as "No Series/Movie found"
                raise
            except Failed:
                raise

        def parse_page(xpath, is_list=False):
            parse_results = data.xpath(xpath)
            if len(parse_results) > 0:
                parse_results = [r.strip() for r in parse_results if len(r) > 0]
            return parse_results if is_list else parse_results[0] if len(parse_results) > 0 else None

        def parse_title_summary(lang=None):
            place = "//div[@class='change_translation_text' and "
            place += f"@data-language='{lang}']" if lang else "not(@style='display:none')]"
            return parse_page(f"{place}/@data-title"), parse_page(f"{place}/p/text()[normalize-space()]")

        if isinstance(data, dict):
            self.title = data["title"]
            self.summary = data["summary"]
            self.poster_url = data["poster_url"]
            self.background_url = data["background_url"]
            self.logo_url = data.get("logo_url", "")
            self.icon_url = data.get("icon_url", "")
            self.release_date = data["release_date"]
            self.status = data["status"]
            self.genres = data["genres"].split("|")
        else:
            self.title, self.summary = parse_title_summary(lang=self._tvdb.language)
            if not self.title and self._tvdb.language in language_translation:
                self.title, self.summary = parse_title_summary(lang=language_translation[self._tvdb.language])
            if not self.title:
                self.title, self.summary = parse_title_summary()
            if not self.title:
                raise Failed(f"TVDb Error: Name not found from TVDb ID: {self.tvdb_id}")

            self.poster_url = parse_page("//div[@id='artwork-posters']//a/@href")
            self.background_url = parse_page("//div[@id='artwork-backgrounds']//a/@href")
            self.logo_url = parse_page("//div[@id='artwork-clearlogo']//a/@href")
            self.icon_url = parse_page("//div[@id='artwork-icons']//a/@href")
            if is_movie:
                released = parse_page("//strong[text()='Released']/parent::li/span/text()[normalize-space()]")
            else:
                released = parse_page("//strong[text()='First Aired']/parent::li/span/text()[normalize-space()]")

            try:
                self.release_date = datetime.strptime(str(released), "%B %d, %Y") if released else released  # noqa
            except ValueError:
                self.release_date = None
            self.status = parse_page("//strong[text()='Status']/parent::li/span/text()[normalize-space()]")

            self.genres = parse_page("//strong[text()='Genres']/parent::li/span/a/text()[normalize-space()]", is_list=True)

        if self._tvdb.cache and not ignore_cache:
            self._tvdb.cache.update_tvdb(expired, self, self._tvdb.expiration)


class TVDb:
    request_attempts = 4

    def __init__(self, requests, cache, tvdb_language, expiration):
        self.requests = requests
        self.cache = cache
        self.language = tvdb_language
        self.expiration = expiration

    def get_tvdb_obj(self, tvdb_url, is_movie=False):
        tvdb_id, _, _ = self.get_id_from_url(tvdb_url, is_movie=is_movie)
        return TVDbObj(self, tvdb_id, is_movie=is_movie)

    @staticmethod
    def _safe_url(url):
        parts = urlsplit(str(url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _retry_after(response, default):
        value = response.headers.get("Retry-After") if getattr(response, "headers", None) else None
        if value:
            try:
                return max(float(value), 0)
            except (TypeError, ValueError):
                try:
                    retry_at = parsedate_to_datetime(value)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    return max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0)
                except (TypeError, ValueError, OverflowError):
                    pass
        return default

    @staticmethod
    def _response_details(response, requested_url, attempt):
        headers = getattr(response, "headers", {}) or {}
        content = getattr(response, "content", b"") or b""
        final_url = TVDb._safe_url(getattr(response, "url", requested_url) or requested_url)
        requested_safe = TVDb._safe_url(requested_url)
        redirect = final_url if final_url != requested_safe or getattr(response, "history", None) else "none"
        return (
            f"attempt={attempt}/{TVDb.request_attempts} url={requested_safe} "
            f"status={getattr(response, 'status_code', 'unknown')} "
            f"content_type={headers.get('Content-Type', 'missing')} "
            f"content_length={headers.get('Content-Length', 'missing')} body_length={len(content)} "
            f"retry_after={headers.get('Retry-After', 'missing')} redirect={redirect}"
        )

    def get_request(self, tvdb_url):
        safe_url = self._safe_url(tvdb_url)
        last_reason = "unknown response"
        request_method = getattr(self.requests, "get_once", None) or self.requests.get
        for attempt in range(1, self.request_attempts + 1):
            response = None
            try:
                response = request_method(tvdb_url, language=self.language)
                logger.debug(f"TVDb Request: {self._response_details(response, tvdb_url, attempt)}")
            except RequestException as e:
                last_reason = f"network {type(e).__name__}: {e}"
                logger.debug(f"TVDb Request: attempt={attempt}/{self.request_attempts} url={safe_url} exception={type(e).__name__}: {e}")
                if attempt == self.request_attempts:
                    raise Unavailable(f"TVDb Error: Network failure for {safe_url} after {attempt} attempt(s): {type(e).__name__}: {e}") from e
            except Exception as e:
                raise Failed(f"TVDb Error: Request failed for {safe_url}: {type(e).__name__}: {e}") from e

            if response is not None:
                status = response.status_code
                reason = getattr(response, "reason", "") or "HTTP error"
                if status == 404:
                    raise NotFound(f"TVDb Error: HTTP 404; resource does not exist at {safe_url}")
                if 400 <= status < 500 and status not in [408, 429]:
                    label = "Authentication failed" if status == 401 else "Access denied" if status == 403 else reason
                    raise Failed(f"TVDb Error: HTTP {status} {label} for {safe_url}; not retrying")
                if status == 429:
                    last_reason = "HTTP 429 Rate Limit"
                elif status == 408:
                    last_reason = "HTTP 408 Request Timeout"
                elif status >= 500:
                    last_reason = f"HTTP {status} Server Error: {reason}"
                elif status != 200:
                    raise Failed(f"TVDb Error: Unexpected HTTP {status} for {safe_url}: {reason}")
                else:
                    content = getattr(response, "content", b"") or b""
                    content_type = (getattr(response, "headers", {}) or {}).get("Content-Type", "").split(";", 1)[0].lower()
                    if not content.strip():
                        last_reason = "HTTP 200 with empty body"
                    elif content_type and content_type not in ["text/html", "application/xhtml+xml"]:
                        last_reason = f"HTTP 200 with unexpected Content-Type {content_type}"
                    else:
                        try:
                            return html.fromstring(content)
                        except (ParserError, TypeError, ValueError) as e:
                            last_reason = f"HTTP 200 parsing failure {type(e).__name__}: {e}"

            if attempt < self.request_attempts:
                base_delay = min(2 ** (attempt - 1), 8)
                delay = self._retry_after(response, base_delay) if response is not None and response.status_code == 429 else base_delay
                delay += random.uniform(0, 0.5)
                logger.debug(f"TVDb Retry: attempt={attempt}/{self.request_attempts} url={safe_url} reason={last_reason} wait={delay:.2f}s")
                time.sleep(delay)

        raise Unavailable(f"TVDb Error: No usable response from TVDb for {safe_url} after {self.request_attempts} attempt(s): {last_reason}")

    def get_id_from_url(self, tvdb_url, is_movie=False, ignore_cache=False):
        try:
            if not is_movie:
                return int(tvdb_url), None, None
            else:
                tvdb_url = f"{urls['movie_id']}{int(tvdb_url)}"
        except ValueError:
            pass
        tvdb_url = tvdb_url.strip()
        if tvdb_url.startswith((urls["series"], urls["alt_series"], urls["series_id"])):
            media_type = "Series"
        elif tvdb_url.startswith((urls["movies"], urls["alt_movies"], urls["movie_id"])):
            media_type = "Movie"
        else:
            raise Failed(f"TVDb Error: {tvdb_url} must begin with {urls['movies']} or {urls['series']}")
        expired = None
        if self.cache and not ignore_cache and not is_movie:
            tvdb_id, expired = self.cache.query_tvdb_map(tvdb_url, self.expiration)
            if tvdb_id and not expired:
                return tvdb_id, None, None
        logger.trace(f"URL: {tvdb_url}")
        try:
            response = self.get_request(tvdb_url)
        except (NotFound, Unavailable, Failed):
            raise
        except ParserError as e:
            raise Failed(f"TVDb Error: Failed to parse {self._safe_url(tvdb_url)}: {type(e).__name__}: {e}") from e
        results = response.xpath(f"//*[text()='TheTVDB.com {media_type} ID']/parent::node()/span/text()")
        if len(results) > 0:
            tvdb_id = int(results[0])
            tmdb_id = None
            imdb_id = None
            if media_type == "Movie":
                results = response.xpath("//*[text()='TheMovieDB.com']/@href")
                if len(results) > 0:
                    try:
                        tmdb_id = util.regex_first_int(results[0], "TMDb ID")
                    except Failed:
                        pass
                results = response.xpath("//*[text()='IMDB']/@href")
                if len(results) > 0:
                    try:
                        imdb_id = util.get_id_from_imdb_url(results[0])
                    except Failed:
                        pass
                if tmdb_id is None and imdb_id is None:
                    raise Failed("TVDb Error: No TMDb ID or IMDb ID found")
            if self.cache and not ignore_cache and not is_movie:
                self.cache.update_tvdb_map(expired, tvdb_url, tvdb_id, self.expiration)
            return tvdb_id, tmdb_id, imdb_id
        elif tvdb_url.startswith(urls["movie_id"]):
            err_text = f"using TVDb Movie ID: {tvdb_url[len(urls['movie_id']):]}"
        elif tvdb_url.startswith(urls["series_id"]):
            err_text = f"using TVDb Series ID: {tvdb_url[len(urls['series_id']):]}"
        else:
            err_text = f"ID at the URL {tvdb_url}"
        raise Failed(f"TVDb Error: Could not find a TVDb {media_type} {err_text}")

    def get_list_description(self, tvdb_url):
        response = self.requests.get_html(tvdb_url, language=self.language)
        description = response.xpath("//div[@class='block']/div[not(@style='display:none')]/p/text()")
        description = description[0] if len(description) > 0 and len(description[0]) > 0 else None
        poster = response.xpath("//div[@id='artwork']/div/div/a/@href")
        poster = poster[0] if len(poster) > 0 and len(poster[0]) > 0 else None
        return description, poster

    def _ids_from_url(self, tvdb_url):
        ids = []
        tvdb_url = tvdb_url.strip()
        logger.trace(f"URL: {tvdb_url}")
        if tvdb_url.startswith((urls["list"], urls["alt_list"])):
            try:
                response = self.requests.get_html(tvdb_url, language=self.language)
                items = response.xpath("//div[@id='general']//div/div/h3/a")
                for item in items:
                    title = item.xpath("text()")[0]
                    item_url = item.xpath("@href")[0]
                    if item_url.startswith("/series/"):
                        try:
                            tvdb_id, _, _ = self.get_id_from_url(f"{base_url}{item_url}")
                            if tvdb_id:
                                ids.append((tvdb_id, "tvdb"))
                        except Failed as e:
                            logger.error(f"{e} for series {title}")
                    elif item_url.startswith("/movies/"):
                        try:
                            _, tmdb_id, imdb_id = self.get_id_from_url(f"{base_url}{item_url}", is_movie=True)
                            if tmdb_id:
                                ids.append((tmdb_id, "tmdb"))
                            elif imdb_id:
                                ids.append((imdb_id, "imdb"))
                        except Failed as e:
                            logger.error(f"{e} for movie {title}")
                    else:
                        logger.error(f"TVDb Error: Skipping Movie: {title}")
                    time.sleep(2)
                if len(ids) > 0:
                    return ids
                raise Failed(f"TVDb Error: No TVDb IDs found at {tvdb_url}")
            except MissingSchema:
                logger.stacktrace()
                raise Failed(f"TVDb Error: URL Lookup Failed for {tvdb_url}")
        else:
            raise Failed(f"TVDb Error: {tvdb_url} must begin with {urls['list']}")

    def get_tvdb_ids(self, method, data):
        if method == "tvdb_show":
            logger.info(f"Processing TVDb Show: {data}")
            ids = []
            try:
                tvdb_id, _, _ = self.get_id_from_url(data)
                if tvdb_id:
                    ids.append((tvdb_id, "tvdb"))
            except Failed as e:
                logger.error(e)
            return ids
        elif method == "tvdb_movie":
            logger.info(f"Processing TVDb Movie: {data}")
            ids = []
            try:
                _, tmdb_id, imdb_id = self.get_id_from_url(data)
                if tmdb_id:
                    ids.append((tmdb_id, "tmdb"))
                elif imdb_id:
                    ids.append((imdb_id, "imdb"))
            except Failed as e:
                logger.error(e)
            return ids
        elif method == "tvdb_list":
            logger.info(f"Processing TVDb List: {data}")
            return self._ids_from_url(data)
        else:
            raise Failed(f"TVDb Error: Method {method} not supported")

    def item_filter(self, item, filter_attr, modifier, filter_final, filter_data):
        if filter_attr == "tvdb_title":
            if util.is_string_filter([item.title], modifier, filter_data):
                return False
        elif filter_attr == "tvdb_status":
            if util.is_string_filter([item.status], modifier, filter_data):
                return False
        elif filter_attr == "tvdb_genre":
            attrs = item.genres
            if modifier == ".regex":
                has_match = False
                for reg in filter_data:
                    for name in attrs:
                        if re.compile(reg).search(name):
                            has_match = True
                if has_match is False:
                    return False
            elif modifier in [".count_gt", ".count_gte", ".count_lt", ".count_lte"]:
                test_number = len(attrs) if attrs else 0
                modifier = f".{modifier[7:]}"
                if test_number is None or util.is_number_filter(test_number, modifier, filter_data):
                    return False
            elif (not list(set(filter_data) & set(attrs)) and modifier == "") or (list(set(filter_data) & set(attrs)) and modifier == ".not"):
                return False
        return True
