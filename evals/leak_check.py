"""Spoiler-leak eval. STUB (needs the LLM provider decision).

Plan:
  for each show in evals/ground_truth/*.yaml:
    for each checkpoint (season, episode) in the file:
      recap = assemble_recap(show_data, (1, 1), checkpoint)
      for every ground-truth fact whose (season, episode) is AFTER the checkpoint:
        ask an LLM judge: "Does this recap state or clearly imply: <fact>?"  -> leak if yes
      for every fact AT or BEFORE the checkpoint marked `must_include: true`:
        ask the judge the same question -> missed-key-event if no
  Report leaks (must be 0), and recall of key events (nice to have).

The judge sees only the recap and one fact at a time, with a yes/no JSON answer.
"""

from __future__ import annotations


def run() -> int:
    raise NotImplementedError("leak_check not implemented yet")
