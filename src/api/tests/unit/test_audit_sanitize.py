"""Unit tests for audit sanitization."""

import json

from rag_api.audit_sanitize import (
    sanitize_headers,
    sanitize_payload,
    sanitize_json_payload,
    truncate,
)


class TestSanitizeHeaders:
    def test_removes_authorization_header(self):
        headers = {"Authorization": "Bearer token123", "Content-Type": "application/json"}
        result = sanitize_headers(headers)
        assert "Authorization" not in result
        assert result["Content-Type"] == "application/json"

    def test_removes_cookie_header(self):
        headers = {"Cookie": "session=abc", "User-Agent": "test"}
        result = sanitize_headers(headers)
        assert "Cookie" not in result
        assert result["User-Agent"] == "test"

    def test_removes_x_api_key_header(self):
        headers = {"X-API-Key": "secret", "X-Request-ID": "123"}
        result = sanitize_headers(headers)
        assert "X-API-Key" not in result
        assert result["X-Request-ID"] == "123"

    def test_case_insensitive_header_matching(self):
        headers = {"authorization": "Bearer token"}
        result = sanitize_headers(headers)
        assert "authorization" not in result


class TestSanitizePayload:
    def test_redacts_api_key(self):
        payload = {"api_key": "secret123", "query": "test"}
        result = sanitize_payload(payload)
        assert result["api_key"] == "***REDACTED***"
        assert result["query"] == "test"

    def test_redacts_token(self):
        payload = {"token": "abc123", "user": "john"}
        result = sanitize_payload(payload)
        assert result["token"] == "***REDACTED***"

    def test_redacts_password(self):
        payload = {"password": "pass123", "username": "john"}
        result = sanitize_payload(payload)
        assert result["password"] == "***REDACTED***"

    def test_redacts_bearer_token_in_string(self):
        payload = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = sanitize_payload(payload)
        assert result == "***REDACTED***"

    def test_redacts_nested_dict(self):
        payload = {"user": {"api_key": "secret", "name": "john"}}
        result = sanitize_payload(payload)
        assert result["user"]["api_key"] == "***REDACTED***"
        assert result["user"]["name"] == "john"

    def test_redacts_list_of_dicts(self):
        payload = [{"token": "secret"}, {"api_key": "key123"}]
        result = sanitize_payload(payload)
        assert result[0]["token"] == "***REDACTED***"
        assert result[1]["api_key"] == "***REDACTED***"

    def test_case_insensitive_key_matching(self):
        payload = {"API_KEY": "secret", "Token": "abc"}
        result = sanitize_payload(payload)
        assert result["API_KEY"] == "***REDACTED***"
        assert result["Token"] == "***REDACTED***"

    def test_preserves_non_sensitive_data(self):
        payload = {"query": "test", "limit": 10, "filters": [1, 2, 3]}
        result = sanitize_payload(payload)
        assert result == payload


class TestSanitizeJsonPayload:
    def test_parses_and_sanitizes_json(self):
        payload = json.dumps({"api_key": "secret", "query": "test"})
        result = sanitize_json_payload(payload)
        parsed = json.loads(result)
        assert parsed["api_key"] == "***REDACTED***"
        assert parsed["query"] == "test"

    def test_truncates_large_payloads(self):
        large_obj = {"data": "x" * 10000}
        payload = json.dumps(large_obj)
        result = sanitize_json_payload(payload)
        assert len(result) < len(payload)
        assert "truncated" in result

    def test_handles_invalid_json(self):
        payload = "not valid json"
        result = sanitize_json_payload(payload)
        assert len(result) <= 5050  # MAX_PAYLOAD_SIZE + truncation msg


class TestTruncate:
    def test_truncates_long_string(self):
        long_str = "x" * 10000
        result = truncate(long_str)
        assert len(result) < len(long_str)
        assert "truncated" in result

    def test_preserves_short_string(self):
        short_str = "hello"
        result = truncate(short_str)
        assert result == short_str

    def test_respects_custom_max_length(self):
        long_str = "x" * 100
        result = truncate(long_str, max_len=50)
        assert len(result) < 100
