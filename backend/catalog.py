"""基础设施 · 本地曲库检索。取代已下线的 Cyanite（赛后赞助商 API 关停）。

对外接口与原 cyanite.py 逐一对应、签名不变，所以编排层只需改个名字；测试仍靠
monkeypatch 本模块离线跑。

数据源 data/demo_catalog.json 由 build_catalog.py 从公开 Jamendo API 抓取一次
（CC BY-SA 3.0），**运行时零网络、零 API key**。音频仍由 Jamendo 公开 CDN 直供，
前端按 track_id 拼 URL，不经过本模块。

与 Cyanite 时代的关键简化：**cyanite_id 就是 Jamendo track_id**，双 id 体系消失。
字段名保留 `cyanite_id` 是为了不动前端契约和编排层的几十处引用。

检索是「IDF 加权的标签/词面匹配」，不是音频语义检索——这是公开数据能做到的诚实上限。
# ponytail: 词面匹配封顶。要真语义检索得上 JamendoMaxCaps caption 向量索引（见 README「Stage 2」）。
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re

import config

_CATALOG = pathlib.Path(__file__).resolve().parent / "data" / "demo_catalog.json"

# 检索口径：情绪/风格/乐器标签是主信号，曲名作者只作弱信号。
_W_TAG = 3.0
_W_TEXT = 1.0
_W_SPEED = 1.5

_STOP = {
    "the", "and", "for", "with", "that", "this", "some", "like", "into", "from",
    "you", "your", "want", "need", "song", "songs", "music", "track", "tracks",
    "something", "sounds", "sound", "feel", "feels", "feeling", "give", "make",
    "listener", "listen", "listening", "please", "about", "when", "while",
}

# prompt 用词 -> Jamendo 标签词表。只收录高频且确实对不上的，不做同义词大全。
_SYNONYMS = {
    "lonely": ["melancholic", "sad", "solitude"], "loneliness": ["melancholic", "sad"],
    "midnight": ["night", "dark"], "night": ["night", "dark"],
    "sleepy": ["relaxing", "soft"], "sleep": ["relaxing", "soft"],
    "study": ["relaxing", "ambient"], "focus": ["ambient", "minimal"],
    "workout": ["energetic", "sport"], "gym": ["energetic", "sport"],
    "running": ["energetic", "sport"], "party": ["energetic", "groovy"],
    "rain": ["melancholic", "soft"], "rainy": ["melancholic", "soft"],
    "morning": ["fresh", "positive"], "sunny": ["happy", "summer"],
    "happy": ["happy", "positive"], "sad": ["sad", "melancholic"],
    "calm": ["peaceful", "relaxing"], "chill": ["relaxing", "lounge"],
    "angry": ["aggressive", "dark"], "nostalgic": ["nostalgic", "retro"],
    "driving": ["energetic", "road"], "drive": ["energetic", "road"],
    "cinematic": ["cinematic", "film"], "movie": ["cinematic", "film"],
    "train": ["travel", "road"], "travel": ["travel", "road"],
    "slow": ["slow", "soft"], "fast": ["energetic", "fast"],
    "warm": ["warm", "romantic"], "cold": ["cold", "dark"],
    "hopeful": ["hopeful", "positive"], "epic": ["epic", "powerful"],
}

# 速度词 -> Jamendo musicinfo.speed 档位
_SPEED_WORDS = {
    "slow": "low", "slowly": "low", "calm": "low", "sleepy": "verylow",
    "relaxed": "low", "gentle": "low", "fast": "high", "energetic": "high",
    "upbeat": "high", "driving": "high", "intense": "veryhigh", "frantic": "veryhigh",
}


def _load() -> list[dict]:
    """曲库缺失也不能让服务起不来——返回空库，检索退化为空结果。"""
    try:
        return json.loads(_CATALOG.read_text())["tracks"]
    except (OSError, ValueError, KeyError) as e:
        print(f"[warn] demo catalog unavailable ({e}); search will return nothing")
        return []


_TRACKS: list[dict] = _load()
_BY_ID: dict[str, dict] = {t["id"]: t for t in _TRACKS}


def _all_tags(t: dict) -> list[str]:
    tags = t.get("tags") or {}
    return [*tags.get("genres", []), *tags.get("instruments", []), *tags.get("vartags", [])]


# IDF：'acoustic'/'voice' 这类标签在库里占一半以上，不做逆频率加权就会淹没真正的区分信号。
_DF: dict[str, int] = {}
for _t in _TRACKS:
    for _tag in set(_all_tags(_t)):
        _DF[_tag] = _DF.get(_tag, 0) + 1
_N = max(len(_TRACKS), 1)
_IDF: dict[str, float] = {tag: math.log(_N / (1 + df)) + 1.0 for tag, df in _DF.items()}

# 词面检索用的文本 blob（曲名 + 作者），标签单独走精确匹配。
_BLOB: dict[str, str] = {
    t["id"]: f"{t.get('title', '')} {t.get('artist', '')}".lower() for t in _TRACKS
}
_TAGSET: dict[str, set[str]] = {t["id"]: set(_all_tags(t)) for t in _TRACKS}


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z]+", (text or "").lower())
    return [w for w in words if len(w) >= 3 and w not in _STOP]


def _expand(tokens: list[str]) -> set[str]:
    out = set(tokens)
    for w in tokens:
        out.update(_SYNONYMS.get(w, ()))
    return out


def _wanted_speed(tokens: list[str]) -> str:
    for w in tokens:
        if w in _SPEED_WORDS:
            return _SPEED_WORDS[w]
    return ""


def _stable_jitter(query: str, track_id: str) -> float:
    """确定性伪随机 0..1：同 query 永远同结果，不同 query 给不同排序。
    用于全都零分时兜底，保证「任何 prompt 都有 5 张卡」而不是空页面。"""
    h = hashlib.sha1(f"{query}|{track_id}".encode()).digest()
    return int.from_bytes(h[:4], "big") / 0xFFFFFFFF


def _row(track_id: str, score: float) -> dict:
    return {"cyanite_id": track_id, "score": round(float(score), 4), "track_id": track_id}


def _diversify(ranked: list[tuple[float, str]], limit: int, per_artist: int = 2) -> list[tuple[float, str]]:
    """同一艺术家最多留 per_artist 首。

    标签检索会把同一张专辑整批顶上来（同作者 = 同标签），5 张卡里 3 张同一人，
    演示看着像坏了。先按配额取，不够再用剩下的补满。
    """
    kept, spill, used = [], [], {}
    for item in ranked:
        artist = (_BY_ID.get(item[1], {}).get("artist") or "").lower()
        if used.get(artist, 0) < per_artist:
            used[artist] = used.get(artist, 0) + 1
            kept.append(item)
            if len(kept) == limit:
                return kept
        else:
            spill.append(item)
    return kept + spill[:limit - len(kept)]


# --- id / 展示 ---
def to_cyanite(track_id: str) -> str:
    tid = str(track_id)
    if tid not in _BY_ID:           # 调用方 (user_profiles) 按 KeyError 判存在性
        raise KeyError(tid)
    return tid


def to_jamendo(cyanite_id: str) -> str:
    return str(cyanite_id)


def display(cyanite_id: str, track_id: str = "") -> dict:
    t = _BY_ID.get(str(cyanite_id))
    if not t:
        return {"track_id": track_id or str(cyanite_id), "cyanite_id": cyanite_id,
                "title": "", "artist": ""}
    return {"track_id": t["id"], "cyanite_id": t["id"],
            "title": t.get("title", ""), "artist": t.get("artist", "")}


def normalize(resp: dict) -> list[dict]:
    """保留原签名：把 {items:[{track,score}]} 压平。本地检索已直出该结构，
    仅在有人复用旧响应格式时用到。"""
    out = []
    for it in resp.get("items", []):
        track = it.get("track", it)
        tid = str(track.get("id") or "")
        out.append({"cyanite_id": tid, "score": it.get("score"), "track_id": tid})
    return out


def enrich_meta(cards: list[dict]) -> list[dict]:
    """补 title/artist，补不上的丢弃（拿不到真实曲名就不渲染）。
    曲库自带元数据，无需再打 Jamendo API。"""
    out = []
    for c in cards:
        if not c.get("title"):
            d = display(c.get("cyanite_id", ""), c.get("track_id", ""))
            c = {**c, "title": d["title"], "artist": d["artist"],
                 "track_id": c.get("track_id") or d["track_id"]}
        if c.get("title"):
            out.append(c)
    return out


# --- 检索 ---
def search_by_prompt(query: str, limit: int = config.SEARCH_LIMIT,
                     metadata_filter: dict | None = None) -> list[dict]:
    """自然语言 -> 候选曲。IDF 加权标签匹配 + 曲名词面匹配 + 速度档位。

    metadata_filter 是 Cyanite 时代的 MongoDB 风格硬过滤，本地库无对应字段体系；
    # ponytail: 直接忽略。无 OPENAI_API_KEY 时 intent_agent 恒返回 None，演示路径根本不产生它。
    """
    if not _TRACKS:
        return []
    tokens = _tokens(query)
    wanted = _expand(tokens)
    speed = _wanted_speed(tokens)

    scored = []
    for t in _TRACKS:
        tid = t["id"]
        hit = wanted & _TAGSET[tid]
        score = _W_TAG * sum(_IDF.get(tag, 1.0) for tag in hit)
        blob = _BLOB[tid]
        score += _W_TEXT * sum(1 for w in tokens if w in blob)
        if speed and t.get("speed") == speed:
            score += _W_SPEED
        scored.append((score, tid))

    top = max((s for s, _ in scored), default=0.0)
    if top <= 0:
        # 一个标签都没匹配上（例如全中文 prompt）：给确定性伪随机排序，页面不能是空的
        ranked = sorted(scored, key=lambda p: _stable_jitter(query, p[1]), reverse=True)
        return [_row(tid, 0.0) for _, tid in _diversify(ranked, limit)]

    # 归一化到 0..1，并用 jitter 打散同分（否则同分曲永远按库内顺序出现）
    ranked = sorted([p for p in scored if p[0] > 0],
                    key=lambda p: (p[0], _stable_jitter(query, p[1])), reverse=True)
    return [_row(tid, s / top) for s, tid in _diversify(ranked, limit)]


def _similar_to_tagset(seed_tags: set[str], exclude: set[str], limit: int) -> list[dict]:
    """IDF 加权的标签重叠度，归一化成 0..1 的相似分。"""
    if not seed_tags or not _TRACKS:
        return []
    seed_norm = math.sqrt(sum(_IDF.get(tag, 1.0) ** 2 for tag in seed_tags)) or 1.0
    scored = []
    for t in _TRACKS:
        tid = t["id"]
        if tid in exclude:
            continue
        shared = seed_tags & _TAGSET[tid]
        if not shared:
            continue
        other_norm = math.sqrt(sum(_IDF.get(tag, 1.0) ** 2 for tag in _TAGSET[tid])) or 1.0
        overlap = sum(_IDF.get(tag, 1.0) ** 2 for tag in shared)
        scored.append((overlap / (seed_norm * other_norm), tid))
    scored.sort(reverse=True)
    return [_row(tid, s) for s, tid in _diversify(scored, limit)]


def find_similar(cyanite_id: str, limit: int = config.SIMILAR_LIMIT) -> list[dict]:
    """单种子相似：拿种子自身标签做 IDF 加权近邻。"""
    seed = _BY_ID.get(str(cyanite_id))
    if not seed:
        return []
    return _similar_to_tagset(set(_all_tags(seed)), {str(cyanite_id)}, limit)


def find_similar_multi(cyanite_ids: list[str], limit: int = config.SIMILAR_LIMIT) -> list[dict]:
    """多种子相似（≤10）：标签并集求公共声音区。"""
    seeds = [_BY_ID[str(c)] for c in cyanite_ids[:10] if str(c) in _BY_ID]
    if not seeds:
        return []
    union: set[str] = set()
    for s in seeds:
        union.update(_all_tags(s))
    return _similar_to_tagset(union, {str(c) for c in cyanite_ids}, limit)


# --- 标签（给 "Why this track?" 供证据）---
# Jamendo musicinfo -> 原 Cyanite 模型名，保持 explanation_builder 的取用方式不变。
_SPEED_BPM = {"verylow": "very slow", "low": "slow", "medium": "medium",
              "high": "fast", "veryhigh": "very fast"}


def model_tags(cyanite_id: str, models: list[str]) -> dict:
    """返回 Cyanite 形态 {"items":[{"version","tags"}]}，只填公开数据拿得到的维度。

    注意：没有逐段时间戳，所以 explanation_builder.mood_timeline() 会返回 []，
    前端情绪角标不渲染（它本来就按拿不到 segments 处理）。
    """
    t = _BY_ID.get(str(cyanite_id))
    if not t:
        return {"items": []}
    tags = t.get("tags") or {}
    available = {
        "MainGenreV2": tags.get("genres") or [],
        "MoodSimpleV2": tags.get("vartags") or [],
        "InstrumentsV2": tags.get("instruments") or [],
        "BpmV2": [_SPEED_BPM[t["speed"]]] if t.get("speed") in _SPEED_BPM else [],
        "VocalsV2": [t["vocalinstrumental"]] if t.get("vocalinstrumental") else [],
    }
    return {"items": [{"version": m, "tags": available[m]}
                      for m in models if available.get(m)]}


def _selfcheck() -> None:
    """离线自检：不打网络，验证曲库与检索契约。"""
    assert _TRACKS, "demo catalog 为空，先跑 build_catalog.py"
    sample = _TRACKS[0]["id"]
    d = display(sample)
    assert d["title"] and d["track_id"] == d["cyanite_id"] == sample, d
    assert display("not-in-catalog", "999")["track_id"] == "999"

    calm = search_by_prompt("peaceful calm piano for a quiet evening", limit=5)
    loud = search_by_prompt("aggressive fast energetic rock workout", limit=5)
    assert len(calm) == 5 and len(loud) == 5, (len(calm), len(loud))
    assert {r["cyanite_id"] for r in calm} != {r["cyanite_id"] for r in loud}, "不同 prompt 必须给不同结果"
    assert all(0.0 <= r["score"] <= 1.0 for r in calm + loud)

    # 一个英文标签都碰不到也不能返回空页面
    assert len(search_by_prompt("夜晚的孤独列车", limit=5)) == 5

    sim = find_similar(calm[0]["cyanite_id"], limit=5)
    assert sim and all(r["cyanite_id"] != calm[0]["cyanite_id"] for r in sim)
    multi = find_similar_multi([calm[0]["cyanite_id"], loud[0]["cyanite_id"]], limit=5)
    assert multi

    tags = model_tags(calm[0]["cyanite_id"], config.EXPLAIN_TAG_MODELS)
    assert tags["items"] and all(i["tags"] for i in tags["items"]), tags
    assert model_tags("not-in-catalog", config.EXPLAIN_TAG_MODELS) == {"items": []}

    print(f"✅ selfcheck: {len(_TRACKS)} 首 / {len(_IDF)} 个标签 / "
          f"calm[0]={display(calm[0]['cyanite_id'])['title']!r} "
          f"loud[0]={display(loud[0]['cyanite_id'])['title']!r}")


if __name__ == "__main__":
    _selfcheck()
