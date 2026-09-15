"""本地曲库检索自检。取代 Cyanite 之后，这是唯一的召回来源，契约必须钉死。"""
import catalog
import config


def test_selfcheck_passes():
    catalog._selfcheck()


def test_ids_are_jamendo_ids():
    """Cyanite 下线后 cyanite_id 就是 track_id——前端按 track_id 拼音频 URL，错了就不出声。"""
    row = catalog.search_by_prompt("piano", limit=1)[0]

    assert row["cyanite_id"] == row["track_id"]
    assert row["track_id"].isdigit()


def test_different_prompts_give_different_results():
    calm = [r["cyanite_id"] for r in catalog.search_by_prompt("peaceful calm piano", limit=5)]
    loud = [r["cyanite_id"] for r in catalog.search_by_prompt("aggressive fast rock", limit=5)]

    assert calm != loud


def test_same_prompt_is_deterministic():
    a = catalog.search_by_prompt("melancholic rainy night", limit=5)
    b = catalog.search_by_prompt("melancholic rainy night", limit=5)

    assert a == b


def test_unmatchable_prompt_still_fills_the_page():
    """一个英文标签都碰不到（如中文 prompt）也不能给空页面——那就是死胡同。"""
    rows = catalog.search_by_prompt("夜晚的孤独列车", limit=config.VISIBLE_N)

    assert len(rows) == config.VISIBLE_N
    # 仍然按 query 分流，不是所有 prompt 都返回同一批
    other = catalog.search_by_prompt("完全不同的中文提示", limit=config.VISIBLE_N)
    assert [r["cyanite_id"] for r in rows] != [r["cyanite_id"] for r in other]


def test_similar_excludes_its_own_seed():
    seed = catalog.search_by_prompt("jazz saxophone", limit=1)[0]["cyanite_id"]
    rows = catalog.find_similar(seed, limit=10)

    assert rows
    assert seed not in {r["cyanite_id"] for r in rows}


def test_similar_multi_excludes_all_seeds():
    seeds = [r["cyanite_id"] for r in catalog.search_by_prompt("ambient strings", limit=3)]
    rows = catalog.find_similar_multi(seeds, limit=10)

    assert rows
    assert not set(seeds) & {r["cyanite_id"] for r in rows}


def test_unknown_id_degrades_quietly():
    """曲库里没有的 id 不能抛——编排层会拿着任意 id 来问。"""
    assert catalog.find_similar("not-a-track") == []
    assert catalog.find_similar_multi(["not-a-track"]) == []
    assert catalog.model_tags("not-a-track", config.EXPLAIN_TAG_MODELS) == {"items": []}
    assert catalog.display("not-a-track", "42")["track_id"] == "42"


def test_model_tags_keep_cyanite_shape():
    """explanation_builder 按 {"items":[{"version","tags"}]} 取用，形状不能变。"""
    cid = catalog.search_by_prompt("piano", limit=1)[0]["cyanite_id"]
    out = catalog.model_tags(cid, config.EXPLAIN_TAG_MODELS)

    assert out["items"]
    for item in out["items"]:
        assert item["version"] in config.EXPLAIN_TAG_MODELS
        assert item["tags"] and all(isinstance(t, str) for t in item["tags"])


def test_enrich_meta_drops_nameless_cards():
    """拿不到真实曲名的卡不渲染——空白卡片比少一张卡更糟。"""
    kept = {"cyanite_id": catalog._TRACKS[0]["id"], "track_id": catalog._TRACKS[0]["id"]}

    assert catalog.enrich_meta([kept])[0]["title"]
    assert catalog.enrich_meta([{"cyanite_id": "ghost", "track_id": "ghost"}]) == []


def test_results_do_not_pile_up_on_one_artist():
    """标签检索会把同一张专辑整批顶上来；5 张卡里 3 张同一人，演示看着像坏了。"""
    rows = catalog.search_by_prompt("dark ambient sad", limit=config.VISIBLE_N)
    artists = [catalog.display(r["cyanite_id"])["artist"] for r in rows]

    assert max(artists.count(a) for a in artists) <= 2, artists
