# External model adapter contract

Install the adapter module separately in the active Python environment, then set `AUTOGUI_BACKEND` to its importable module name. Adapter implementations are not included in this source distribution.

## Text and vision generation

```python
def chat(*, messages, purpose, max_tokens):
    """Return {"text": str, "usage": optional mapping}."""
```

`messages` is a list of role messages. For text-only calls, `content` is a string. For vision calls, it is a list of text and image items, with images passed as data URLs.

`purpose` is `llm_chat`, `llm_vision`, or `qc` and can be used to select different models. `max_tokens` is an integer or `None`.

The response must contain a nonempty `text` string. Optional `usage` metadata records only nonnegative integer values for `prompt_tokens`, `completion_tokens`, and `total_tokens`.

## Image generation and editing

```python
def image(*, prompt, operation, image_bytes, size, quality):
    """Return {"image": bytes, "usage": optional mapping}."""
```

- `operation="generate"`: generate an image from text, with `image_bytes=None`.
- `operation="edit"`: edit a reference image, with `image_bytes` containing the previous frame.
- `size` is a string such as `1792x1024`; `quality` is `low`, `medium`, or `high`.
- The response's `image` field contains decodable PNG bytes with exactly the requested width and height, for the initial screenshot or next observation. Other formats or sizes are rejected.

Adapters must support concurrent calls or lock any model instances that require serial access.

## Errors and retries

An adapter can raise `autogui.clients.backend.TransientBackendError` to report a retryable failure. Other exceptions are treated as permanent failures. The public pipeline does not expose the adapter's original exception details.

Text calls use bounded retries with backoff. `IMAGE_MAX_RETRIES` controls image retries. `LLM_RATE_PER_MIN` and `IMAGE_RATE_PER_MIN` control request spacing within a process.

## Offline development

Tests implement this contract with in-memory modules or mocked responses, so no real model adapter is required. Run `python -m unittest tests.test_backend -v` to check the adapter boundary, then run the full test suite.

## Minimal adapter shape

The module below illustrates the contract. Supply the two provider functions in your own
installed module. Images must be valid encoded image bytes; empty or corrupt output is rejected.

```python
def chat(*, messages, purpose, max_tokens):
    response = provider_chat(messages=messages, purpose=purpose, max_tokens=max_tokens)
    return {"text": response.text, "usage": response.usage}


def image(*, prompt, operation, image_bytes, size, quality):
    encoded_image = provider_image(
        prompt=prompt, operation=operation, reference=image_bytes, size=size, quality=quality,
    )
    return {"image": encoded_image}
```

The public pipeline records numeric token counters and safe operation errors. Tasks and
screenshots are still passed to the adapter as model inputs. Keep your adapter's connection
configuration outside this repository.
