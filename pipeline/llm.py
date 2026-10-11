"""Claude on Amazon Bedrock, for the offline pipeline only (the server never calls an LLM).

Uses the Messages-API Bedrock endpoint ("Claude in Amazon Bedrock") via
`anthropic.AnthropicBedrockMantle`, which serves Opus 4.7+ / Sonnet 5+ / Haiku 5.5 with
`anthropic.`-prefixed model IDs. (The older boto3 Converse / InvokeModel path is the legacy
integration for Opus 4.6 and earlier.)

Config via environment (nothing is hardcoded; no keys live in the repo):
  AWS_REGION            default us-east-1
  AWS_PROFILE / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
                        standard AWS credential chain, resolved by the SDK
  BEDROCK_MODEL_ID      default anthropic.claude-opus-5-5
  BEDROCK_EFFORT        default low (digests are short; deeper reasoning isn't needed)

Bedrock model access must be enabled for the model in the AWS console first.
Structured outputs are not supported on this endpoint, so callers ask for JSON in the
prompt and validate it themselves (see pipeline/digest.py).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Protocol

DEFAULT_MODEL = "anthropic.claude-opus-5-5"


class LLM(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str: ...


class BedrockLLM:
    def __init__(
        self,
        model: str | None = None,
        region: str | None = None,
        effort: str | None = None,
        client=None,
    ):
        self.model = model or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("BEDROCK_EFFORT", "low")
        if client is None:
            from anthropic import AnthropicBedrockMantle  # needs `anthropic[bedrock]`

            client = AnthropicBedrockMantle(
                aws_region=region or os.environ.get("AWS_REGION", "us-east-1")
            )
        self.client = client

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str:
        # max_tokens leaves room for adaptive thinking, which counts toward the limit.
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            output_config={"effort": self.effort},
            messages=[{"role": "user", "content": user}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused the request: {resp.stop_details}")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("response hit max_tokens before finishing; raise max_tokens")
        return next((b.text for b in resp.content if b.type == "text"), "")


class DiskCachedLLM:
    """Wraps any LLM; identical (model, system, user) calls are answered from disk.

    Makes pipeline reruns free and resumable after a crash or a rate-limit stop.
    """

    def __init__(self, inner: LLM, cache_dir: str | Path):
        self.inner = inner
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str:
        model = getattr(self.inner, "model", "")
        key = hashlib.sha256(json.dumps([model, system, user]).encode()).hexdigest()
        path = self.dir / f"{key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        text = self.inner.complete(system, user, max_tokens)
        path.write_text(text, encoding="utf-8")
        return text
