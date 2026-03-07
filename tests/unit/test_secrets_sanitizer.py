"""
Unit tests for SecretsSanitizer.

Tests detection and sanitization of various secret patterns.
"""

import pytest


class TestSecretsSanitizerSanitize:
    """Tests for sanitize() method."""

    def test_sanitizes_google_api_key(self):
        """Sanitizes Google API keys (AIza format)."""
        from app.core.security import secrets_sanitizer

        # Exactly 35 chars after AIza
        key = 'AIzaSyB_1234567890abcdefghijklmnopqrs12'
        text = f'My API key is {key}'
        result = secrets_sanitizer.sanitize(text)

        assert '[REDACTED_GOOGLE_API_KEY]' in result
        assert key not in result

    def test_sanitizes_jwt_token(self):
        """Sanitizes JWT tokens."""
        from app.core.security import secrets_sanitizer

        jwt = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        result = secrets_sanitizer.sanitize(f'Token: {jwt}')

        assert '[REDACTED_JWT_TOKEN]' in result
        assert jwt not in result

    def test_sanitizes_github_pat(self):
        """Sanitizes GitHub Personal Access Tokens."""
        from app.core.security import secrets_sanitizer

        # 36 chars after ghp_
        token = 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'
        result = secrets_sanitizer.sanitize(f'GitHub: {token}')

        assert '[REDACTED_GITHUB_PAT]' in result
        assert token not in result

    def test_sanitizes_bearer_token(self):
        """Sanitizes Bearer tokens."""
        from app.core.security import secrets_sanitizer

        text = 'Authorization: Bearer eyJhbGciOiJSUzI1NiIs'
        result = secrets_sanitizer.sanitize(text)

        assert '[REDACTED_BEARER_TOKEN]' in result

    def test_sanitizes_url_password(self):
        """Sanitizes passwords in URLs."""
        from app.core.security import secrets_sanitizer

        url = 'postgres://admin:supersecretpassword@db.example.com/mydb'
        result = secrets_sanitizer.sanitize(url)

        assert '[REDACTED_URL_PASSWORD]' in result
        assert 'supersecretpassword' not in result

    def test_sanitizes_aws_access_key(self):
        """Sanitizes AWS Access Key IDs."""
        from app.core.security import secrets_sanitizer

        key = 'AKIAIOSFODNN7EXAMPLE'
        result = secrets_sanitizer.sanitize(f'AWS Key: {key}')

        assert '[REDACTED_AWS_ACCESS_KEY]' in result
        assert key not in result

    def test_sanitizes_private_key_header(self):
        """Sanitizes private key headers."""
        from app.core.security import secrets_sanitizer

        text = '-----BEGIN RSA PRIVATE KEY-----\nMIIE...'
        result = secrets_sanitizer.sanitize(text)

        assert '[REDACTED_PRIVATE_KEY]' in result

    def test_sanitizes_multiple_secrets(self):
        """Sanitizes multiple secrets in same text."""
        from app.core.security import secrets_sanitizer

        text = '''
        config = {
            google_key: AIzaSyB_1234567890abcdefghijklmnopqrs12,
            github: ghp_1234567890abcdefghijklmnopqrstuvwxyz
        }
        '''
        result = secrets_sanitizer.sanitize(text)

        assert '[REDACTED_GOOGLE_API_KEY]' in result
        assert '[REDACTED_GITHUB_PAT]' in result

    def test_preserves_normal_text(self):
        """Preserves text without secrets."""
        from app.core.security import secrets_sanitizer

        text = 'Hello, this is a normal message without any secrets.'
        result = secrets_sanitizer.sanitize(text)

        assert result == text

    def test_handles_empty_string(self):
        """Handles empty string input."""
        from app.core.security import secrets_sanitizer

        result = secrets_sanitizer.sanitize('')
        assert result == ''

    def test_handles_none_like_empty(self):
        """Handles None-like empty input."""
        from app.core.security import secrets_sanitizer

        result = secrets_sanitizer.sanitize('')
        assert result == ''


class TestSecretsSanitizerDetect:
    """Tests for detect() method."""

    def test_detects_google_api_key(self):
        """Detects Google API keys."""
        from app.core.security import secrets_sanitizer

        key = 'AIzaSyB_1234567890abcdefghijklmnopqrs12'
        detected = secrets_sanitizer.detect(key)

        assert 'GOOGLE_API_KEY' in detected

    def test_detects_jwt_token(self):
        """Detects JWT tokens."""
        from app.core.security import secrets_sanitizer

        jwt = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        detected = secrets_sanitizer.detect(jwt)

        assert 'JWT_TOKEN' in detected

    def test_detects_multiple_types(self):
        """Detects multiple secret types."""
        from app.core.security import secrets_sanitizer

        text = 'AIzaSyB_1234567890abcdefghijklmnopqrs12 ghp_1234567890abcdefghijklmnopqrstuvwxyz'
        detected = secrets_sanitizer.detect(text)

        assert 'GOOGLE_API_KEY' in detected
        assert 'GITHUB_PAT' in detected

    def test_returns_empty_for_no_secrets(self):
        """Returns empty list for text without secrets."""
        from app.core.security import secrets_sanitizer

        detected = secrets_sanitizer.detect('Normal text without secrets')
        assert detected == []

    def test_returns_empty_for_empty_input(self):
        """Returns empty list for empty input."""
        from app.core.security import secrets_sanitizer

        detected = secrets_sanitizer.detect('')
        assert detected == []


class TestSecretsSanitizerHasSecrets:
    """Tests for has_secrets() method."""

    def test_returns_true_for_secrets(self):
        """Returns True when secrets are present."""
        from app.core.security import secrets_sanitizer

        key = 'AIzaSyB_1234567890abcdefghijklmnopqrs12'
        assert secrets_sanitizer.has_secrets(key) is True

    def test_returns_false_for_no_secrets(self):
        """Returns False when no secrets are present."""
        from app.core.security import secrets_sanitizer

        assert secrets_sanitizer.has_secrets('Normal text') is False

    def test_returns_false_for_empty(self):
        """Returns False for empty input."""
        from app.core.security import secrets_sanitizer

        assert secrets_sanitizer.has_secrets('') is False


class TestSecretsSanitizerPatterns:
    """Tests for specific pattern coverage."""

    def test_github_oauth_token(self):
        """Detects GitHub OAuth tokens."""
        from app.core.security import secrets_sanitizer

        token = 'gho_1234567890abcdefghijklmnopqrstuvwxyz'
        result = secrets_sanitizer.sanitize(token)

        assert '[REDACTED_GITHUB_OAUTH]' in result

    def test_slack_token(self):
        """Detects Slack tokens."""
        from app.core.security import secrets_sanitizer

        token = 'xoxb-1234567890-abcdefghij'
        result = secrets_sanitizer.sanitize(token)

        assert '[REDACTED_SLACK_TOKEN]' in result

    def test_generic_password(self):
        """Detects generic password patterns."""
        from app.core.security import secrets_sanitizer

        text = 'password="mysecretpassword123"'
        result = secrets_sanitizer.sanitize(text)

        assert '[REDACTED_GENERIC_SECRET]' in result

    def test_does_not_false_positive_on_short_values(self):
        """Does not match on too-short values."""
        from app.core.security import secrets_sanitizer

        # Short values should not trigger GENERIC_SECRET
        text = 'password: abc'  # Only 3 chars
        result = secrets_sanitizer.sanitize(text)

        # Should be unchanged (value too short)
        assert 'abc' in result
