from unittest.mock import MagicMock, patch

from core.llm_client import chat_completion


def test_chat_completion_parses_assistant_content():
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"choices": [{"message": {"content": "hello"}}]}

    inner_client = MagicMock()
    inner_client.post.return_value = post_resp

    cm = MagicMock()
    cm.__enter__.return_value = inner_client
    cm.__exit__.return_value = None

    with patch("core.llm_client.httpx.Client", return_value=cm) as _:
        out = chat_completion(
            "http://127.0.0.1:1234/v1",
            "m",
            [{"role": "user", "content": "x"}],
            timeout_sec=5.0,
        )
    assert out == "hello"
