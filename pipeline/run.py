"""Pipeline CLI.

    python -m pipeline.run --mode baseline "Severance" "The Bear"
    python -m pipeline.run --mode baseline            # uses pipeline/shows.yaml
    python -m pipeline.run --mode llm ...             # not implemented yet

Raw source text is cached under data/cache/ (git-ignored); digests land in data/shows/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from common.models import ShowData
from common.store import ShowStore
from pipeline import digest
from pipeline.season import build_season_digests
from pipeline.sources import tvmaze

SHOWS_YAML = Path(__file__).with_name("shows.yaml")


def process_show(name: str, mode: str, store: ShowStore) -> ShowData:
    show, episodes = tvmaze.fetch_show_and_episodes(name)
    cache = store.root / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / f"{show.id}.json").write_text(
        json.dumps([e.model_dump() for e in episodes], indent=1), encoding="utf-8"
    )

    ep_digests = []
    if mode == "baseline":
        for ep in sorted(episodes, key=lambda e: e.pos):
            d = digest.baseline_episode_digest(ep)
            if d:
                ep_digests.append(d)
        season_make = digest.baseline_season_digest
    else:
        prior = []
        for ep in sorted(episodes, key=lambda e: e.pos):
            d = digest.llm_episode_digest(ep, prior)
            ep_digests.append(d)
            prior.append(d)
        season_make = digest.llm_season_digest

    data = ShowData(
        show=show,
        episodes=ep_digests,
        seasons=build_season_digests(show, ep_digests, season_make),
    )
    store.save(data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("shows", nargs="*", help="show names; default: pipeline/shows.yaml")
    parser.add_argument("--mode", choices=["baseline", "llm"], default="baseline")
    args = parser.parse_args()

    names = args.shows or yaml.safe_load(SHOWS_YAML.read_text())["shows"]
    store = ShowStore()
    for name in names:
        data = process_show(name, args.mode, store)
        print(
            f"{data.show.name}: {len(data.episodes)} episode digests, "
            f"{len(data.seasons)} season digests"
        )


if __name__ == "__main__":
    main()
