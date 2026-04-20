FROM pytorch/pytorch:2.11.0-cuda13.0-cudnn9-devel
# FROM tensorflow/tensorflow:latest

WORKDIR /opt/app/

COPY pyproject.toml ./pyproject.toml
COPY uv.lock ./uv.lock

RUN uv sync

EXPOSE 8888
CMD [ "uv", "run", "jupyter", "lab", "--allow-root", "--ip=0.0.0.0", "--NotebookApp.allow_origin='*'" ]
