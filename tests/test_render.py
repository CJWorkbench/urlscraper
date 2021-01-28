import pandas as pd
from pandas.testing import assert_frame_equal

from urlscraper import render


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


def test_module_initial_nop():
    table = pd.DataFrame({"A": [1]})
    result = render(table.copy(), P(urlsource="list", urllist=""), fetch_result=None)
    assert_frame_equal(result, table)


def test_module_nop_with_initial_col_selection():
    table = pd.DataFrame({"A": [1]})
    result = render(table.copy(), P(urlsource="column", urlcol=""), fetch_result=None)
    assert_frame_equal(result, table)


def test_module_nop_with_missing_col_selection():
    table = pd.DataFrame({"A": [1]})
    result = render(table.copy(), P(urlsource="column", urlcol="B"), fetch_result=None)
    assert_frame_equal(result, table)
