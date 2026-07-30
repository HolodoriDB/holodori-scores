from __future__ import annotations

from typing import Any

from sonolus_converters.notes.score import Score

from .render import _Timeline

_CATS = (
    "taps",
    "flicks",
    "long_starts",
    "long_ends",
    "long_flick_ends",
    "long_relays",
    "long_continuations",
)
_KEYS = tuple(k for c in _CATS for k in (c, "critical_" + c))
_SKILL_BUCKETS = range(5, 16)

_Event = tuple[str, bool, float]


def _tally(
    events: list[_Event],
    *,
    beat_window: tuple[float, float] | None = None,
    sec_window: tuple[float, float] | None = None,
    timeline: _Timeline | None = None,
) -> dict[str, int]:
    counts = {k: 0 for k in _KEYS}
    for cat, crit, beat in events:
        if beat_window is not None and not (beat_window[0] <= beat < beat_window[1]):
            continue
        if sec_window is not None and timeline is not None:
            t = timeline.time(beat)
            if not (sec_window[0] <= t < sec_window[1]):
                continue
        counts[("critical_" if crit else "") + cat] += 1
    return counts


def _timeline(score: Score, bar_lengths: list[tuple[int, float]]) -> _Timeline:
    bpms = [(n.beat, n.bpm) for n in score.notes if type(n).__name__ == "Bpm"]
    return _Timeline(bpms, bar_lengths)


def _fever_window(score: Score) -> tuple[float, float] | None:
    fs = next(
        (n.beat for n in score.notes if type(n).__name__ == "HolodoriFeverStart"), None
    )
    fe = next(
        (n.beat for n in score.notes if type(n).__name__ == "HolodoriFeverEnd"), None
    )
    return (fs, fe) if fs is not None and fe is not None else None


def chart_metadata(
    score: Score, bar_lengths: list[tuple[int, float]]
) -> dict[str, Any]:
    timeline = _timeline(score, bar_lengths)
    events: list[_Event] = list(score.combo_events())

    counts = _tally(events)
    fever_window = _fever_window(score)
    fever = (
        _tally(events, beat_window=fever_window)
        if fever_window
        else {k: 0 for k in _KEYS}
    )

    skills = []
    for note in score.notes:
        if type(note).__name__ != "HolodoriSkill":
            continue
        start = timeline.time(note.beat)
        buckets = {
            str(k): _tally(events, sec_window=(start, start + k), timeline=timeline)
            for k in _SKILL_BUCKETS
        }
        skills.append({"skill_slot_no": note.slot, "counts": buckets})

    return {**counts, "fever": fever, "skills": skills}


def notes_coefficient(counts: dict[str, int], weights: dict[str, int]) -> float:
    permil = sum(
        weights.get(c, 0) * (counts.get(c, 0) + counts.get("critical_" + c, 0))
        for c in _CATS
    )
    return permil / 1000


def chart_score_multipliers(
    score: Score,
    bar_lengths: list[tuple[int, float]],
    *,
    combo_curve: list[tuple[int, int]],
    weights: dict[str, int],
    fever_bonus: float,
    multi_bonus: float,
    skill_seconds: float = 9.0,
    skill_multiplier: float = 2.0,
) -> dict[str, float]:
    timeline = _timeline(score, bar_lengths)
    events = sorted(score.combo_events(), key=lambda e: e[2])
    skill_times = sorted(
        timeline.time(n.beat)
        for n in score.notes
        if type(n).__name__ == "HolodoriSkill"
    )
    thresholds = sorted(combo_curve)

    def combo_bonus(combo: int) -> float:
        permil = 0
        for combo_from, up in thresholds:
            if combo >= combo_from:
                permil = up
            else:
                break
        return permil / 1000

    def in_skill(t: float) -> bool:
        return any(st <= t < st + skill_seconds for st in skill_times)

    total = weighted = 0.0
    for combo, (cat, _crit, beat) in enumerate(events, start=1):
        w = weights.get(cat, 0) / 1000
        factor = 1 + combo_bonus(combo)
        if in_skill(timeline.time(beat)):
            factor *= skill_multiplier
        total += w
        weighted += w * factor
    solo = weighted / total if total else 0.0
    multi_factor = multi_bonus * (
        1 + fever_bonus if _fever_window(score) is not None else 1
    )
    return {"solo": solo, "multi": solo * multi_factor}
