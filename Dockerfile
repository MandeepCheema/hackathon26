# Penny Console (FastAPI) + in-process agent backend.
# claude-agent-sdk ships a bundled CLI, so no Node layer is needed —
# flip PENNY_BACKEND=agent via env, the image supports both.
FROM python:3.13-slim
WORKDIR /srv

COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

# Agent backend (PENNY_BACKEND=agent): claude-agent-sdk ships a bundled CLI —
# no Node needed. Own layer so the 76MB wheel only rebuilds when reqs change.
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
