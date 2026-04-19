## Cheat sheet
```bash
docker run -it --rm tensorflow/tensorflow bash


docker build -t cid4-tensorflow:latest .
docker run --rm --name cid4-tensorflow -p 8888:8888 cid4-tensorflow:latest
nc -vz $(minikube ip) 8888

docker image rm cid4-tensorflow:latest
```
http://192.168.64.23:8888/lab?token=<token>
