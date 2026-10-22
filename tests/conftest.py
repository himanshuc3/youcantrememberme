import pytest

from common.backend import DynamoBackend
from common.models import EpisodeDigest, SeasonDigest, Show, ShowData
from common.store import ShowStore


@pytest.fixture
def dynamo(monkeypatch):
    """Empty DynamoDB tables, in memory (moto): no Docker, no network, nothing to clean up."""
    moto = pytest.importorskip("moto")
    import boto3

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    with moto.mock_aws():
        backend = DynamoBackend(resource=boto3.resource("dynamodb", region_name="us-east-1"))
        backend.ensure_tables()
        yield backend


@pytest.fixture
def shows(tmp_path, dynamo):
    """A ShowStore (in-memory DynamoDB) holding one 2-season show ("The Test Show")."""
    sizes = {1: 3, 2: 3}
    data = ShowData(
        show=Show(id=7, name="The Test Show", season_sizes=sizes),
        episodes=[
            EpisodeDigest(season=s, number=n, digest=f"S{s}E{n} happens.")
            for s, size in sizes.items()
            for n in range(1, size + 1)
        ],
        seasons=[
            SeasonDigest(season=s, digest=f"SEASON{s} summary.", episode_count=size)
            for s, size in sizes.items()
        ],
    )
    store = ShowStore(tmp_path, backend=dynamo)
    store.save(data)
    return store


# Settings that change behaviour and could be set in a developer's shell (for the Bedrock
# pipeline, the demo script, a tunnel...). Tests must not depend on them.
_ENV_THAT_AFFECTS_BEHAVIOUR = [
    "ALLOWED_HOSTS",
    "DATA_DIR",
    "DYNAMODB_TABLE_PREFIX",
    "DYNAMODB_ENDPOINT_URL",
    "MCP_URL",
    "BEDROCK_MODEL_ID",
    "BEDROCK_EFFORT",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_PROFILE",
    "ON_DEMAND",
    "WEB_DEMO_LLM",
    "WEB_DEMO_MODEL_ID",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "AWS_BEARER_TOKEN_BEDROCK",
    "ON_DEMAND_DAILY_LIMIT",
]


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    for name in _ENV_THAT_AFFECTS_BEHAVIOUR:
        monkeypatch.delenv(name, raising=False)
