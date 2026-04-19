## Cheat sheet
```bash
docker run -it --rm pytorch/pytorch:2.11.0-cuda13.0-cudnn9-devel bash

docker build -t cid4-pytorch:latest .
docker run --rm --name cid4-pytorch -p 8888:8888 cid4-pytorch:latest
nc -vz $(minikube ip) 8888

docker image rm cid4-pytorch:latest
```
http://192.168.64.23:8888/lab?token=<token>
