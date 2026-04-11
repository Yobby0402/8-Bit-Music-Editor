"""
Seed 轨道构建 helper。

集中承接低音、和声、鼓点轨道的生成逻辑，
让 `seed_music_generator` 更聚焦于主旋律与整体装配流程。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .models import Note, Track, TrackType
from .seed_generation_planner import PhrasePlan, chord_root_degree
from .seed_style_catalog import SeedMusicStyle, StyleParams
from .seed_style_configs import MusicStyleConfig


@dataclass(frozen=True)
class TrackBuildContext:
    """描述非主旋律轨道构建所需的共享上下文。"""

    rng: random.Random
    style: SeedMusicStyle
    variant_id: str
    style_params: StyleParams
    style_config: MusicStyleConfig
    phrase_plan: PhrasePlan
    length_bars: int
    beats_per_bar: float
    beat_duration: float
    bars_progression: tuple[int, ...]
    root_midi: int
    scale_offsets: tuple[int, ...]
    quiet_bars: frozenset[int]
    dance_harmony_start_bar: int = 0


def build_bass_track(context: TrackBuildContext, *, enable_bass: bool) -> Track | None:
    """根据上下文构建低音轨道。"""

    if not enable_bass:
        return None

    bass_track = Track(name="Seed 低音", track_type=TrackType.NOTE_TRACK)
    bass_adsr = context.style_params.bass_adsr

    for bar_idx in range(context.length_bars):
        bar_start = bar_idx * context.beats_per_bar
        bar_chord_degree = context.bars_progression[bar_idx]
        bar_root_degree = chord_root_degree(bar_chord_degree)

        phrase_role = None
        if bar_idx >= context.phrase_plan.intro_bars:
            phrase_idx = context.phrase_plan.phrase_index_at_bar(bar_idx)
            phrase_role = context.phrase_plan.phrase_role(phrase_idx)

            if context.style == SeedMusicStyle.ROCK and phrase_role == "variation":
                if bar_idx % 2 == 0:
                    bass_root_pitch = context.root_midi - 12 + context.scale_offsets[bar_root_degree]
                    start_time = bar_start * context.beat_duration
                    duration = 1.0 * context.beat_duration
                    note = Note(
                        pitch=bass_root_pitch,
                        start_time=start_time,
                        duration=duration,
                        velocity=70,
                        waveform=context.style_params.bass_waveform,
                        duty_cycle=context.style_params.bass_duty,
                        adsr=bass_adsr,
                    )
                    bass_track.notes.append(note)
                continue

        if context.style == SeedMusicStyle.SUSPENSE and bar_idx in context.quiet_bars:
            continue

        if context.style == SeedMusicStyle.SUSPENSE:
            bass_degree = 0 if (bar_idx % 2 == 0) else 3
            bass_root_pitch = context.root_midi - 12 + context.scale_offsets[
                max(0, min(bass_degree, len(context.scale_offsets) - 1))
            ]
        else:
            bass_root_pitch = context.root_midi - 12 + context.scale_offsets[bar_root_degree]

        bass_pattern = context.style_config.get_bass_pattern(
            context.rng,
            bar_idx,
            bar_root_degree,
            context.root_midi,
            list(context.scale_offsets),
            context.beats_per_bar,
            context.beat_duration,
            context.variant_id,
        )

        for start_beat, dur_beats, base_velocity in bass_pattern:
            start_time = (bar_start + start_beat) * context.beat_duration
            is_strong_beat = abs(start_beat - 0.0) < 1e-6 or abs(start_beat - 2.0) < 1e-6

            if context.style == SeedMusicStyle.BATTLE:
                duration_beats_for_time = max(0.25, dur_beats * 0.7)
            elif context.style == SeedMusicStyle.SUSPENSE:
                duration_beats_for_time = max(0.5, dur_beats * 0.7)
            elif context.style == SeedMusicStyle.ROCK:
                if dur_beats >= context.beats_per_bar:
                    duration_beats_for_time = dur_beats
                else:
                    duration_beats_for_time = dur_beats * 1.1
            elif context.style == SeedMusicStyle.CALM:
                duration_beats_for_time = dur_beats * 1.1
            else:
                duration_beats_for_time = dur_beats

            duration = duration_beats_for_time * context.beat_duration
            will_add_octave = is_strong_beat and context.rng.random() < 0.3

            if will_add_octave:
                bass_velocity = max(70, int(base_velocity * 0.75))
            else:
                bass_velocity = base_velocity

            note = Note(
                pitch=bass_root_pitch,
                start_time=start_time,
                duration=duration,
                velocity=bass_velocity,
                waveform=context.style_params.bass_waveform,
                duty_cycle=context.style_params.bass_duty,
                adsr=bass_adsr,
            )
            bass_track.notes.append(note)

            if will_add_octave:
                octave_choice = context.rng.choice(["lower", "higher"])
                if octave_choice == "lower":
                    overlay_pitch = bass_root_pitch - 12
                else:
                    overlay_pitch = bass_root_pitch + 12

                overlay_pitch = max(24, min(overlay_pitch, 96))
                overlay_velocity = max(60, int(base_velocity * 0.45))

                overlay_note = Note(
                    pitch=overlay_pitch,
                    start_time=start_time,
                    duration=duration * 0.9,
                    velocity=overlay_velocity,
                    waveform=context.style_params.bass_waveform,
                    duty_cycle=context.style_params.bass_duty,
                    adsr=bass_adsr,
                )
                bass_track.notes.append(overlay_note)

    return bass_track


def build_harmony_track(context: TrackBuildContext, *, enable_harmony: bool) -> Track | None:
    """根据上下文构建和声轨道。"""

    if not enable_harmony:
        return None

    harmony_track = Track(name="Seed 和声", track_type=TrackType.NOTE_TRACK)
    harmony_adsr = context.style_params.harmony_adsr

    for bar_idx in range(context.length_bars):
        bar_start = bar_idx * context.beats_per_bar
        bar_chord_degree = context.bars_progression[bar_idx]
        bar_root_degree = chord_root_degree(bar_chord_degree)

        phrase_role = None
        if bar_idx >= context.phrase_plan.intro_bars:
            phrase_idx = context.phrase_plan.phrase_index_at_bar(bar_idx)
            phrase_role = context.phrase_plan.phrase_role(phrase_idx)

        chord_degrees = context.style_config.get_harmony_chord_degrees(
            context.rng,
            bar_root_degree,
            bar_idx,
            phrase_role or "statement",
            context.variant_id,
            list(context.scale_offsets),
        )

        if context.style == SeedMusicStyle.DANCE and bar_idx < context.dance_harmony_start_bar:
            continue

        is_solo_section = False
        if bar_idx < context.phrase_plan.intro_bars:
            if context.style == SeedMusicStyle.DANCE:
                harmony_beats = [0.0, 1.0, 2.0, 3.0]
                harmony_duration_beats = 1.0
            else:
                harmony_beats = [0.0]
                harmony_duration_beats = 2.0
        else:
            phrase_idx = context.phrase_plan.phrase_index_at_bar(bar_idx)
            phrase_role = context.phrase_plan.phrase_role(phrase_idx)

            if context.style == SeedMusicStyle.DANCE:
                harmony_beats = [0.0, 1.0, 2.0, 3.0]
                harmony_duration_beats = 1.0
            elif phrase_role == "statement":
                harmony_beats = [0.0]
                harmony_duration_beats = 2.0
            elif phrase_role == "development":
                harmony_beats = [0.0]
                harmony_duration_beats = 3.0
            elif phrase_role == "variation":
                harmony_beats = [0.0]
                harmony_duration_beats = context.beats_per_bar
                is_solo_section = context.style == SeedMusicStyle.ROCK
            elif phrase_role == "resolution":
                harmony_beats = [0.0]
                harmony_duration_beats = 3.0
            else:
                harmony_beats = [0.0]
                harmony_duration_beats = 2.5 if phrase_role == "question" else 3.0

        if context.style == SeedMusicStyle.SUSPENSE and bar_idx in context.quiet_bars:
            degree = chord_degrees[0]
            pitch = context.root_midi - 12 + context.scale_offsets[degree]
            harmony_track.notes.append(
                Note(
                    pitch=pitch,
                    start_time=bar_start * context.beat_duration,
                    duration=context.beats_per_bar * context.beat_duration,
                    velocity=50,
                    waveform=context.style_params.harmony_waveform,
                    duty_cycle=context.style_params.harmony_duty,
                    adsr=harmony_adsr,
                )
            )
            continue

        for harmony_beat in harmony_beats:
            start_time = (bar_start + harmony_beat) * context.beat_duration
            duration = harmony_duration_beats * context.beat_duration

            if context.style == SeedMusicStyle.DANCE:
                base_harmony_velocity = 60
            else:
                base_harmony_velocity = 80

            for degree in chord_degrees:
                pitch = context.root_midi - 12 + context.scale_offsets[degree]
                if context.style == SeedMusicStyle.DANCE:
                    harmony_velocity = base_harmony_velocity
                elif context.style == SeedMusicStyle.SUSPENSE:
                    harmony_velocity = 55
                elif context.style == SeedMusicStyle.ROCK:
                    if is_solo_section:
                        harmony_velocity = 45
                    else:
                        harmony_velocity = 90
                elif context.style == SeedMusicStyle.CALM:
                    harmony_velocity = 70
                else:
                    harmony_velocity = 80

                harmony_track.notes.append(
                    Note(
                        pitch=pitch,
                        start_time=start_time,
                        duration=duration,
                        velocity=harmony_velocity,
                        waveform=context.style_params.harmony_waveform,
                        duty_cycle=context.style_params.harmony_duty,
                        adsr=harmony_adsr,
                    )
                )

    return harmony_track


def build_drum_track(
    context: TrackBuildContext,
    *,
    drum_boost: float,
    enable_drums: bool,
) -> Track | None:
    """根据上下文构建鼓点轨道。"""

    if not enable_drums:
        return None

    drum_track = Track(name="Seed 鼓点", track_type=TrackType.DRUM_TRACK)

    for bar_idx in range(context.length_bars):
        bar_start = bar_idx * context.beats_per_bar
        phrase_idx = context.phrase_plan.phrase_index_at_bar(bar_idx)
        phrase_role = context.phrase_plan.phrase_role_at_bar(bar_idx)

        if phrase_idx >= 0:
            phrase_progress = context.phrase_plan.phrase_progress_at_bar(bar_idx, phrase_idx)
            is_phrase_end = context.phrase_plan.is_phrase_end(bar_idx, phrase_idx)
        else:
            phrase_progress = context.phrase_plan.phrase_progress_at_bar(bar_idx)
            is_phrase_end = context.phrase_plan.is_phrase_end(bar_idx)

        drum_events = context.style_config.generate_drum_pattern(
            context.rng,
            bar_idx,
            bar_start,
            phrase_role,
            phrase_progress,
            is_phrase_end,
            context.beats_per_bar,
            context.variant_id,
            context.phrase_plan.intro_bars,
            context.quiet_bars,
        )

        for event in drum_events:
            drum_track.drum_events.append(event)

    if context.style == SeedMusicStyle.DANCE:
        base = 1.2
        drum_track.volume = max(0.2, min(1.8, base + drum_boost))
    elif context.style == SeedMusicStyle.WORKSHOP:
        base = 0.95
        drum_track.volume = max(0.2, min(1.3, base + drum_boost))
    elif context.style == SeedMusicStyle.SUSPENSE:
        base = 0.6
        drum_track.volume = max(0.2, min(1.2, base + drum_boost))
    elif context.style == SeedMusicStyle.ROCK:
        base = 1.1
        drum_track.volume = max(0.2, min(1.5, base + drum_boost))
    elif context.style == SeedMusicStyle.BATTLE:
        base = 1.0
        drum_track.volume = max(0.2, min(1.2, base + drum_boost))

    return drum_track


__all__ = [
    "TrackBuildContext",
    "build_bass_track",
    "build_drum_track",
    "build_harmony_track",
]
