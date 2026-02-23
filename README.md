
# Agentex Python API library

[![PyPI version](https://img.shields.io/pypi/v/agentex-sdk.svg?label=pypi%20(stable))](https://pypi.org/project/agentex-sdk/)

Python library for the [Agentex](https://docs.gp.scale.com) REST API. Supports both synchronous and asynchronous usage.

## Installation

```sh
pip install agentex-sdk
```

## Usage

```python
import os
from agentex import Agentex

client = Agentex(
    api_key=os.environ.get("AGENTEX_SDK_API_KEY"),
)

tasks = client.tasks.list()
```

Set `AGENTEX_SDK_API_KEY` in your environment (or `.env` file) to avoid hardcoding credentials.

## Async usage

```python
import os
import asyncio
from agentex import AsyncAgentex

client = AsyncAgentex(
    api_key=os.environ.get("AGENTEX_SDK_API_KEY"),
)

async def main() -> None:
    tasks = await client.tasks.list()

asyncio.run(main())
```

## Debugging

```bash
uv run agentex agents run --manifest manifest.yaml --debug-worker
```

## Error handling

```python
import agentex
from agentex import Agentex

client = Agentex()

try:
    client.tasks.list()
except agentex.APIConnectionError as e:
    print("Could not reach server")
except agentex.RateLimitError as e:
    print("Rate limited (429)")
except agentex.APIStatusError as e:
    print(e.status_code, e.response)
```

## Requirements

Python 3.9 or higher.

## Documentation

- [API Reference](https://docs.gp.scale.com)
- [Full API details](api.md)
- [Contributing](./CONTRIBUTING.md)
