"""构建期脚本 · 从公开 Jamendo API 抓一份本地演示曲库。

只在开发机上跑一次，产物 data/demo_catalog.json 入库；**运行时不需要任何 key**。
数据全部是 Jamendo 公开元数据（CC BY-SA 3.0，见 DATA_LICENSE.md），不含任何 Cyanite 内容。

    JAMENDO_CLIENT_ID=xxx uv run python build_catalog.py

覆盖面靠一组 mood/genre 种子词分散取样：Cyanite 没了之后检索退化成本地标签匹配，
曲库必须在情绪空间里铺得够开，不同 prompt 才会给出不同结果。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import requests

import config

OUT = pathlib.Path(__file__).resolve().parent / "data" / "demo_catalog.json"
PER_SEED = 200          # Jamendo 单次上限
TARGET = 3000           # 去重后保留上限；曲库越深，反复 dislike 后越不容易见底

# 情绪/风格种子。每个词打一次 fuzzytags，取并集——比单一 query 铺得开得多。
SEEDS = [
    "melancholic sad", "peaceful calm", "dreamy ethereal", "dark cinematic",
    "energetic upbeat", "groovy funky", "nostalgic retro", "epic powerful",
    "romantic warm", "lonely night", "hopeful uplifting", "tense suspense",
    "playful happy", "meditative ambient", "rainy melancholy", "summer sunny",
    "piano solo", "acoustic guitar", "jazz saxophone", "strings orchestral",
    "electronic synth", "lofi chill", "rock guitar", "folk acoustic",
    "classical piano", "ambient drone", "hiphop beat", "world percussion",
    "morning fresh", "midnight drive",
]


def _fetch(session: requests.Session, seed: str) -> list[dict]:
    r = session.get(
        f"{config.JAMENDO_BASE_URL}/tracks/",
        params={
            "client_id": config.JAMENDO_CLIENT_ID,
            "format": "json",
            "limit": PER_SEED,
            "fuzzytags": seed,
            "include": "musicinfo",
            "order": "popularity_total",
            "audioformat": "mp32",
        },
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("headers", {}).get("status") != "success":
        print(f"  [warn] {seed}: {body.get('headers', {}).get('error_message')}")
        return []
    return body.get("results", [])


def _row(t: dict) -> dict | None:
    """只留能渲染成卡片的曲：必须有数字 id + 真实曲名。"""
    tid = str(t.get("id") or "")
    if not tid.isdigit() or not t.get("name"):
        return None
    info = t.get("musicinfo") or {}
    tags = info.get("tags") or {}
    return {
        "id": tid,
        "title": t.get("name", ""),
        "artist": t.get("artist_name", ""),
        "duration": t.get("duration") or 0,
        "speed": info.get("speed", ""),
        "vocalinstrumental": info.get("vocalinstrumental", ""),
        "acousticelectric": info.get("acousticelectric", ""),
        "tags": {
            "genres": tags.get("genres") or [],
            "instruments": tags.get("instruments") or [],
            "vartags": tags.get("vartags") or [],
        },
        "license_ccurl": t.get("license_ccurl", ""),
    }


def main() -> int:
    if not config.JAMENDO_CLIENT_ID:
        print("JAMENDO_CLIENT_ID 未设置（构建期才需要，运行时不需要）")
        return 1

    session = requests.Session()
    by_id: dict[str, dict] = {}
    for i, seed in enumerate(SEEDS, 1):
        rows = _fetch(session, seed)
        added = 0
        for t in rows:
            row = _row(t)
            # 无标签的曲对本地标签匹配毫无贡献，直接丢
            if row and row["id"] not in by_id and any(row["tags"].values()):
                by_id[row["id"]] = row
                added += 1
        print(f"[{i:>2}/{len(SEEDS)}] {seed:<22} +{added:<4} 累计 {len(by_id)}")
        time.sleep(0.2)   # 温和一点，别把共享额度打满

    tracks = sorted(by_id.values(), key=lambda r: r["id"])[:TARGET]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "attribution": "Music and metadata courtesy of Jamendo (https://www.jamendo.com). "
                       "Per-track Creative Commons licenses apply; see license_ccurl.",
        "tracks": tracks,
    }, ensure_ascii=False, indent=1))

    tagged = sum(1 for t in tracks if t["tags"]["vartags"])
    print(f"\n✅ {len(tracks)} 首 -> {OUT}  ({OUT.stat().st_size // 1024} KB, 带情绪标签 {tagged})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
