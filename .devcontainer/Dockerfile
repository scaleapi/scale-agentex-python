ARG VARIANT="3.12"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

USER vscode

COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /uvx /bin/

RUN echo "[[ -d .venv ]] && source .venv/bin/activate || export PATH=\$PATH" >> /home/vscode/.bashrc
