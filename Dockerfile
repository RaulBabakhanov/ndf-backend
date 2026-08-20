FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
COPY app ./app
COPY data ./data
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["sh", "-c", "python -m app.init_db && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
