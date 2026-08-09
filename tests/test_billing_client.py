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
    get_credit_allocation_history,
    get_credits,
)
from tests.conftest import make_credit, make_history_record


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


# ---------------------------------------------------------------------------
# get_credit_allocation_history
# ---------------------------------------------------------------------------

class TestGetCreditAllocationHistory:
    def test_returns_records_without_pagination(self):
        record = make_history_record()
        mock_response = {
            "creditAllocationHistoryList": [record],
            "partialResults": False,
            "failedMonths": [],
        }
        with patch("common.billing_client._get_client") as mock_client_factory:
            mock_client_factory.return_value.get_credit_allocation_history.return_value = mock_response
            records, partial, failed = get_credit_allocation_history("123456789012")
        assert records == [record]
        assert partial is False
        assert failed == []

    def test_handles_pagination(self):
        page1 = {
            "creditAllocationHistoryList": [make_history_record(billing_month="2026-05")],
            "partialResults": False,
            "failedMonths": [],
            "nextToken": "token-abc",
        }
        page2 = {
            "creditAllocationHistoryList": [make_history_record(billing_month="2026-06")],
            "partialResults": False,
            "failedMonths": [],
        }
        with patch("common.billing_client._get_client") as mock_client_factory:
            mock_boto = mock_client_factory.return_value
            mock_boto.get_credit_allocation_history.side_effect = [page1, page2]
            records, partial, failed = get_credit_allocation_history("123456789012")
        assert len(records) == 2
        assert mock_boto.get_credit_allocation_history.call_count == 2

    def test_reports_partial_results(self):
        mock_response = {
            "creditAllocationHistoryList": [],
            "partialResults": True,
            "failedMonths": ["2026-04"],
        }
        with patch("common.billing_client._get_client") as mock_client_factory:
            mock_client_factory.return_value.get_credit_allocation_history.return_value = mock_response
            records, partial, failed = get_credit_allocation_history("123456789012")
        assert partial is True
        assert failed == ["2026-04"]
