# Hello Oldowan Agent

This is a simple example agent that demonstrates the basics of the Agent 2 Client Protocol (ACP) and the AgentEx framework with an integration to oldowan.

## For Development
Navigate to `tutorials/00_sync/030_hello_oldowan`

```bash
# Generate CodeArtifact configuration for building (run from repo root)
./setup-build-codeartifact.sh

# Set up local development environment
uv venv --python 3.12
source .venv/bin/activate

uv pip install -r requirements.txt --prerelease=allow
```
