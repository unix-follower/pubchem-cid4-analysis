## CID4 Oat++ server
Without TLS
```bash
export DATA_DIR="$(pwd)/../data"
./build/main --port 8000
curl -v http://127.0.0.1:8000/api/health
curl -v "http://127.0.0.1:8000/api/health?mode=error"
curl -v http://127.0.0.1:8000/api/cid4/conformer/1
curl -v http://127.0.0.1:8000/api/cid4/compound
```

With TLS enabled
```bash
./build/main
curl -kv https://127.0.0.1:8443/api/health
curl -kv "https://127.0.0.1:8443/api/health?mode=error"
curl -kv https://127.0.0.1:8443/api/cid4/conformer/1
curl -kv https://127.0.0.1:8443/api/cid4/compound
```
