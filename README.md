
# Agentex Python API library

<!-- prettier-ignore -->
[![PyPI version](https://img.shields.io/pypi/v/agentex-sdk.svg?label=pypi%20(stable))](https://pypi.org/project/agentex-sdk/)

The Agentex Python library provides convenient access to the Agentex REST API from any Python 3.9+
application. The library includes type definitions for all request params and response fields,
and offers both synchronous and asynchronous clients powered by [httpx](https://github.com/encode/httpx).

It is generated with [Stainless](https://www.stainless.com/).

## Documentation

The REST API documentation can be found on [docs.gp.scale.com](https://docs.gp.scale.com). The full API of this library can be found in [api.md](api.md).

## Installation

```sh
# install from PyPI
pip install agentex-sdk
```

## Usage

The full API of this library can be found in [api.md](api.md).

```python
import os
from agentex import Agentex

client = Agentex(
    api_key=os.environ.get("AGENTEX_SDK_API_KEY"),  # This is the default and can be omitted
    # defaults to "production".
    environment="development",
)

tasks = client.tasks.list()
```

While you can provide an `api_key` keyword argument,
we recommend using [python-dotenv](https://pypi.org/project/python-dotenv/)
to add `AGENTEX_SDK_API_KEY="My API Key"` to your `.env` file
so that your API Key is not stored in source control.

## Async usage

Simply import `AsyncAgentex` instead of `Agentex` and use `await` with each API call:

```python
import os
import asyncio
from agentex import AsyncAgentex

client = AsyncAgentex(
    api_key=os.environ.get("AGENTEX_SDK_API_KEY"),  # This is the default and can be omitted
    # defaults to "production".
    environment="development",
)


async def main() -> None:
    tasks = await client.tasks.list()


asyncio.run(main())
```

Functionality between the synchronous and asynchronous clients is otherwise identical.

## Debugging

AgentEx provides built-in debugging support for **temporal projects** during local development.

```bash
# Basic debugging
uv run agentex agents run --manifest manifest.yaml --debug-worker

# Wait for debugger to attach before starting
uv run agentex agents run --manifest manifest.yaml --debug-worker --wait-for-debugger

# Custom debug port
uv run agentex agents run --manifest manifest.yaml --debug-worker --debug-port 5679
```

For **VS Code**, add this configuration to `.vscode/launch.json`:

```json
{
  "name": "Attach to AgentEx Worker",
  "type": "debugpy",
  "request": "attach",
  "connect": { "host": "localhost", "port": 5678 },
  "pathMappings": [{ "localRoot": "${workspaceFolder}", "remoteRoot": "." }],
  "justMyCode": false,
  "console": "integratedTerminal"
}
```

The debug server automatically finds an available port starting from 5678 and prints connection details when starting.

### With aiohttp

By default, the async client uses `httpx` for HTTP requests. However, for improved concurrency performance you may also use `aiohttp` as the HTTP backend.

You can enable this by installing `aiohttp`:

```sh
# install from PyPI
pip install agentex-sdk[aiohttp]
```

Then you can enable it by instantiating the client with `http_client=DefaultAioHttpClient()`:

```python
import os
import asyncio
from agentex import DefaultAioHttpClient
from agentex import AsyncAgentex


async def main() -> None:
    async with AsyncAgentex(
        api_key=os.environ.get("AGENTEX_SDK_API_KEY"),  # This is the default and can be omitted
        http_client=DefaultAioHttpClient(),
    ) as client:
        tasks = await client.tasks.list()


asyncio.run(main())
```

## Using types

Nested request parameters are [TypedDicts](https://docs.python.org/3/library/typing.html#typing.TypedDict). Responses are [Pydantic models](https://docs.pydantic.dev) which also provide helper methods for things like:

- Serializing back into JSON, `model.to_json()`
- Converting to a dictionary, `model.to_dict()`

Typed requests and responses provide autocomplete and documentation within your editor. If you would like to see type errors in VS Code to help catch bugs earlier, set `python.analysis.typeCheckingMode` to `basic`.

## Handling errors

When the library is unable to connect to the API (for example, due to network connection problems or a timeout), a subclass of `agentex.APIConnectionError` is raised.

When the API returns a non-success status code (that is, 4xx or 5xx
response), a subclass of `agentex.APIStatusError` is raised, containing `status_code` and `response` properties.

All errors inherit from `agentex.APIError`.

```python
import agentex
from agentex import Agentex

client = Agentex()

try:
    client.tasks.list()
except agentex.APIConnectionError as e:
    print("The server could not be reached")
    print(e.__cause__)  # an underlying Exception, likely raised within httpx.
except agentex.RateLimitError as e:
    print("A 429 status code was received; we should back off a bit.")
except agentex.APIStatusError as e:
    print("Another non-200-range status code was received")
    print(e.status_code)
    print(e.response)
```

Error codes are as follows:

| Status Code | Error Type                 |
| ----------- | -------------------------- |
| 400         | `BadRequestError`          |
| 401         | `AuthenticationError`      |
| 403         | `PermissionDeniedError`    |
| 404         | `NotFoundError`            |
| 422         | `UnprocessableEntityError` |
| 429         | `RateLimitError`           |
| >=500       | `InternalServerError`      |
| N/A         | `APIConnectionError`       |

### Retries

Certain errors are automatically retried 2 times by default, with a short exponential backoff.
Connection errors (for example, due to a network connectivity problem), 408 Request Timeout, 409 Conflict,
429 Rate Limit, and >=500 Internal errors are all retried by default.

You can use the `max_retries` option to configure or disable retry settings:

```python
from agentex import Agentex

# Configure the default for all requests:
client = Agentex(
    # default is 2
    max_retries=0,
)

# Or, configure per-request:
client.with_options(max_retries=5).tasks.list()
```

### Timeouts

By default requests time out after 1 minute. You can configure this with a `timeout` option,
which accepts a float or an [`httpx.Timeout`](https://www.python-httpx.org/advanced/timeouts/#fine-tuning-the-configuration) object:

```python
from agentex import Agentex

# Configure the default for all requests:
client = Agentex(
    # 20 seconds (default is 1 minute)
    timeout=20.0,
)

# More granular control:
client = Agentex(
    timeout=httpx.Timeout(60.0, read=5.0, write=10.0, connect=2.0),
)

# Override per-request:
client.with_options(timeout=5.0).tasks.list()
```

On timeout, an `APITimeoutError` is thrown.

Note that requests that time out are [retried twice by default](#retries).

## Advanced

### Logging

We use the standard library [`logging`](https://docs.python.org/3/library/logging.html) module.

You can enable logging by setting the environment variable `AGENTEX_LOG` to `info`.

```shell
$ export AGENTEX_LOG=info
```

Or to `debug` for more verbose logging.

### How to tell whether `None` means `null` or missing

In an API response, a field may be explicitly `null`, or missing entirely; in either case, its value is `None` in this library. You can differentiate the two cases with `.model_fields_set`:

```py
if response.my_field is None:
  if 'my_field' not in response.model_fields_set:
    print('Got json like {}, without a "my_field" key present at all.')
  else:
    print('Got json like {"my_field": null}.')
```

### Accessing raw response data (e.g. headers)

The "raw" Response object can be accessed by prefixing `.with_raw_response.` to any HTTP method call, e.g.,

```py
from agentex import Agentex

client = Agentex()
response = client.tasks.with_raw_response.list()
print(response.headers.get('X-My-Header'))

task = response.parse()  # get the object that `tasks.list()` would have returned
print(task)
```

These methods return an [`APIResponse`](https://github.com/scaleapi/scale-agentex-python/tree/main/src/agentex/_response.py) object.

The async client returns an [`AsyncAPIResponse`](https://github.com/scaleapi/scale-agentex-python/tree/main/src/agentex/_response.py) with the same structure, the only difference being `await`able methods for reading the response content.

#### `.with_streaming_response`

The above interface eagerly reads the full response body when you make the request, which may not always be what you want.

To stream the response body, use `.with_streaming_response` instead, which requires a context manager and only reads the response body once you call `.read()`, `.text()`, `.json()`, `.iter_bytes()`, `.iter_text()`, `.iter_lines()` or `.parse()`. In the async client, these are async methods.

```python
with client.tasks.with_streaming_response.list() as response:
    print(response.headers.get("X-My-Header"))

    for line in response.iter_lines():
        print(line)
```

The context manager is required so that the response will reliably be closed.

### Making custom/undocumented requests

This library is typed for convenient access to the documented API.

If you need to access undocumented endpoints, params, or response properties, the library can still be used.

#### Undocumented endpoints

To make requests to undocumented endpoints, you can make requests using `client.get`, `client.post`, and other
http verbs. Options on the client will be respected (such as retries) when making this request.

```py
import httpx

response = client.post(
    "/foo",
    cast_to=httpx.Response,
    body={"my_param": True},
)

print(response.headers.get("x-foo"))
```

#### Undocumented request params

If you want to explicitly send an extra param, you can do so with the `extra_query`, `extra_body`, and `extra_headers` request
options.

#### Undocumented response properties

To access undocumented response properties, you can access the extra fields like `response.unknown_prop`. You
can also get all the extra fields on the Pydantic model as a dict with
[`response.model_extra`](https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_extra).

### Configuring the HTTP client

You can directly override the [httpx client](https://www.python-httpx.org/api/#client) to customize it for your use case, including:

- Support for [proxies](https://www.python-httpx.org/advanced/proxies/)
- Custom [transports](https://www.python-httpx.org/advanced/transports/)
- Additional [advanced](https://www.python-httpx.org/advanced/clients/) functionality

```python
import httpx
from agentex import Agentex, DefaultHttpxClient

client = Agentex(
    # Or use the `AGENTEX_BASE_URL` env var
    base_url="http://my.test.server.example.com:8083",
    http_client=DefaultHttpxClient(
        proxy="http://my.test.proxy.example.com",
        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
    ),
)
```

You can also customize the client on a per-request basis by using `with_options()`:

```python
client.with_options(http_client=DefaultHttpxClient(...))
```

### Managing HTTP resources

By default the library closes underlying HTTP connections whenever the client is [garbage collected](https://docs.python.org/3/reference/datamodel.html#object.__del__). You can manually close the client using the `.close()` method if desired, or with a context manager that closes when exiting.

```py
from agentex import Agentex

with Agentex() as client:
  # make requests here
  ...

# HTTP client is now closed
```

## Versioning

This package generally follows [SemVer](https://semver.org/spec/v2.0.0.html) conventions, though certain backwards-incompatible changes may be released as minor versions:

1. Changes that only affect static types, without breaking runtime behavior.
2. Changes to library internals which are technically public but not intended or documented for external use. _(Please open a GitHub issue to let us know if you are relying on such internals.)_
3. Changes that we do not expect to impact the vast majority of users in practice.

We take backwards-compatibility seriously and work hard to ensure you can rely on a smooth upgrade experience.

We are keen for your feedback; please open an [issue](https://www.github.com/scaleapi/scale-agentex-python/issues) with questions, bugs, or suggestions.

### Determining the installed version

If you've upgraded to the latest version but aren't seeing any new features you were expecting then your python environment is likely still using an older version.

You can determine the version that is being used at runtime with:

```py
import agentex
print(agentex.__version__)
```

## Troubleshooting

### Authentication and API Key Issues

**`AuthenticationError` (401) when making requests**

Ensure your API key is set correctly. The SDK reads from the `AGENTEX_SDK_API_KEY` environment variable by default:

```sh
export AGENTEX_SDK_API_KEY="your-api-key-here"
```

Or pass it explicitly when creating the client:

```python
from agentex import Agentex

client = Agentex(api_key="your-api-key-here")
```

**`PermissionDeniedError` (403) for valid requests**

Your API key may not have the required permissions for the operation. Verify your key has access to the resource you are requesting.

---

### Installation Issues

**`ModuleNotFoundError: No module named 'agentex'`**

Install the SDK from PyPI:

```sh
pip install agentex-sdk
```

If you are using the `aiohttp` backend, install the optional dependency:

```sh
pip install agentex-sdk[aiohttp]
```

**Wrong Python version**

The SDK requires Python 3.9 or higher. Check your version:

```sh
python --version
```

---

### Connection and Timeout Errors

**`APIConnectionError` — cannot reach the server**

This usually indicates a network issue. Common causes:
- No internet connection or firewall blocking outbound HTTPS
- Incorrect `base_url` (check for typos in custom base URL configurations)
- Proxy misconfiguration

If you are behind a proxy, configure it via the HTTP client:

```python
import httpx
from agentex import Agentex, DefaultHttpxClient

client = Agentex(
    http_client=DefaultHttpxClient(
        proxy="http://my.proxy.example.com",
    ),
)
```

**`APITimeoutError` — requests timing out**

The default timeout is 1 minute. For slow networks or large payloads, increase it:

```python
from agentex import Agentex

client = Agentex(timeout=120.0)  # 2 minutes
```

---

### Rate Limiting

**`RateLimitError` (429) — too many requests**

The SDK automatically retries rate-limited requests twice with exponential backoff. If you still hit limits, add explicit retry logic or reduce request frequency:

```python
from agentex import Agentex

client = Agentex(max_retries=5)
```

To disable automatic retries entirely:

```python
client = Agentex(max_retries=0)
```

---

### Environment and Logging

**Enabling debug logging to diagnose issues**

Set the `AGENTEX_LOG` environment variable before running your code:

```sh
# Info-level logs
export AGENTEX_LOG=info

# Verbose debug logs (includes request/response bodies)
export AGENTEX_LOG=debug
```

**Identifying the installed SDK version**

```python
import agentex
print(agentex.__version__)
```

If the version does not match what you expect, you may have multiple Python environments. Use `pip show agentex-sdk` to confirm which environment the package is installed in.

---

### Agent Development Issues

**Agent fails to start with `agentex agents run`**

1. Verify your `manifest.yaml` is valid and points to the correct agent entry point.
2. Check that all dependencies are installed in your agent's virtual environment.
3. Use the `--debug-worker` flag to attach a debugger and inspect runtime errors:

   ```sh
   uv run agentex agents run --manifest manifest.yaml --debug-worker
   ```

**Debugger not connecting in VS Code**

Ensure your `.vscode/launch.json` uses the correct port (default `5678`):

```json
{
  "name": "Attach to AgentEx Worker",
  "type": "debugpy",
  "request": "attach",
  "connect": { "host": "localhost", "port": 5678 },
  "pathMappings": [{ "localRoot": "${workspaceFolder}", "remoteRoot": "." }],
  "justMyCode": false,
  "console": "integratedTerminal"
}
```

If port `5678` is already in use, specify a different port:

```sh
uv run agentex agents run --manifest manifest.yaml --debug-worker --debug-port 5679
```

And update the `port` in your launch configuration to match.

**Using `--wait-for-debugger` to pause startup**

If your breakpoints are not hit because execution finishes before the debugger attaches, use the `--wait-for-debugger` flag:

```sh
uv run agentex agents run --manifest manifest.yaml --debug-worker --wait-for-debugger
```

The worker will pause until the debugger connects.

---

### Type Checking and IDE Integration

**No autocomplete or type errors in VS Code**

Set `python.analysis.typeCheckingMode` to `basic` in your VS Code settings to enable Pyright-based type checking. This surfaces type errors in the editor before running your code.

**Distinguishing `null` from a missing field in API responses**

A field that is absent and a field explicitly set to `null` both appear as `None` in Python. Use `.model_fields_set` to tell them apart:

```python
if response.my_field is None:
    if "my_field" not in response.model_fields_set:
        print("Field was not present in the response")
    else:
        print("Field was explicitly null")
```

---

## Requirements

Python 3.9 or higher.

## Contributing

See [the contributing documentation](./CONTRIBUTING.md).
