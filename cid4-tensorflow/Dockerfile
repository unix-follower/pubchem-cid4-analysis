FROM tensorflow/tensorflow:latest

WORKDIR /opt/app/

COPY pyproject.toml ./pyproject.toml

RUN pip install uv && uv sync --python 3.13

EXPOSE 8888
CMD [ "uv", "run", "jupyter", "lab", "--allow-root", "--ip=0.0.0.0", "--NotebookApp.allow_origin='*'" ]
