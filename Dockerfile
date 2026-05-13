FROM python:3.11-slim

# libgomp1 is required by faiss-cpu at runtime on Debian/Ubuntu
RUN apt-get update && apt-get install -y libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Q&A_Agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Q&A_Agent/ .

CMD uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000}
