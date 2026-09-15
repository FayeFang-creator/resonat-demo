import user_profiles


def test_liked_ids_returns_empty_for_unknown_user():
    assert user_profiles.liked_cyanite_ids("__missing__") == []


def test_liked_ids_survives_missing_profile_file(monkeypatch):
    """公开演示版没有主办方 users.csv：缺档案必须安静退化，不能炸。"""
    monkeypatch.setattr(user_profiles, "_USER_LIKES", {})

    assert user_profiles.liked_cyanite_ids("545127") == []


def test_liked_ids_maps_known_user_to_catalog_tracks(monkeypatch):
    import catalog

    known = next(iter(catalog._BY_ID))
    monkeypatch.setattr(user_profiles, "_USER_LIKES", {"u1": [known, "not-a-real-track"]})

    # 曲库里没有的 id 被跳过，不会带着空卡片往下走
    assert user_profiles.liked_cyanite_ids("u1") == [known]
