
# Agentex Python API library

[![PyPI version](https://img.shields.io/pypi/v/agentex-sdk.svg?label=pypi%20(stable))](https://pypi.org/project/agentex-sdk/)

The Agentex Python library provides convenient access to the Agentex REST API from any Python 3.9+ application.

## Documentation

API documentation: [docs.gp.scale.com](https://docs.gp.scale.com). Full library API reference: [api.md](api.md).

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

Store your API key in a `.env` file as `AGENTEX_SDK_API_KEY="My API Key"` and use [python-dotenv](https://pypi.org/project/python-dotenv/) to avoid storing it in source control.

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

## Handling errors

```python
import agentex
from agentex import Agentex

client = Agentex()

try:
    client.tasks.list()
except agentex.APIConnectionError as e:
    print("The server could not be reached")
except agentex.RateLimitError as e:
    print("Rate limited (429)")
except agentex.APIStatusError as e:
    print(e.status_code)
```

Errors automatically retry 2 times by default for connection errors, timeouts, 429, and 5xx responses.

## Requirements

Python 3.9 or higher.

## Contributing

See [the contributing documentation](./CONTRIBUTING.md).
