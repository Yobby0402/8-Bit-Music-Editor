import pytest

from core.sfx_ai_service import (
    build_sfx_generation_messages,
    extract_json_object,
    generate_sfx_spec_from_description,
)


def test_build_sfx_generation_messages_rejects_empty_description():
    with pytest.raises(ValueError, match="empty"):
        build_sfx_generation_messages(" ")


def test_extract_json_object_supports_fenced_response():
    data = extract_json_object(
        """
        Sure:
        ```json
        {"kind": "coin", "label": "Coin", "notes": [{"pitch": 84, "start_beat": 0, "duration_beats": 0.1}]}
        ```
        """
    )

    assert data["kind"] == "coin"
    assert data["notes"][0]["pitch"] == 84


def test_generate_sfx_spec_from_description_uses_chat_fn_and_validates_payload():
    calls = []

    def fake_chat(base_url, model, messages, **kwargs):
        calls.append((base_url, model, messages, kwargs))
        return """
        {
          "kind": "coin_ai",
          "label": "AI coin",
          "notes": [
            {
              "pitch": 84,
              "start_beat": 0.0,
              "duration_beats": 0.1,
              "velocity": 112,
              "waveform": "square",
              "adsr": {"attack": 0.002, "decay": 0.04, "sustain": 0.25, "release": 0.03}
            }
          ],
          "delay_params": {"delay_time": 0.06, "feedback": 0.2, "mix": 0.2, "enabled": true}
        }
        """

    spec = generate_sfx_spec_from_description(
        "coin pickup",
        base_url="http://127.0.0.1:1234/v1",
        model="local-model",
        chat_fn=fake_chat,
    )

    assert spec.kind == "coin_ai"
    assert spec.label == "AI coin"
    assert spec.notes[0].pitch == 84
    assert spec.delay_params is not None
    assert calls[0][0] == "http://127.0.0.1:1234/v1"
    assert calls[0][1] == "local-model"
