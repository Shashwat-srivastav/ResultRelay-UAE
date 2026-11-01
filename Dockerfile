# ResultRelay — API + pre-built console on one port. Synthetic data only; no authentication by default.
FROM python:3.12-slim
WORKDIR /opt/resultrelay
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY kb/ kb/
COPY scenarios/ scenarios/
COPY evaluation/ evaluation/
COPY scripts/ scripts/
COPY run_demo.py pyproject.toml ./
RUN useradd --system relay && chown -R relay /opt/resultrelay
USER relay
ENV RESULTRELAY_DB=/tmp/resultrelay.db
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
