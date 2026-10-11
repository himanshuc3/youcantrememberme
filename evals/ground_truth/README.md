# Ground truth for the spoiler-leak eval

One YAML file per show, hand-written (this is the only manual part of the project).
Each fact is something a recap must NOT reveal before `season`/`episode`, and optionally
something it SHOULD mention once that episode is covered.

```yaml
show: Severance
checkpoints: [[1, 3], [1, 9], [2, 5]]   # ranges are always evaluated from S1E1
facts:
  - season: 1
    episode: 9
    fact: "<short plain statement of the plot event>"
    must_include: false      # true = a good recap through this episode should mention it
```

Write facts from memory of the show, then double-check each against Wikipedia before relying
on it. A wrong "this happens in episode N" fact makes the eval lie.
