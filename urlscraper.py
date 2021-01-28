import asyncio
import datetime
import io
import re
from typing import List, Protocol, Tuple

import pandas as pd
import rfc3987
from cjwmodule.http import HttpError
from cjwmodule.http.client import download
from cjwmodule.http.httpfile import extract_first_header
from cjwmodule.i18n import trans

MaxNUrls = 10


class Settings(Protocol):
    SCRAPER_NUM_CONNECTIONS: int
    """Maximum number of concurrent fetches."""

    SCRAPER_TIMEOUT: float
    """Maximum number of seconds before abandoning HTTP request."""


def utcnow():
    """
    Return datetime.datetime.utcnow().

    It's a separate function so we can mock it in unit tests.
    """
    return datetime.datetime.utcnow()


def _as_text(buf: bytes, headers: List[Tuple[str, str]]) -> str:
    """Guess encoding and return buf as text.

    Never raise.
    """
    if isinstance(headers, list):
        content_type = extract_first_header(headers, "Content-Type")
    else:
        # httpx Response headers
        content_type = headers["Content-Type"]
    if content_type and "charset=" in content_type:
        charset = content_type.split("charset=")[1]
    else:
        charset = "utf-8"  # guessing
    try:
        return buf.decode(encoding=charset, errors="replace")
    except LookupError:  # invalid encoding
        return buf.decode("latin1")  # never fails


async def async_get_url(row, url, *, settings: Settings):
    """Return a Future (row, status, text).

    The Future will resolve within settings.SCRAPER_TIMEOUT seconds. `status`
    may be one of '200 OK', '404 Not Found', 'Timed out', 'Invalid URL',
    "Can't connect: [err]", 'Unknown error: [err]'.
    """
    buf = io.BytesIO()

    def ret(status_text: str, headers: List[Tuple[str, str]] = []):
        return row, status_text, _as_text(buf.getvalue(), headers)

    try:
        parts = rfc3987.parse(url, "absolute_URI")  # raise ValueError
        if parts["scheme"] not in {"http", "https"}:
            raise ValueError("Unsupported scheme")
        if not parts["authority"]:
            raise ValueError(
                "No authority, probably because we prepended 'http:' to any old string"
            )
    except ValueError:
        return ret("Invalid URL")

    try:
        downloaded = await download(url, buf, total_timeout=settings.SCRAPER_TIMEOUT)
        return ret(
            "%d %s" % (downloaded.status_code, downloaded.reason_phrase),
            downloaded.headers,
        )
    except HttpError.InvalidUrl:
        return ret("Invalid URL")
    except HttpError.Timeout:
        return ret("Timed out")
    except HttpError.TooManyRedirects:
        return ret("Too many redirects")
    except HttpError.NotSuccess as err:
        return ret(
            "%d %s" % (err.response.status_code, err.response.reason_phrase),
            err.response.headers,
        )
    except HttpError.Generic as err:
        return ret(str(err))


# Asynchronously scrape many urls, and store the results in the table
async def scrape_urls(urls, result_table, settings):
    next_queued_row = 0  # index into urls
    fetching = set()  # {Future<response>}

    max_fetchers = settings.SCRAPER_NUM_CONNECTIONS

    while next_queued_row < len(urls) or fetching:
        # start tasks until we max out connections, or run out of urls
        while next_queued_row < len(urls) and len(fetching) < max_fetchers:
            row = next_queued_row
            url = urls[row].strip()
            fetching.add(async_get_url(row, url, settings=settings))

            next_queued_row += 1

        assert fetching

        # finish one or more tasks, then loop
        done, pending = await asyncio.wait(
            fetching, return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            row, status, text = await task
            result_table.loc[row, "status"] = status
            result_table.loc[row, "html"] = text

        fetching = pending  # delete done tasks


def render(table, params, *, fetch_result):
    if fetch_result is None:
        return table

    else:
        return fetch_result


def _truncate_error():
    return trans(
        "params.limitedNUrls",
        "We limited your scrape to {nUrls} URLs",
        {"nUrls": MaxNUrls},
    )


def fetch(params, *, get_input_dataframe, settings):
    urls = []
    urlsource = params["urlsource"]
    errors = []

    if urlsource == "list":
        urllist_text: str = params["urllist"]
        urllist_raw = urllist_text.split("\n")
        for url in urllist_raw:
            s_url = url.strip()
            if len(s_url) == 0:
                continue
            # Fix in case user adds an URL without http(s) prefix
            if not re.match("^https?://.*", s_url):
                urls.append("http://{}".format(s_url))
            else:
                urls.append(s_url)
        if not urls:
            return None
        if len(urls) > MaxNUrls:
            urls = urls[:MaxNUrls]
            errors.append(_truncate_error())
    elif urlsource == "column":
        # We won't execute here -- there's no need: the user clicked a
        # button so should be pretty clear on what the input is.
        prev_table = asyncio.run(get_input_dataframe())

        if prev_table is None or params["urlcol"] not in prev_table.columns:
            return None

        # get our list of URLs from a column in the input table
        urlcol: str = params["urlcol"]
        urls = prev_table[urlcol].tolist()
        if len(urls) > MaxNUrls:
            urls = urls[:MaxNUrls]
            errors.append(_truncate_error())
    elif urlsource == "paged":
        # Count through a list of page numbers, appending each to the URL
        pagedurl: str = params["pagedurl"]
        if not pagedurl:
            return None

        # Fix in case user adds an URL without http(s) prefix
        if not re.match("^https?://.*", pagedurl):
            pagedurl = "http://" + pagedurl

        begin = params["startpage"]
        end = params["endpage"] + 1
        if end - begin > MaxNUrls:
            end = begin + MaxNUrls
            errors.append(_truncate_error())

        # Generate multiple urls by adding page numbers, if user says so
        if params["addpagenumbers"]:
            # limit the number of pages we can scrape with this method
            urls = [pagedurl + str(num) for num in range(begin, end)]
        else:
            urls = [pagedurl]
    else:
        raise RuntimeError("Invalid urlsource")

    table = pd.DataFrame(
        {
            "url": urls,
            # TODO use response date, not current date
            # TODO migrate to use timestamp type, not text (will affect
            # existing users)
            "date": utcnow().isoformat(timespec="seconds") + "Z",
            "status": "",
            "html": "",
        }
    )

    asyncio.run(scrape_urls(urls, table, settings=settings))
    return table, errors


def _migrate_params_v0_to_v1(params):
    """
    v0: urlsource was 0 ("List") or 1 ("Input column")

    v1: urlsource is "list" or "column".
    """
    return {**params, "urlsource": ["list", "column"][params["urlsource"]]}


def _migrate_params_v1_to_v2(params):
    """
    v2 adds "paged" option to urlsource menu and related parameters
    """
    return {
        **params,
        "pagedurl": "",
        "addpagenumbers": False,  # defaults, from json file
        "startpage": 0,
        "endpage": 9,
    }


def _migrate_params_v2_to_v3(params):
    """
    v3 adds "addpagenumbers" checkbox
    """
    return {**params, "addpagenumbers": True}  # match v2 behavior


def migrate_params(params):
    if isinstance(params["urlsource"], int):
        params = _migrate_params_v0_to_v1(params)
    if "pagedurl" not in params:
        params = _migrate_params_v1_to_v2(params)
    if "addpagenumbers" not in params:
        params = _migrate_params_v2_to_v3(params)
    return params
