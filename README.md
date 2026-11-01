# PoemReciter

A Chinese poem recitation flashcard tool available both as a console script and as a Flask web application.

## Run Locally (Python venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py
```

Then open `http://localhost:8000` in your browser.

To run the classic console version:

```bash
python3 PoemReciter.py
```

## Run with Docker (Local or GCP VM)

```bash
docker compose up -d --build
```

By default, the container exposes port `8000` (`http://localhost:8000`). You can override the host port via `HOST_PORT`:

```bash
HOST_PORT=5001 docker compose up -d --build
```

### Optional Nginx Reverse Proxy on GCP VM

If you are running Nginx on your GCP VM (e.g., alongside `StockTracker`), you can proxy traffic to the container:

```nginx
location /poems/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Run Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```
