from __future__ import annotations

from forge.core.llm import parse_json_response


def test_parse_json_response_handles_fenced_json() -> None:
    parsed = parse_json_response("```json\n{\"ok\": true}\n```")
    assert parsed == {"ok": True}


def test_parse_json_response_handles_wrapped_json() -> None:
    parsed = parse_json_response("Here is the result:\n{\"count\": 2}")
    assert parsed == {"count": 2}

