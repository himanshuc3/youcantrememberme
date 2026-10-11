# Using Claude on Amazon Bedrock for the digest pipeline

Used only by the offline pipeline (`pipeline/llm.py`). The MCP server never calls an LLM.

## Setup (you, once)
1. In the AWS console go to **Amazon Bedrock → Model access** and enable the Claude model
   you want. Opus 5.5, Sonnet 5.5 and Haiku 5.5 are marked "See Access" in the docs, so
   they may need a request. Sonnet 5 and Opus 4.8 are listed as open.
2. Credentials: use a normal AWS profile or environment variables (the SDK reads the usual
   chain). No key goes in the repo. Any `.env` file is git-ignored.
3. Install: `pip install -e ".[pipeline]"` (pulls `anthropic[bedrock]`).

```bash
export AWS_PROFILE=<your profile>        # or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
export AWS_REGION=us-east-1
# optional:
export BEDROCK_MODEL_ID=anthropic.claude-opus-5-5   # default
export BEDROCK_EFFORT=low                           # default

python -m pipeline.run --mode llm "Severance"
```

## How it is called
- Client: `anthropic.AnthropicBedrockMantle(aws_region=...)`, the Messages-API endpoint for
  Opus 4.7+ / Sonnet 5+ / Haiku 5.5. Model IDs carry an `anthropic.` prefix. The old boto3
  `Converse` / `InvokeModel` route is the legacy path for Opus 4.6 and earlier.
- Structured output is not supported on this endpoint, so the prompt asks for a JSON
  object and `pipeline/digest.py` validates it, with one retry.
- Prompt caching isn't used: our prompts are short (below the minimum cacheable size).
  Reruns are made free by an on-disk reply cache instead (`data/cache/llm/`).
- A `refusal` or `max_tokens` stop raises an error instead of saving a bad digest.

## Cost
One short call per episode plus one per season. A 50-episode show is on the order of a
few cents to a dollar depending on the model. Check the Bedrock pricing page.

## What is NOT verified
No live call has been made from this repo yet: the tests use a fake client. The first real
run may reveal an access or parameter error (for example if `output_config.effort` is
rejected for your model or region). Try `BEDROCK_MODEL_ID=anthropic.claude-sonnet-5` if
Opus 5.5 access is pending.

## For the AWS Builder mini-challenge
It needs a **documented** AWS integration. This file plus the "AWS service(s) used" answer
in the Devpost Product Feedback is where that goes.
