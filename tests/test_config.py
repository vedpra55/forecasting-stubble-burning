from stubblecast import config


def test_splits_are_disjoint_and_ordered():
    s = config.load("seasons")["splits"]
    train, val, test = set(s["train"]), set(s["validate"]), set(s["test"])
    assert not (train & val or train & test or val & test)
    assert max(train) < min(val) <= max(val) < min(test)


def test_eda_seasons_exclude_test_seasons():
    cfg = config.load("seasons")
    assert not set(cfg["eda_seasons"]) & set(cfg["splits"]["test"])


def test_dataset_ids_present():
    gee = config.load("sources")["gee"]
    for k in ("s2", "cloud_score_plus", "s1", "worldcover", "era5_land_daily"):
        assert gee[k]
