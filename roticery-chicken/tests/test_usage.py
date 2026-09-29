from roticery.usage import estimate_tokens, extract_usage


def test_extract_chat_usage():
    assert extract_usage({"usage": {"prompt_tokens": 10, "completion_tokens": 7, "total_tokens": 17}}) == 17


def test_extract_responses_usage():
    assert extract_usage({"usage": {"input_tokens": 10, "output_tokens": 7}}) == 17


def test_extract_without_usage_uses_zero():
    assert extract_usage({}) == 0


def test_estimate_is_positive():
    assert estimate_tokens({"messages": [{"role": "user", "content": "hello"}]}) >= 1
