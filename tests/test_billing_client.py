"""
Unit tests for common/billing_client.py
Uses moto to mock AWS Billing API calls.
"""
import sys
import os

# Ensure src/ is on the path when running tests from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import MagicMock, patch, call
import pytest
from botocore.exceptions import ClientError

from common.billing_client import (
    _retry_with_backoff,
    get_credits,
)
from tests.conftest import make_credit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _throttling_error():
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "GetCredits",
    )


def _other_error():
    return ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
        "GetCredits",
    )


# ---------------------------------------------------------------------------
# _retry_with_backoff
# ---------------------------------------------------------------------------

class TestRetryWithBackoff:
    def test_success_on_first_attempt(self):
        func = MagicMock(return_value={"ok": True})
        result = _retry_with_backoff(func)
        assert result == {"ok": True}
        func.assert_called_once()

    def test_retries_on_throttling_then_succeeds(self):
        func = MagicMock(side_effect=[_throttling_error(), {"ok": True}])
        with patch("common.billing_client.time.sleep"):
            result = _retry_with_backoff(func)
        assert result == {"ok": True}
        assert func.call_count == 2

    def test_raises_after_max_retries(self):
        func = MagicMock(side_effect=_throttling_error())
        with patch("common.billing_client.time.sleep"):
            with pytest.raises(ClientError) as exc_info:
                _retry_with_backoff(func)
        assert exc_info.value.response["Error"]["Code"] == "ThrottlingException"

    def test_raises_immediately_on_non_throttling_error(self):
        func = MagicMock(side_effect=_other_error())
        with pytest.raises(ClientError) as exc_info:
            _retry_with_backoff(func)
        assert exc_info.value.response["Error"]["Code"] == "AccessDeniedException"
        func.assert_called_once()


# ---------------------------------------------------------------------------
# get_credits
# ---------------------------------------------------------------------------

class TestGetCredits:
    def test_returns_credits_list(self):
        credit = make_credit()
        mock_response = {"credits": [credit]}
        with patch("common.billing_client._get_client") as mock_client_factory:
            mock_client_factory.return_value.get_credits.return_value = mock_response
            result = get_credits("123456789012")
        assert result == [credit]

    def test_returns_empty_list_when_no_credits(self):
        with patch("common.billing_client._get_client") as mock_client_factory:
            mock_client_factory.return_value.get_credits.return_value = {"credits": []}
            result = get_credits("123456789012")
        assert result == []

    def test_passes_payer_flag(self):
        with patch("common.billing_client._get_client") as mock_client_factory:
            mock_boto = mock_client_factory.return_value
            mock_boto.get_credits.return_value = {"credits": []}
            get_credits("123456789012", payer_flag=True)
            call_kwargs = mock_boto.get_credits.call_args[1]
        assert call_kwargs["payerAccountFlag"] is True

