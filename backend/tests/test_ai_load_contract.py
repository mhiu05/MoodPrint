def test_synthetic_provider_reports_known_usage_within_the_envelope():
    from tests.scale_readiness_server import known_usage

    usage = known_usage()
    assert 0 < usage.input_tokens <= 64000
    assert 0 < usage.output_tokens <= 1200
    assert usage.total_tokens == usage.input_tokens + usage.output_tokens
