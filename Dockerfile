FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY gem_monitor ./gem_monitor
COPY keywords.json ./keywords.json
RUN pip install --no-cache-dir .
ENV DATABASE_PATH=/app/data/monitor.sqlite3
RUN mkdir -p /app/data
EXPOSE 8000
# Override command per service: API uses uvicorn; worker uses python -m gem_monitor.scheduler.
CMD ["uvicorn", "gem_monitor.api:app", "--host", "0.0.0.0", "--port", "8000"]
