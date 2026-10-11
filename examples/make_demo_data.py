"""Generate the offline demo dataset: examples/demo-data/shows/9001.json.

"The Lighthouse Keepers" is a FICTIONAL show written for this project, so the demo and the
tests need no network, no API key, and no third-party titles or trademarks.

It has a deliberate twist (the radio voice is Mara's father, revealed in S1E5) so that
spoiler safety is easy to see: a recap "through season 1 episode 3" must not mention the
father, while a recap through the end of season 1 should.

    python examples/make_demo_data.py
"""

from __future__ import annotations

from pathlib import Path

from common.models import EpisodeDigest, SeasonDigest, Show, ShowData
from common.store import ShowStore

EPISODES = {
    (1, 1): "Mara Voss arrives at the Gull Rock lighthouse to replace the keeper who "
    "vanished. The lamp still works, but the logbook has pages torn out.",
    (1, 2): "A storm traps Mara and the supply boat captain, Teo Marsh, on the rock. "
    "They find the missing keeper's coat in the cellar.",
    (1, 3): "A faint radio voice reads out coordinates at midnight. Teo insists the signal "
    "is impossible because the transmitter was removed years ago.",
    (1, 4): "Mara and Teo follow the coordinates to a sealed tidal cave holding the missing "
    "keeper's notebook, which says the lamp must never go dark.",
    (1, 5): "Mara plays an old recording and recognises the radio voice as her father, who "
    "was reported lost at sea twenty years ago. Then the lamp goes dark and the voice "
    "falls silent.",
    (2, 1): "Mara refuses to leave the rock and keeps the lamp burning night and day, "
    "hoping to hear her father again. Teo brings supplies and a new radio.",
    (2, 2): "A coast guard officer arrives asking about the missing keeper and the "
    "coordinates. Mara lies and says the logbook was lost.",
    (2, 3): "Teo confesses that he removed the old transmitter himself, to stop her "
    "father's signal. He will not say why.",
    (2, 4): "Mara finds a second cave with a working transmitter powered by the lamp. Her "
    "father answers, but the line cuts out when the coast guard boat docks.",
}

SEASONS = {
    1: "Mara Voss takes over the Gull Rock lighthouse after the last keeper vanishes. With "
    "boat captain Teo Marsh she follows a mysterious radio signal to a hidden cave, and "
    "learns the voice on the radio is her father, long believed dead.",
    2: "Mara stays on the rock to keep the lamp burning and to reach her father. Teo "
    "confesses he silenced the old transmitter, and a coast guard officer closes in just "
    "as Mara finds a hidden transmitter that lets her speak to her father.",
}


def build() -> ShowData:
    sizes: dict[int, int] = {}
    for season, _ in EPISODES:
        sizes[season] = sizes.get(season, 0) + 1
    return ShowData(
        show=Show(
            id=9001,
            name="The Lighthouse Keepers",
            aliases=["Lighthouse Keepers", "Keepers"],
            premiered="2026-01-01",
            season_sizes=sizes,
        ),
        episodes=[
            EpisodeDigest(season=s, number=n, digest=text)
            for (s, n), text in sorted(EPISODES.items())
        ],
        seasons=[
            SeasonDigest(season=s, digest=text, episode_count=sizes[s])
            for s, text in SEASONS.items()
        ],
        attribution=["Demo data: fictional, written for this project (MIT)."],
    )


if __name__ == "__main__":
    out = ShowStore(Path(__file__).parent / "demo-data").save(build())
    print(f"wrote {out}")
