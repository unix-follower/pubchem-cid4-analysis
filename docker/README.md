## Cheat sheet
Disable autorstart
```bash
sudo systemctl disable docker.service docker.socket
```
```bash
sudo systemctl start docker
sudo systemctl status docker
```

```bash
docker network create \
  --driver=bridge \
  --subnet=192.168.2.0/24 \
  --gateway=192.168.2.254 \
  local-bridge
```
