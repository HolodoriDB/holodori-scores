from __future__ import annotations

import bisect
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


def _note_list(score: Score, timeline: _Timeline) -> list[tuple[str, float]]:
    # every note as (type, time_seconds), time-ordered - the single source of truth for
    # scoring. critical variants keep a "critical_" prefix; they share the base weight.
    return sorted(
        (
            (("critical_" if crit else "") + cat, timeline.time(beat))
            for cat, crit, beat in score.combo_events()
        ),
        key=lambda n: n[1],
    )


def chart_metadata(
    score: Score, bar_lengths: list[tuple[int, float]]
) -> dict[str, Any]:
    # note list (type + time) + skill fire times drive the calculation; counts/combo are all
    # derivable from these, so nothing is precomputed. two notes on the same tick no longer
    # confuse combo-based windows, since scoring keys off exact per-note times.
    timeline = _timeline(score, bar_lengths)
    notes = _note_list(score, timeline)
    combo_beats = sorted(beat for _cat, _crit, beat in score.combo_events())

    skills = [
        {
            "skill_slot_no": note.slot,
            "time": round(timeline.time(note.beat), 6),
            # display only; may shift by a note when several land on the same beat
            "skill_starts_at_combo": bisect.bisect_left(combo_beats, note.beat),
        }
        for note in score.notes
        if type(note).__name__ == "HolodoriSkill"
    ]

    return {"notes": [[typ, round(t, 6)] for typ, t in notes], "skills": skills}


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
    # main meta file: built from the same time-ordered note list as the per-chart metadata,
    # so combo (per-note, sequential) and skill windows (by time) are tie-safe.
    timeline = _timeline(score, bar_lengths)
    notes = _note_list(score, timeline)
    skill_times = sorted(
        timeline.time(n.beat)
        for n in score.notes
        if type(n).__name__ == "HolodoriSkill"
    )
    thresholds = sorted(combo_curve)
    fever = _fever_window(score)
    fever_times = (timeline.time(fever[0]), timeline.time(fever[1])) if fever else None

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

    total = weighted = weighted_fever = 0.0
    for combo, (typ, t) in enumerate(notes, start=1):
        base = typ[9:] if typ.startswith("critical_") else typ
        w = weights.get(base, 0) / 1000
        factor = 1 + combo_bonus(combo)
        if in_skill(t):
            factor *= skill_multiplier
        contrib = w * factor
        total += w
        weighted += contrib
        if fever_times is not None and fever_times[0] <= t < fever_times[1]:
            weighted_fever += contrib
    solo = weighted / total if total else 0.0
    fever_share = weighted_fever / total if total else 0.0
    multi = solo + (1 + fever_bonus) * multi_bonus * fever_share
    return {"solo": solo, "multi": multi}
