"""HTTP 层 · 冻死的数据契约 + 路由（你负责）。

只做两件事：定义请求/响应 schema（前后端的接缝），把请求转给 orchestrator。
业务编排全在 orchestrator.py，这里保持薄。

run: uv run uvicorn app:app --reload
"""
from __future__ import annotations

from urllib.parse import quote

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

import config
import orchestrator

app = FastAPI(title="Cochlea")

# ponytail: dev 全放行；上线再收敛到具体来源
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ─────────── 请求契约 ───────────
class IntentIn(BaseModel):
    text: str
    user_id: str = "demo"


class FollowUpIn(BaseModel):
    session_id: str
    text: str


class ConfirmIn(BaseModel):
    session_id: str


class FeedbackIn(BaseModel):
    session_id: str
    track_id: str
    verdict: str  # "like" | "dislike"
    mode: str = "normal"  # "normal" | "anti_addiction"


class ExplainIn(BaseModel):
    session_id: str
    track_id: str


class ExplainSoundsLikeYouIn(BaseModel):
    user_id: str = "demo"
    cyanite_id: str


# ─────────── 响应裁剪（只把前端要的字段吐出去）───────────
def _intent_view(s: dict) -> dict:
    return {"session_id": s["id"], "whiteboard_posts": s["whiteboard_posts"],
            "query_card": s["query_card"]}


def _board_view(s: dict) -> dict:
    return {"whiteboard_posts": s["whiteboard_posts"], "query_card": s["query_card"]}


def _cards_view(s: dict) -> dict:
    fields = ("track_id", "cyanite_id", "title", "artist", "source", "score", "why")
    cards = [{k: c[k] for k in fields if k in c} for c in s["visible_cards"]]
    return {"cards": cards, "candidate_pool_size": len(s["candidate_pool"])}


def _guard(fn, *args):
    try:
        return fn(*args)
    except orchestrator.SessionNotFound:
        raise HTTPException(404, "unknown session_id")


# ─────────── 路由 ───────────
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/intent")
def intent(body: IntentIn):
    return _intent_view(orchestrator.start_session(body.user_id, body.text))


@app.post("/intent/follow-up")
def follow_up(body: FollowUpIn):
    return _board_view(_guard(orchestrator.add_follow_up, body.session_id, body.text))


@app.post("/intent/confirm")
def confirm(body: ConfirmIn):
    return _cards_view(_guard(orchestrator.confirm, body.session_id))


@app.post("/feedback")
def feedback(body: FeedbackIn):
    return _cards_view(_guard(orchestrator.feedback, body.session_id, body.track_id, body.verdict, body.mode))


@app.post("/round/finish")
def round_finish(body: ConfirmIn):
    """用户点「完成本轮」：把这一轮选的歌落成「感觉」记忆，返回更新后的画像。"""
    return _guard(orchestrator.finish_round, body.session_id)


@app.post("/explain")
def explain(body: ExplainIn):
    return _guard(orchestrator.explain, body.session_id, body.track_id)


@app.get("/your-sound")
def your_sound(user_id: str = "demo"):
    return {"memory_md": orchestrator.your_sound(user_id)}


@app.post("/explain-sounds-like-you")
def explain_sounds_like_you(body: ExplainSoundsLikeYouIn):
    """Why the sounds-like-you track IS this user — based on their taste profile."""
    return _guard(orchestrator.explain_sounds_like_you, body.user_id, body.cyanite_id)


@app.get("/sounds-like-you")
def sounds_like_you(user_id: str = "demo"):
    """「听起来像你」：基于长期画像搜一首 AI 眼中的「你本人」专属歌。"""
    return _guard(orchestrator.sounds_like_you, user_id)


# ─────────── 高质量下载代理 ───────────
# 走官方 /tracks API 拿 audiodownload + audiodownload_allowed（艺术家可关下载），
# 再服务器端带 Referer 取文件。浏览器没法直接下：Jamendo 防盗链 403 + 无 CORS 头。
# 全程重试：Jamendo 偶发连接重置，单次失败不该让用户拿到 500。
_DL_HEADERS = {"Referer": "https://www.jamendo.com/", "User-Agent": "Mozilla/5.0"}


def _get_with_retry(url: str, *, params=None, tries: int = 3, **kw) -> requests.Response:
    last = None
    for _ in range(tries):
        try:
            r = requests.get(url, params=params, headers=_DL_HEADERS, timeout=30, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
    raise HTTPException(502, f"Jamendo unreachable: {last}")


@app.get("/download/{track_id}")
def download(track_id: str):
    if not track_id.isdigit():  # 只允许 Jamendo 数字 id，挡 SSRF
        raise HTTPException(400, "track_id must be numeric")
    if not config.JAMENDO_CLIENT_ID:
        raise HTTPException(503, "download disabled: JAMENDO_CLIENT_ID not set")

    meta = _get_with_retry(f"{config.JAMENDO_BASE_URL}/tracks",
                           params={"client_id": config.JAMENDO_CLIENT_ID, "id": track_id,
                                   "format": "json", "audioformat": "mp32"}).json()
    results = meta.get("results") or []
    if not results:
        raise HTTPException(404, "track not found on Jamendo")
    t = results[0]
    if not t.get("audiodownload_allowed") or not t.get("audiodownload"):
        raise HTTPException(403, "The artist has disabled download for this track.")

    # 流式透传：浏览器点完立刻开始下、能显示进度，而不是等服务器缓冲完整文件。
    # 错误状态码靠上面的 /tracks 元数据预检保证；这里只有上游中途断开才会半途失败（罕见，可接受）。
    r = _get_with_retry(t["audiodownload"], stream=True)
    name = quote(f'{t.get("name", "track")} - {t.get("artist_name", "Jamendo")}.mp3')
    headers = {"content-disposition": f"attachment; filename*=UTF-8''{name}"}
    if cl := r.headers.get("content-length"):  # 透传长度，浏览器才有进度条
        headers["content-length"] = cl
    return StreamingResponse(r.iter_content(64 * 1024), media_type="audio/mpeg", headers=headers)
