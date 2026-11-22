# Gepetto Python SDK

[![PyPI](https://img.shields.io/pypi/v/gepetto)](https://pypi.org/project/gepetto/) [![Tests](https://github.com/Gepetto-AI/gepetto-python/actions/workflows/tests.yml/badge.svg)](https://github.com/Gepetto-AI/gepetto-python/actions/workflows/tests.yml)

The official Python SDK of the [Gepetto API v2](https://docs.gepettoapp.com): real estate photo editing. Enhance a photo, declutter a room, furnish it, change the sky, restyle it, repaint walls and floors, upscale. One call, an image URL in return.

```bash
pip install gepetto
```

Python 3.10 or later. No dependency: the standard library is enough. Fully typed.

## Quickstart

```python
from gepetto import Gepetto

gepetto = Gepetto()  # reads GEPETTO_API_KEY

job = gepetto.furnish(
    url="https://assets.gepettoapp.com/raw-images/b85e2aa5-ac29-44a0-93eb-2de0a40f7905.png",
    room_id="living_room",
    style_id="scandinave",
)

print(job.output)  # https://assets.gepettoapp.com/api/v2/jobs/.../output.jpg
```

No key yet? A free test key (200 real renders, no watermark) in two commands:

```bash
npx @gepetto/cli login   # opens a page: check the code, click "Authorize"
npx @gepetto/cli init    # writes GEPETTO_API_KEY to .env
```

The key can also be given directly: `Gepetto("test_...")`, or `Gepetto(api_key=..., timeout=120)`.

## What you get

- **The method waits for the image.** Each tool returns the finished `Job`, whose `output` is the image URL. A failed render raises a `GepettoError`, and is never charged.
- **Your editor knows the parameters.** Every tool takes keyword arguments with types: completion in VS Code and PyCharm, and mypy or Pyright catch a typo before the API does.
- **Retries are safe.** Every render is sent with an idempotency key (yours, or one generated). A network error, a `429` or a `5xx` is retried with the same key: a render is never started, nor billed, twice.
- **Long renders just work.** If the connection drops while the image is being made, the SDK picks up the same job and waits for it.
- **The names are those of the API, in snake_case.** `room_id` is `roomId` in the [docs](https://docs.gepettoapp.com): same fields, same ids, same error codes.

## Tools

The `url` of every tool is a public http(s) URL of a JPEG, PNG, WebP or HEIC image: upload the photo to your own storage first. The output URL is public too; copy the image if you keep it.

| Method | What it does |
| --- | --- |
| `enhance(url=..., straighten=True)` | Light and colours corrected at the size of the photo, nothing redrawn |
| `declutter(url=..., keep_fireplace=True)` | The whole room emptied (also `keep_kitchen`, `keep_bathroom`) |
| `declutter(url=..., mask=...)` | What the mask covers removed |
| `furnish(url=..., room_id=..., style_id=...)` | The whole room furnished |
| `furnish(url=..., mask=..., room_id=..., style_id=...)` | The zone of the mask furnished as a room |
| `furnish(url=..., mask=..., furniture_id=...)` | One piece of furniture in the zone (`style_id` optional) |
| `sunshine(url=..., sky_id="sunny")` | A blue sky and the matching light (also `light_projection`, `pool_light`, `add_leafs`) |
| `creative_redesign(url=..., room_id=..., style_id=...)` | The room redesigned in a style (`preserve_floor` to keep the floor) |
| `surfaces(url=..., surface="walls", wall_type=...)` | Walls repainted (`"custom"` with `custom_wall_color`, `preserve_ceiling`) |
| `surfaces(url=..., surface="floor", floor_type=...)` | Floor changed (`include_baseboard`) |
| `surfaces(url=..., surface="finish", finish_id=...)` | A finish applied: clean floor, clean pool, mowed lawn... |
| `upscale(url=..., resolution="4k")` | Enlarged to about 4 (`"2k"`) or 16 megapixels (`"4k"`, default) |

**Masks.** A mask is a black image with the zone painted in white, drawn on the photo. Give its URL, or the image itself in base64: nothing to host.

```python
from gepetto import mask_from_file

job = gepetto.declutter(url=photo_url, mask=mask_from_file("mask.png"))
```

Every tool also takes:

```python
gepetto.enhance(
    url=photo_url,
    straighten=True,
    idempotency_key=f"{photo.id}:enhance",  # one key per photo and per tool
    timeout=120,                            # seconds, for this call (default: the client's, 10 minutes)
)
```

## Lists

The ids are not guessable: they come from the API.

```python
gepetto.list_rooms()       # room_id, with the modes of each room ("auto": whole room, "zone": with a mask)
gepetto.list_styles()      # style_id
gepetto.list_furnitures()  # furniture_id, grouped by type
gepetto.list_skies()       # sky_id
gepetto.list_surfaces()    # {"walls": [...], "floors": [...], "finishes": [...]}
```

## Errors

Every error is a `GepettoError`. `code` is stable, for your code; the message says what to do next.

```python
from gepetto import GepettoError

try:
    job = gepetto.furnish(url=photo_url, room_id="bedroom", style_id="modrn")
except GepettoError as e:
    e.code    # "unknown_style"
    e.param   # "styleId"
    e.status  # 400
    str(e)    # No style "modrn". The list is on GET /v2/styles.
    e.job_id  # set when a render was started (failed render, timeout)
```

The codes are listed in the [docs](https://docs.gepettoapp.com) (Errors). The SDK adds `timeout` and `connection_error`.

## Webhooks

To not wait for the image in the request, pass `webhook`: the call returns at once with the pending job, and Gepetto sends the finished job to your URL, signed.

```python
job = gepetto.furnish(url=photo_url, room_id="bedroom", style_id="modern", webhook="https://your-site.com/gepetto")
# job.status == "pending"
```

```python
from gepetto import verify_webhook

# In your webhook route (here Flask). The secret is read from GEPETTO_WEBHOOK_SECRET:
# it is webhook_secret of gepetto.account(), or `npx @gepetto/cli secret`
@app.post("/gepetto")
def gepetto_webhook():
    job = verify_webhook(request.get_data(), request.headers.get("Gepetto-Signature"))
    if job.is_success:
        ...  # job.output
    return "", 204
```

`verify_webhook` raises `invalid_signature` when the request does not come from Gepetto. Give it the raw body, before any JSON decoding.

## Jobs, account

```python
gepetto.get_job(job_id)        # a job, finished or not
gepetto.wait_for_job(job_id)   # waits for a job started with a webhook
gepetto.list_jobs(status="error", limit=10)
gepetto.account()              # key type, test renders used, webhook secret
gepetto.usage()                # consumption of the current period
```

## Options

```python
Gepetto(
    api_key="...",      # default: GEPETTO_API_KEY
    timeout=600,        # seconds a call waits for its image, retries included
    max_retries=2,      # after a network error, a 429 or a 5xx
    transport=my_send,  # your own HTTP layer: (method, url, headers, body, timeout) -> (status, body)
)
```

The calls are synchronous. In async code (FastAPI...), run them in a thread: `await asyncio.to_thread(gepetto.furnish, url=...)`.

Keep the key on your server: never in a web page or a mobile app.

## About Gepetto

Gepetto is the AI photo studio for real estate professionals. From a single photo, it furnishes an empty room, empties a cluttered one, restyles an interior, replaces a grey sky, repaints walls, changes floors, enhances the picture and animates the property on video, in seconds and with no technical skill. Launched in January 2023 in Bordeaux, France, Gepetto is used by more than 1,000 agencies, networks and real estate photographers, on the web, on iPhone and Android, and through this API inside real estate CRMs and platforms.

[gepettoapp.com](https://gepettoapp.com) · [API documentation](https://docs.gepettoapp.com) · [TypeScript SDK](https://github.com/Gepetto-AI/gepetto-sdk) · [PHP SDK](https://github.com/Gepetto-AI/gepetto-php) · [CLI](https://github.com/Gepetto-AI/gepetto-cli)

## Changes

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT
