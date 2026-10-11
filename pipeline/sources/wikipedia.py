"""Wikipedia episode plot summaries (CC BY-SA). STUB.

Why: TVmaze summaries are 1-2 sentences; Wikipedia "List of <show> episodes" tables have a
fuller plot paragraph per episode, which makes much better recaps.

TODO (needs a network that isn't rate-limited; this container's shared IP was blocked):
  * resolve the "List of ... episodes" page for a show (MediaWiki search API)
  * parse each season table's "Episode N" rows -> plot summary (action=parse / wikitext)
  * return {(season, number): plot_text} to merge into `Episode.extra_text`
  * send a descriptive User-Agent with contact info, per Wikimedia API etiquette
"""

from __future__ import annotations

USER_AGENT = "youcantrememberme-hackathon/0.1 (contact: himichhabra14@gmail.com)"


def fetch_plot_summaries(show_name: str) -> dict[tuple[int, int], str]:
    raise NotImplementedError("Wikipedia source not implemented yet")
