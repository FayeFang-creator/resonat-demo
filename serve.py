"""单进程部署入口：一个源站同时供前端静态文件和后端 API。

开发时前端跑 Vite dev server，用 proxy 把 /api 转到 :8000（见 frontend/vite.config.ts）。
线上没有 Vite，所以这里把后端挂到 /api、把构建产物挂到 /，前端 api.ts 里的
`BASE = "/api"` 因此一字不用改，也不需要 CORS。

    uv run uvicorn serve:root --port 7860       # 需先 cd frontend && npm run build
"""
from __future__ import annotations

import pathlib

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "backend"))

import app as backend  # noqa: E402  (需先把 backend 加入 sys.path)

DIST = pathlib.Path(__file__).resolve().parent / "frontend" / "dist"


class SPAFiles(StaticFiles):
    """找不到的路径回退到 index.html。

    前端有客户端路由（/results），直接刷新该地址时磁盘上并没有对应文件，
    不回退就会 404——访客刷新一下页面就"坏了"。
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


root = FastAPI(title="Sounds Like You")
root.mount("/api", backend.app)

if DIST.is_dir():
    root.mount("/", SPAFiles(directory=DIST, html=True), name="frontend")
else:  # 没构建前端也让 API 起得来，便于单独调后端
    print(f"[warn] {DIST} 不存在；只提供 /api（先跑 cd frontend && npm run build）")
