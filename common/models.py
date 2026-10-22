"""Data models shared by the pipeline (writes them) and the server (reads them).

Spoiler-safety invariants live in these shapes:

* An `EpisodeDigest` is generated from that one episode's source text (plus earlier
  digests for context) and must never mention later events.
* A `SeasonDigest` is generated from the digests of *that season's* episodes only, and
  records `episode_count` so the server can refuse to use it for a partial season.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# (season, episode number). Tuples compare in watch order.
Pos = tuple[int, int]

TVMAZE_ATTRIBUTION = "Episode data: TVmaze (CC BY-SA 4.0), https://www.tvmaze.com"


class Show(BaseModel):
    id: int  # TVmaze show id
    name: str
    aliases: list[str] = Field(default_factory=list)
    premiered: str | None = None
    season_sizes: dict[int, int] = Field(default_factory=dict)  # season -> episode count


class Episode(BaseModel):
    """Raw source record. Pipeline-internal; never served to users."""

    show_id: int
    season: int
    number: int
    title: str
    airdate: str | None = None
    summary: str = ""  # plain text, HTML stripped
    extra_text: str = ""  # e.g. Wikipedia plot summary, when available

    @property
    def pos(self) -> Pos:
        return (self.season, self.number)


class EpisodeDigest(BaseModel):
    season: int
    number: int
    digest: str  # short, speakable, spoiler-safe up to and including this episode
    title: str | None = None
    title_is_spoiler: bool = False  # e.g. "The Death of X": never read the title aloud

    @property
    def pos(self) -> Pos:
        return (self.season, self.number)


class SeasonDigest(BaseModel):
    season: int
    digest: str
    episode_count: int  # number of episodes this digest was built from


class CastMember(BaseModel):
    character: str
    actor: str | None = None


class ShowData(BaseModel):
    """Everything the server needs for one show, stored as one DynamoDB item."""

    show: Show
    # The WHOLE cast, so listing it as-is would leak characters introduced later. The server
    # only ever shows characters whose names already appear in digests up to the user's
    # position (server/characters.py).
    cast: list[CastMember] = Field(default_factory=list)
    episodes: list[EpisodeDigest] = Field(default_factory=list)
    seasons: list[SeasonDigest] = Field(default_factory=list)
    attribution: list[str] = Field(default_factory=lambda: [TVMAZE_ATTRIBUTION])


class Recap(BaseModel):
    show: str
    text: str  # what Alexa should say
    starts_at: str  # e.g. "season 1, episode 1"
    covered_through: str  # last episode actually included; never later than requested
    truncated: bool = False  # True if the oldest events were dropped to fit speech length
    attribution: list[str] = Field(default_factory=list)


def fmt_pos(pos: Pos) -> str:
    return f"season {pos[0]}, episode {pos[1]}"
