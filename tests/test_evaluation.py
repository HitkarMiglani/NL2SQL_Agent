from nl2sql_agent.evaluation import _parse_judge_response


def test_parse_valid_json_response():
    raw = '{"correctness": 5, "relevance": 4, "clarity": 3, "rationale": "Solid answer."}'
    score = _parse_judge_response(raw)
    assert score is not None
    assert score["correctness"] == 5
    assert score["relevance"] == 4
    assert score["clarity"] == 3
    assert score["overall_score"] == 4
    assert score["rationale"] == "Solid answer."


def test_parse_clamps_out_of_range_scores():
    raw = '{"correctness": 9, "relevance": -2, "clarity": 3, "rationale": "x"}'
    score = _parse_judge_response(raw)
    assert score is not None
    assert score["correctness"] == 5
    assert score["relevance"] == 1


def test_parse_handles_markdown_fenced_json():
    raw = '```json\n{"correctness": 3, "relevance": 3, "clarity": 3, "rationale": "ok"}\n```'
    score = _parse_judge_response(raw)
    assert score is not None
    assert score["overall_score"] == 3


def test_parse_returns_none_for_unparsable_text():
    assert _parse_judge_response("not json at all") is None


def test_parse_returns_none_for_missing_fields():
    raw = '{"correctness": 3}'
    assert _parse_judge_response(raw) is None
