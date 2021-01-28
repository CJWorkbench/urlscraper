from typing import NamedTuple

import pandas as pd
from cjwmodule.testing.i18n import i18n_message
from freezegun import freeze_time
from pandas.testing import assert_frame_equal
from pytest_httpx import HTTPXMock

from urlscraper import fetch


def P(
    urlsource="list",
    urllist="",
    urlcol="",
    pagedurl="",
    addpagenumbers=False,
    startpage=0,
    endpage=9,
):
    return dict(
        urlsource=urlsource,
        urllist=urllist,
        urlcol=urlcol,
        pagedurl=pagedurl,
        addpagenumbers=addpagenumbers,
        startpage=startpage,
        endpage=endpage,
    )


class Settings(NamedTuple):
    SCRAPER_NUM_CONNECTIONS: int = 3
    SCRAPER_TIMEOUT: float = 1


async def _no_input_dataframe():
    return None


MOCK_DATETIME_S = "2021-01-28T18:56:12Z"


@freeze_time(MOCK_DATETIME_S)
def test_simple_urls(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://a.com/file", data=b"<div>all good</div>")
    httpx_mock.add_response(
        url="https://b.com/file2", status_code=404, data=b"not found"
    )
    httpx_mock.add_response(url="http://c.com/file/dir", data=b"<h1>What a page!</h1>")
    table, errors = fetch(
        P(urllist="http://a.com/file\nhttps://b.com/file2\nhttp://c.com/file/dir"),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert errors == []
    assert_frame_equal(
        table,
        pd.DataFrame(
            {
                "url": [
                    "http://a.com/file",
                    "https://b.com/file2",
                    "http://c.com/file/dir",
                ],
                "date": [MOCK_DATETIME_S] * 3,
                "status": ["200 OK", "404 Not Found", "200 OK"],
                "html": ["<div>all good</div>", "not found", "<h1>What a page!</h1>"],
            }
        ),
    )


@freeze_time(MOCK_DATETIME_S)
def test_invalid_url():
    table, errors = fetch(
        P(urllist="just not a url\n/relative/url"),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert errors == []
    assert_frame_equal(
        table,
        pd.DataFrame(
            {
                "url": ["http://just not a url", "http:///relative/url"],
                "date": [MOCK_DATETIME_S, MOCK_DATETIME_S],
                "status": ["Invalid URL", "Invalid URL"],
                "html": ["", ""],
            }
        ),
    )


def test_content_type_charset(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        data=b"caf\xe9", headers={"Content-Type": "text/html; charset=latin1"}
    )
    table, errors = fetch(
        P(urllist="http://hi"),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert errors == []
    assert list(table["html"]) == ["café"]


def test_content_type_charset_invalid(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        data=b"caf\xe9", headers={"Content-Type": "text/html; charset=moo"}
    )
    table, errors = fetch(
        P(urllist="http://hi"),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert errors == []
    assert list(table["html"]) == ["café"]  # fallback to latin1 because it won't fail


@freeze_time(MOCK_DATETIME_S)
def test_timeout_url(httpx_mock: HTTPXMock):
    # httpx_mock default is httpx.TimeoutException
    table, errors = fetch(
        P(urllist="https://example.org"),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert errors == []
    assert_frame_equal(
        table,
        pd.DataFrame(
            {
                "url": ["https://example.org"],
                "date": [MOCK_DATETIME_S],
                "status": ["Timed out"],
                "html": [""],
            }
        ),
    )


# @freeze_time(MOCK_DATETIME_S)
# def test_no_connection_url(httpx_mock: HTTPXMock):
#     def raise_failure(request, ext):
#         raise httpx.ReadTimeout("failure", request=request)
#
#     httpx_mock.add_response(raise_failure, url="https://example.org")
#     table, errors = fetch(
#         P(urllist="https://example.org"),
#         get_input_dataframe=_no_input_dataframe,
#         settings=Settings(),
#     )
#     assert errors == []
#     assert_frame_equal(
#         table,
#         pd.DataFrame(
#             {
#                 "url": ["https://example.org"],
#                 "date": [MOCK_DATETIME_S],
#                 "status": ["failure"],
#                 "html": [""],
#             }
#         ),
#     )


def test_http_not_success(httpx_mock: HTTPXMock):
    httpx_mock.add_response(data=b"hi", status_code=429)
    table, errors = fetch(
        P(urllist="https://example.org"),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert errors == []
    assert list(table["status"]) == ["429 Too Many Requests"]
    assert list(table["html"]) == ["hi"]


@freeze_time(MOCK_DATETIME_S)
def test_many_urls(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="http://1.com", data=b"1")
    httpx_mock.add_response(url="http://2.com", data=b"2")
    httpx_mock.add_response(url="http://3.com", data=b"3")
    httpx_mock.add_response(url="http://4.com", data=b"4")
    httpx_mock.add_response(url="http://5.com", data=b"5")
    url_list = ["http://%d.com" % i for i in range(1, 6)]
    table, errors = fetch(
        P(urllist="\n".join(url_list)),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(SCRAPER_NUM_CONNECTIONS=2),
    )
    assert errors == []
    assert_frame_equal(
        table,
        pd.DataFrame(
            {
                "url": url_list,
                "date": [MOCK_DATETIME_S] * 5,
                "status": ["200 OK"] * 5,
                "html": list("12345"),
            }
        ),
    )


def test_module_initial_nop():
    result = fetch(
        P(urlsource="list", urllist=""),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert result is None


def test_module_nop_with_initial_col_selection():
    async def get_input_dataframe():
        return pd.DataFrame({"A": [1]})

    result = fetch(
        P(urlsource="column", urlcol=""),
        get_input_dataframe=get_input_dataframe,
        settings=Settings(),
    )
    assert result is None


def test_urlcol(httpx_mock: HTTPXMock):
    async def get_input_dataframe():
        return pd.DataFrame({"A": ["http://a", "http://b"]})

    table, errors = fetch(
        P(urlsource="column", urlcol="A"),
        get_input_dataframe=get_input_dataframe,
        settings=Settings(),
    )
    assert errors == []
    assert list(table["url"]) == ["http://a", "http://b"]


def test_urlcol_truncate(httpx_mock: HTTPXMock):
    async def get_input_dataframe():
        return pd.DataFrame({"A": ["http://%i" % i for i in range(1, 12)]})

    table, errors = fetch(
        P(urlsource="column", urlcol="A"),
        get_input_dataframe=get_input_dataframe,
        settings=Settings(),
    )
    assert errors == [i18n_message("params.limitedNUrls", {"nUrls": 10})]
    assert list(table["url"]) == ["http://%i" % i for i in range(1, 11)]


def test_urlcol_missing_input_table(httpx_mock: HTTPXMock):
    result = fetch(
        P(urlsource="column", urlcol="A"),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert result is None


def test_scrape_list_truncate(httpx_mock: HTTPXMock):
    url_list = ["http://%d.com" % i for i in range(1, 12)]

    for url in url_list[:10]:
        httpx_mock.add_response(url=url, data=b"hi")

    table, errors = fetch(
        P(urllist="\n".join(url_list)),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )
    assert errors == [i18n_message("params.limitedNUrls", {"nUrls": 10})]
    assert_frame_equal(table[["url"]], pd.DataFrame({"url": url_list[:10]}))


def test_scrape_paged(httpx_mock: HTTPXMock):
    for i in range(1, 4):
        httpx_mock.add_response(url="http://foo?p=%d" % i, data=b"hi")

    table, errors = fetch(
        P(
            urlsource="paged",
            pagedurl="http://foo?p=",
            startpage=1,
            endpage=3,
            addpagenumbers=True,
        ),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )

    assert errors == []
    assert_frame_equal(
        table[["url"]],
        pd.DataFrame({"url": ["http://foo?p=1", "http://foo?p=2", "http://foo?p=3"]}),
    )


def test_scrape_paged_truncate(httpx_mock: HTTPXMock):
    for i in range(1, 11):
        httpx_mock.add_response(url="http://foo?p=%d" % i, data=b"hi")

    table, errors = fetch(
        P(
            urlsource="paged",
            pagedurl="http://foo?p=",
            startpage=1,
            endpage=23,
            addpagenumbers=True,
        ),
        get_input_dataframe=_no_input_dataframe,
        settings=Settings(),
    )

    assert errors == [i18n_message("params.limitedNUrls", {"nUrls": 10})]
    assert_frame_equal(
        table[["url"]],
        pd.DataFrame({"url": ["http://foo?p=%d" % i for i in range(1, 11)]}),
    )
