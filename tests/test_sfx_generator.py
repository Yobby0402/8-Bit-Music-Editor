from core.models import Project, TrackRole, TrackType, WaveformType
from core.sfx_generator import (
    build_sfx_notes,
    build_sfx_spec,
    find_sfx_track,
    list_sfx_presets,
    make_sfx_track,
    sfx_spec_from_dict,
    sfx_spec_to_dict,
)


def test_list_sfx_presets_includes_coin():
    assert "coin" in list_sfx_presets()
    assert "laser" in list_sfx_presets()
    assert "explosion" in list_sfx_presets()


def test_coin_sfx_spec_is_short_upward_phrase():
    spec = build_sfx_spec("coin")

    assert spec.kind == "coin"
    assert spec.duration_beats > 0
    assert [note.pitch for note in spec.notes] == sorted(note.pitch for note in spec.notes)
    assert spec.notes[0].waveform == WaveformType.SQUARE
    assert spec.delay_params is not None
    assert spec.delay_params.enabled is True


def test_expanded_sfx_presets_configure_track_effects():
    laser = build_sfx_spec("laser")
    power_up = build_sfx_spec("power_up")
    explosion = build_sfx_spec("explosion")

    assert laser.filter_params is not None
    assert laser.vibrato_params is not None
    assert power_up.delay_params is not None
    assert power_up.tremolo_params is not None
    assert explosion.filter_params is not None
    assert explosion.tremolo_params is not None


def test_build_sfx_notes_converts_beats_to_project_timing():
    project = Project(bpm=120.0)
    spec = build_sfx_spec("coin")

    notes = build_sfx_notes(project, spec, start_beat=2.0)

    assert len(notes) == len(spec.notes)
    assert notes[0].start_tick == project.beats_to_ticks(2.0)
    assert notes[0].duration_ticks == project.beats_to_ticks(spec.notes[0].duration_beats)
    assert notes[0].adsr is not None


def test_make_and_find_sfx_track():
    sfx_track = make_sfx_track()

    assert sfx_track.track_type == TrackType.NOTE_TRACK
    assert sfx_track.role == TrackRole.EFFECT
    assert find_sfx_track([sfx_track]) is sfx_track


def test_sfx_spec_from_dict_validates_and_clamps_ai_payload():
    spec = sfx_spec_from_dict(
        {
            "kind": "sparkle",
            "label": "Sparkle",
            "notes": [
                {
                    "pitch": 200,
                    "start_beat": -1.0,
                    "duration_beats": 0.0,
                    "velocity": 140,
                    "waveform": "triangle",
                    "duty_cycle": 2.0,
                    "adsr": {"attack": -1.0, "decay": 0.02, "sustain": 2.0, "release": 0.03},
                    "vibrato": {"rate": 18.0, "depth": 1.5, "enabled": True},
                }
            ],
        }
    )

    note = spec.notes[0]
    assert spec.kind == "sparkle"
    assert spec.label == "Sparkle"
    assert note.pitch == 127
    assert note.start_beat == 0.0
    assert note.duration_beats == 0.01
    assert note.velocity == 127
    assert note.waveform == WaveformType.TRIANGLE
    assert note.duty_cycle == 0.95
    assert note.adsr.attack == 0.0
    assert note.adsr.sustain == 1.0
    assert note.vibrato is not None


def test_sfx_spec_from_dict_accepts_track_effect_payloads():
    spec = sfx_spec_from_dict(
        {
            "label": "Filtered zap",
            "filter_params": {
                "filter_type": "highpass",
                "cutoff_frequency": 50000.0,
                "resonance": 99.0,
                "enabled": True,
            },
            "delay_params": {
                "delay_time": 5.0,
                "feedback": 2.0,
                "mix": 2.0,
                "enabled": True,
            },
            "tremolo_params": {"rate": 99.0, "depth": 5.0, "enabled": True},
            "vibrato_params": {"rate": 7.0, "depth": 1.2, "enabled": True},
            "notes": [{"pitch": 88, "start_beat": 0.0, "duration_beats": 0.1}],
        }
    )

    assert spec.filter_params is not None
    assert spec.filter_params.cutoff_frequency == 20000.0
    assert spec.filter_params.resonance == 10.0
    assert spec.delay_params is not None
    assert spec.delay_params.delay_time == 2.0
    assert spec.delay_params.feedback == 0.95
    assert spec.delay_params.mix == 1.0
    assert spec.tremolo_params is not None
    assert spec.tremolo_params.rate == 40.0
    assert spec.tremolo_params.depth == 1.0
    assert spec.vibrato_params is not None


def test_sfx_spec_to_dict_round_trips_effect_payload():
    original = build_sfx_spec("power_up")

    restored = sfx_spec_from_dict(sfx_spec_to_dict(original))

    assert restored.kind == "power_up"
    assert len(restored.notes) == len(original.notes)
    assert restored.delay_params is not None
    assert restored.tremolo_params is not None


def test_sfx_spec_from_dict_rejects_missing_notes():
    try:
        sfx_spec_from_dict({"label": "Empty"})
    except ValueError as exc:
        assert "notes" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
