from unittest.mock import patch

import httpx

from app.ingest.llm_salary_extractor import extract_salary_with_llm


def _mock_response(content: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json={
            "choices": [
                {"message": {"content": content}}
            ]
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


def test_extracts_yearly_range():
    resp = _mock_response('{"min": 50000, "max": 75000, "period": "yearly"}')
    with patch("app.ingest.llm_salary_extractor.httpx.post", return_value=resp):
        result = extract_salary_with_llm("some text", api_key="test-key")
    assert result is not None
    assert result.min_value == 50000
    assert result.max_value == 75000
    assert result.period == "yearly"


def test_extracts_hourly_single():
    resp = _mock_response('{"min": 25.50, "max": 25.50, "period": "hourly"}')
    with patch("app.ingest.llm_salary_extractor.httpx.post", return_value=resp):
        result = extract_salary_with_llm("some text", api_key="test-key")
    assert result is not None
    assert result.min_value == 25.50
    assert result.max_value == 25.50
    assert result.period == "hourly"


def test_returns_none_when_no_salary():
    resp = _mock_response('{"min": null, "max": null, "period": null}')
    with patch("app.ingest.llm_salary_extractor.httpx.post", return_value=resp):
        result = extract_salary_with_llm("some text", api_key="test-key")
    assert result is None


def test_handles_markdown_code_fences():
    resp = _mock_response('```json\n{"min": 60000, "max": 80000, "period": "yearly"}\n```')
    with patch("app.ingest.llm_salary_extractor.httpx.post", return_value=resp):
        result = extract_salary_with_llm("some text", api_key="test-key")
    assert result is not None
    assert result.min_value == 60000


def test_returns_none_on_api_error():
    with patch(
        "app.ingest.llm_salary_extractor.httpx.post",
        side_effect=httpx.ConnectError("fail"),
    ):
        result = extract_salary_with_llm("some text", api_key="test-key")
    assert result is None


def test_returns_none_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        result = extract_salary_with_llm("some text", api_key=None)
    assert result is None


def test_swaps_min_max_if_reversed():
    resp = _mock_response('{"min": 80000, "max": 50000, "period": "yearly"}')
    with patch("app.ingest.llm_salary_extractor.httpx.post", return_value=resp):
        result = extract_salary_with_llm("some text", api_key="test-key")
    assert result is not None
    assert result.min_value == 50000
    assert result.max_value == 80000


def test_infers_period_when_missing():
    resp = _mock_response('{"min": 45, "max": 55, "period": null}')
    with patch("app.ingest.llm_salary_extractor.httpx.post", return_value=resp):
        result = extract_salary_with_llm("some text", api_key="test-key")
    assert result is not None
    assert result.period == "hourly"

    resp = _mock_response('{"min": 60000, "max": 80000, "period": null}')
    with patch("app.ingest.llm_salary_extractor.httpx.post", return_value=resp):
        result = extract_salary_with_llm("some text", api_key="test-key")
    assert result is not None
    assert result.period == "yearly"
