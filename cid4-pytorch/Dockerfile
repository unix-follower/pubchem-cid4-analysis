FROM pytorch/pytorch:2.11.0-cuda13.0-cudnn9-devel

WORKDIR /opt/app/

COPY pyproject.toml ./pyproject.toml

RUN uv sync

EXPOSE 8888
CMD [ "uv", "run", "jupyter", "lab", "--allow-root", "--ip=0.0.0.0", "--NotebookApp.allow_origin='*'" ]
