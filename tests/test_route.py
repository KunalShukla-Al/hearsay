"""Day 8: the live route to Glimmer, checked with no network.

`glimmer_route` builds the `call_model` that `GlimmerExtractor` holds. A fake
transport stands in for the HTTP call, so the route's request shape and its
reading of an OpenAI-style reply are proven offline, and the whole route +
extractor swap is exercised end to end.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hearsay.model import GlimmerExtractor          # noqa: E402
from hearsay.route import RouteConfig, RouteError, glimmer_route  # noqa: E402
from hearsay.schema import Message, Trust            # noqa: E402

CFG = RouteConfig(base_url="https://glimmer.test/v1", model="muse-glimmer", api_key="k")


def _reply(content: str) -> bytes:
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()


def test_route_sends_an_openai_request_and_reads_the_content():
    seen = {}

    def transport(url, request):
        seen["url"] = url
        seen["request"] = request
        return _reply("hello")

    call = glimmer_route(CFG, transport=transport)
    assert call("a prompt") == "hello"
    assert seen["url"] == "https://glimmer.test/v1/chat/completions"
    assert seen["request"]["headers"]["Authorization"] == "Bearer k"
    body = json.loads(seen["request"]["body"])
    assert body["model"] == "muse-glimmer"
    assert body["messages"][0]["content"] == "a prompt"
    assert body["temperature"] == 0


def test_route_feeds_glimmer_end_to_end():
    # The route's reply is what GlimmerExtractor parses into a Claim.
    def transport(_url, _request):
        return _reply('[{"kind":"exam","subject":"OS","date":"2026-10-29","confidence":0.9}]')

    msg = Message(id=1, group="OS", sender="FACULTY-OS",
                  ts=datetime(2026, 10, 20, tzinfo=timezone.utc), text="OS exam on the 29th", is_from_me=False)
    claims = GlimmerExtractor(glimmer_route(CFG, transport=transport)).extract([msg])
    assert len(claims) == 1
    assert claims[0].subject == "OS" and claims[0].date == "2026-10-29"
    assert claims[0].trust is Trust.FACULTY        # trust still comes from the sender


def test_route_drops_a_junk_reply_without_raising():
    call = glimmer_route(CFG, transport=lambda _u, _r: b"not json at all")
    assert call("p") == ""                         # GlimmerExtractor then emits no claim


def test_route_omits_the_auth_header_without_a_key():
    seen = {}

    def transport(_url, request):
        seen["headers"] = request["headers"]
        return _reply("ok")

    glimmer_route(RouteConfig(base_url="http://localhost:8080/v1", model="g"), transport=transport)("p")
    assert "Authorization" not in seen["headers"]


def test_route_needs_configuration():
    try:
        RouteConfig.from_env({})
    except RouteError:
        pass
    else:
        raise AssertionError("expected RouteError without GLIMMER_BASE_URL / GLIMMER_MODEL")
    cfg = RouteConfig.from_env({"GLIMMER_BASE_URL": "https://x/v1/", "GLIMMER_MODEL": "g"})
    assert cfg.base_url == "https://x/v1" and cfg.api_key == ""   # trailing slash trimmed


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
