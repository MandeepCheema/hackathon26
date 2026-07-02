# Penny Console (FastAPI). Sim backend by default — small, fast build.
# The agent backend (PENNY_BACKEND=agent) will extend this with the root
# requirements + Node/Claude CLI when that workstream lands.
FROM python:3.13-slim
WORKDIR /srv

COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY . .

ENV PORT=8080
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
