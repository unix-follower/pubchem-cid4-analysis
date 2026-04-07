## Starlette server
The Python workspace also includes a Starlette HTTPS server that exposes the same `/api/...` surface as the FastAPI, Scala Tomcat, and Scala Netty backends.

Install the optional server dependencies:

```sh
uv sync
```

Run it from the `py` workspace:

```sh
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/main.py
```

TLS configuration is shared with the FastAPI runner:
- `HOST` or `SERVER_HOST` defaults to `0.0.0.0`
- `PORT`, `SERVER_PORT` defaults to `8443`
- `TLS_CERT_FILE`, `TLS_KEY_FILE`, and optional `TLS_KEY_PASSWORD` can be set explicitly

If explicit TLS files are not set, the Starlette server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

Quick verification:

```sh
curl -k https://localhost:8443/api/health
curl -k https://localhost:8443/api/cid4/conformer/1
curl -k https://localhost:8443/api/algorithms/taxonomy
curl -k "https://localhost:8443/api/health?mode=error"
```
