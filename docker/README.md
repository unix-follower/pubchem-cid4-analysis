```bash
docker network create \
  --driver=bridge \
  --subnet=192.168.2.0/24 \
  --gateway=192.168.2.254 \
  local-bridge
```
