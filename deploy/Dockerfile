# Agent Dead Drop —— 生产镜像（Oracle Always Free / 任意 Linux VPS 通用）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt requirements-mcp.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-mcp.txt || true

# 再拷代码
COPY app ./app
COPY tools ./tools
COPY mcp ./mcp
COPY supabase ./supabase

# 数据目录（sqlite / GeoIP 库 / 隧道令牌）由 compose 挂载进来
RUN mkdir -p /app/data

# 只监听容器网络；公网入口由 cloudflared 隧道提供，不暴露端口
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
