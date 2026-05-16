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
eval $(minikube -p minikube docker-env)
docker build -t custom-postgres:18.4 .
```

```bash
docker network create \
  --driver=bridge \
  --subnet=192.168.2.0/24 \
  --gateway=192.168.2.254 \
  local-bridge
```

```bash
docker-compose up -d
nc -vz $(minikube ip) 5432
nc -vz $(minikube ip) 8888
docker exec -it cid4_postgres /bin/bash
docker exec -it cid4_app /bin/bash
```
