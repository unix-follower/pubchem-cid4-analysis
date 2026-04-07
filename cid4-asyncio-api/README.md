## AsyncIO server
```sh
uv sync
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
python src/main.py
```

TLS configuration:
- `HOST` or `SERVER_HOST` defaults to `0.0.0.0`
- `PORT`, `SERVER_PORT`, or `PORT` defaults to `8443`
- `TLS_CERT_FILE`, `TLS_KEY_FILE`, and optional `TLS_KEY_PASSWORD` can be set explicitly

If explicit TLS files are not set, the asyncio server falls back to the PEM certificate, encrypted private key, and demo password recorded in `data/out/crypto/cid4_crypto.summary.json`.

Quick verification:

```sh
curl -k https://localhost:8443/api/health
curl -k https://localhost:8443/api/cid4/compound
curl -k https://localhost:8443/api/algorithms/taxonomy
curl -k "https://localhost:8443/api/health?mode=error"
```
