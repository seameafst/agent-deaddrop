"""Vercel 部署入口：导出 ASGI app（Vercel Python 运行时原生支持 ASGI）。

本地运行用不到本文件；`vercel deploy` 时由 vercel.json 指向这里。
"""
from app.main import app
