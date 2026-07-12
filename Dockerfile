# Container for the Gradio demo (app.py) — used by Render (render.yaml) or any
# Docker host. Not needed for library/CLI installs; those come from PyPI.

FROM python:3.13-slim

WORKDIR /app

# Install the package (with the gradio extra) from the repo itself.
COPY pyproject.toml README.md LICENSE ./
COPY khatt ./khatt
COPY app.py ./
RUN pip install --no-cache-dir ".[app]"

# Gradio reads these env vars natively; PORT is injected by the host at runtime.
ENV GRADIO_SERVER_NAME=0.0.0.0
EXPOSE 7860

CMD ["sh", "-c", "GRADIO_SERVER_PORT=${PORT:-7860} python app.py"]
