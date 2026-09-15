"""基础设施 · 可选的「已知用户历史喜欢」。

赛期这份数据来自主办方 data/users.csv（pseudonymized，赛后按协议删除）。
公开演示版里它不存在——本模块因此把文件当作**可选**：缺了就返回空列表，
唯一的消费方 orchestrator.explain() 只是少一个可选的解释素材，不影响主流程。

id 体系：Cyanite 下线后 cyanite_id 就是 Jamendo track_id（见 catalog.py）。
"""
from __future__ import annotations

import csv
import pathlib

import catalog

_DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "users.csv"


def _load() -> dict[str, list[str]]:
    if not _DATA.exists():
        return {}
    with _DATA.open() as f:
        return {
            str(row["user_id"]): [t for t in row.get("liked_track_ids", "").split() if t]
            for row in csv.DictReader(f)
        }


_USER_LIKES: dict[str, list[str]] = _load()


def liked_cyanite_ids(user_id: str) -> list[str]:
    """该用户已知的历史喜欢曲（曲库里没有的会被跳过）。没有档案就返回 []。"""
    out = []
    for track_id in _USER_LIKES.get(str(user_id), []):
        try:
            out.append(catalog.to_cyanite(track_id))
        except KeyError:
            continue
    return out
