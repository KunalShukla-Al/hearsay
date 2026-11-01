"""The live route to Muse Glimmer.

`GlimmerExtractor` (model.py) holds the model behind one callable,
`call_model(prompt) -> text`; this module builds that callable for a real
endpoint. Glimmer is served the same way whether it runs as a free GGUF on
Kaggle's 2xT4 (llama.cpp's OpenAI-compatible server) or hosted on Baseten: an
OpenAI-style POST to `/chat/completions`. So the route is one HTTP call, and
only three environment values change between the two:

  GLIMMER_BASE_URL   e.g. https://<kaggle-tunnel>/v1  or  https://...baseten.../v1
  GLIMMER_MODEL      the served model name
  GLIMMER_API_KEY    the bearer token (blank for a local Kaggle server)

Nothing downstream learns which route is live. A bare `run.py` still uses the
stub, so no endpoint or key is needed to run the pipeline on the fixture.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping

# A transport turns a prepared request into the raw response text. The default
# uses urllib; a test injects a fake so the route is checked with no network.
Transport = Callable[[str, dict], bytes]

DEFAULT_TIMEOUT = 60


class RouteError(RuntimeError):
    """The route isn't configured, or the endpoint didn't answer."""


@dataclass(frozen=True)
class RouteConfig:
    base_url: str
    model: str
    api_key: str = ""
    timeout: int = DEFAULT_TIMEOUT

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RouteConfig":
        env = os.environ if env is None else env
        base = (env.get("GLIMMER_BASE_URL") or "").rstrip("/")
        model = env.get("GLIMMER_MODEL") or ""
        if not base or not model:
            raise RouteError(
                "set GLIMMER_BASE_URL and GLIMMER_MODEL for the Glimmer route "
                "(or run with the stub, which is the default)")
        return cls(base_url=base, model=model, api_key=env.get("GLIMMER_API_KEY", ""))


def _urllib_transport(url: str, request: dict) -> bytes:
    req = urllib.request.Request(
        url, data=request["body"], headers=request["headers"], method="POST")
    try:
        with urllib.request.urlopen(req, timeout=request["timeout"]) as resp:
            return resp.read()
    except urllib.error.URLError as e:
        raise RouteError(f"Glimmer endpoint didn't answer: {e.reason}") from e


def glimmer_route(config: RouteConfig | None = None,
                  transport: Transport | None = None) -> Callable[[str], str]:
    """A `call_model(prompt) -> text` over the configured endpoint, ready to
    pass to `GlimmerExtractor`. `transport` is injected in tests."""

    cfg = config or RouteConfig.from_env()
    send = transport or _urllib_transport

    def call_model(prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        body = json.dumps({
            "model": cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,            # the eval needs the same reply each run
        }).encode("utf-8")
        raw = send(f"{cfg.base_url}/chat/completions",
                   {"headers": headers, "body": body, "timeout": cfg.timeout})
        return _content(raw)

    return call_model


def _content(raw: bytes) -> str:
    """The assistant text out of an OpenAI-style reply; "" when it isn't there,
    so a junk reply drops the message in GlimmerExtractor instead of raising."""

    try:
        data = json.loads(raw)
        return data["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        return ""
