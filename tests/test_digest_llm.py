import pytest

from common.models import Episode, EpisodeDigest
from pipeline import digest
from pipeline.llm import BedrockLLM, DiskCachedLLM


class FakeLLM:
    """Records every prompt and replays canned replies."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str:
        self.calls.append((system, user))
        return self.replies.pop(0)


def ep(season, number, summary="Something happens."):
    return Episode(
        show_id=1, season=season, number=number, title=f"T{season}{number}", summary=summary
    )


def prior(n):
    return [EpisodeDigest(season=1, number=i, digest=f"digest {i}") for i in range(1, n + 1)]


def test_episode_digest_parses_json_and_spoiler_flag():
    llm = FakeLLM('{"digest": "Mark meets Helly.", "title_is_spoiler": true}')
    d = digest.llm_episode_digest(llm, "Severance", ep(1, 2), prior(1))
    assert d.digest == "Mark meets Helly."
    assert d.title_is_spoiler is True
    assert (d.season, d.number) == (1, 2)


def test_parses_fenced_json_and_retries_once_on_garbage():
    llm = FakeLLM("sorry, here you go", '```json\n{"digest": "Ok."}\n```')
    d = digest.llm_episode_digest(llm, "S", ep(1, 1), [])
    assert d.digest == "Ok."
    assert len(llm.calls) == 2


def test_gives_up_after_two_bad_replies():
    llm = FakeLLM("nope", '{"digest": ""}')
    with pytest.raises(digest.DigestError):
        digest.llm_episode_digest(llm, "S", ep(1, 1), [])


def test_prompt_contains_only_this_episode_and_recent_earlier_digests():
    # Spoiler safety by construction: later episodes must never reach the model.
    llm = FakeLLM('{"digest": "x"}')
    digest.llm_episode_digest(llm, "Show", ep(1, 5, "FIVE-SOURCE"), prior(4))
    _, user = llm.calls[0]
    assert "FIVE-SOURCE" in user
    assert "digest 4" in user and "digest 2" in user
    assert "digest 1" not in user  # only the last CONTEXT_EPISODES=3
    assert "episode 6" not in user.lower()


def test_no_source_text_means_no_llm_call():
    llm = FakeLLM()
    assert digest.llm_episode_digest(llm, "S", ep(1, 1, summary=""), []) is None
    assert llm.calls == []


def test_system_prompt_forbids_using_model_memory():
    assert "Use ONLY the text provided" in digest.EPISODE_SYSTEM
    assert "Use ONLY the text provided" in digest.SEASON_SYSTEM


def test_season_digest_records_episode_count_and_uses_only_given_digests():
    llm = FakeLLM('{"digest": "A season."}')
    sd = digest.llm_season_digest(llm, "Show", 2, prior(3))
    assert sd.episode_count == 3 and sd.season == 2
    assert "digest 3" in llm.calls[0][1]


def test_disk_cache_avoids_repeat_calls(tmp_path):
    inner = FakeLLM("first", "second")
    cached = DiskCachedLLM(inner, tmp_path)
    assert cached.complete("sys", "user") == "first"
    assert cached.complete("sys", "user") == "first"  # served from disk
    assert cached.complete("sys", "other") == "second"
    assert len(inner.calls) == 2


def test_bedrock_llm_request_shape_and_refusal_handling():
    class Block:
        type = "text"
        text = "hello"

    class Resp:
        def __init__(self, stop_reason):
            self.content = [Block()]
            self.stop_reason = stop_reason
            self.stop_details = None

    class Messages:
        def __init__(self):
            self.kwargs = None
            self.stop_reason = "end_turn"

        def create(self, **kwargs):
            self.kwargs = kwargs
            return Resp(self.stop_reason)

    class Client:
        def __init__(self):
            self.messages = Messages()

    client = Client()
    llm = BedrockLLM(client=client)
    assert llm.complete("sys", "user") == "hello"
    k = client.messages.kwargs
    assert k["model"] == "anthropic.claude-opus-5-5"
    assert k["system"] == "sys" and k["output_config"] == {"effort": "low"}
    assert "temperature" not in k  # sampling params are rejected by current models

    client.messages.stop_reason = "refusal"
    with pytest.raises(RuntimeError):
        llm.complete("sys", "user")
