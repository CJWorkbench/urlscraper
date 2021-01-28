from urlscraper import migrate_params


def test_v1():
    assert migrate_params(
        {"urlsource": 0, "urlcol": "A", "urllist": "http://example.org\n"}
    ) == {
        "urlsource": "list",
        "urlcol": "A",
        "urllist": "http://example.org\n",
        "pagedurl": "",
        "addpagenumbers": False,
        "startpage": 0,
        "endpage": 9,
    }


def test_v2():
    assert migrate_params(
        {"urlsource": "list", "urlcol": "A", "urllist": "http://example.org\n"}
    ) == {
        "urlsource": "list",
        "urlcol": "A",
        "urllist": "http://example.org\n",
        "pagedurl": "",
        "addpagenumbers": False,
        "startpage": 0,
        "endpage": 9,
    }


def test_v3():
    # test that moving form v2 to v3 sets addpagenumbers to True, as that was what v2 did
    assert migrate_params(
        {
            "urlsource": "paged",
            "urlcol": "A",
            "urllist": "",
            "pagedurl": "http://example.org/foo?page=",
            "startpage": 1,
            "endpage": 4,
        }
    ) == {
        "urlsource": "paged",
        "urlcol": "A",
        "urllist": "",
        "pagedurl": "http://example.org/foo?page=",
        "addpagenumbers": True,
        "startpage": 1,
        "endpage": 4,
    }
