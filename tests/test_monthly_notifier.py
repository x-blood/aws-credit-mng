"""
Unit tests for monthly_notifier/handler.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from monthly_notifier.handler import _build_monthly_blocks, _summarize_credits
from tests.conftest import days_from_now, make_credit


# ---------------------------------------------------------------------------
# _summarize_credits
# ---------------------------------------------------------------------------

class TestSummarizeCredits:
    def test_sums_active_remaining_only(self):
        # ENABLED かつ有効期限内（cr-001）と ENABLED だが期限切れ（cr-002）
        credits = [
            make_credit("cr-001", status="ENABLED", remaining=3000.0, end_date=days_from_now(365)),
            make_credit("cr-002", status="ENABLED", remaining=500.0, end_date=days_from_now(-30)),  # 期限切れ
        ]
        summary = _summarize_credits(credits)
        assert summary["total_remaining"] == 3000.0  # BR-01: 期限切れは除外
        assert summary["credit_count"] == 1

    def test_empty_credits_returns_zero(self):
        summary = _summarize_credits([])
        assert summary["total_remaining"] == 0.0
        assert summary["credit_count"] == 0
        assert summary["nearest_expiry"] is None

    def test_nearest_expiry_selects_earliest(self):
        credits = [
            make_credit("cr-001", end_date=days_from_now(365)),
            make_credit("cr-002", end_date=days_from_now(30)),
        ]
        summary = _summarize_credits(credits)
        assert summary["nearest_expiry"] == (datetime.now(tz=timezone.utc) + timedelta(days=30)).date()  # BR-11
        assert summary["nearest_credit_id"] == "cr-002"

    def test_multiple_active_summed(self):
        credits = [
            make_credit("cr-001", remaining=1000.0),
            make_credit("cr-002", remaining=2500.0),
        ]
        summary = _summarize_credits(credits)
        assert summary["total_remaining"] == 3500.0  # BR-02
        assert summary["credit_count"] == 2

    def test_includes_estimated_amount(self):
        """推定残高・未確定の使用見込みがサマリーに含まれる"""
        credits = [make_credit("cr-001", remaining=500.0)]
        # estimatedAmount を 477.10 に設定する
        credits[0]["estimatedAmount"] = {"currencyCode": "USD", "currencyAmount": "477.10"}
        summary = _summarize_credits(credits)
        assert summary["total_estimated"] == pytest.approx(477.10)
        assert summary["total_used"] == pytest.approx(500.0 - 477.10)


# ---------------------------------------------------------------------------
# _build_monthly_blocks
# ---------------------------------------------------------------------------

class TestBuildMonthlyBlocks:
    def _make_summary(self, total=5000.0, count=2):
        return {
            "total_remaining": total,
            "total_estimated": total * 0.95,
            "total_used": total * 0.05,
            "currency": "USD",
            "credit_count": count,
            "nearest_expiry": date(2026, 9, 30),
            "nearest_credit_id": "cr-001",
        }

    def test_includes_header_and_divider(self):
        blocks = _build_monthly_blocks(self._make_summary())
        types = [b["type"] for b in blocks]
        assert "header" in types
        assert "divider" in types


# ---------------------------------------------------------------------------
# handler integration (mocked dependencies)
# ---------------------------------------------------------------------------

class TestMonthlyHandler:
    def test_handler_sends_message(self, lambda_env):
        credits = [make_credit()]

        with patch("monthly_notifier.handler.get_credits", return_value=credits), \
             patch("monthly_notifier.handler.get_channel_id", return_value="C0TEST1234"), \
             patch("monthly_notifier.handler.post_message") as mock_post:
            from monthly_notifier.handler import handler
            handler({}, None)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs.get("text") or mock_post.call_args[0][2]  # text arg present

    def test_handler_propagates_slack_error(self, lambda_env):
        from common.slack_client import SlackApiError
        with patch("monthly_notifier.handler.get_credits", return_value=[make_credit()]), \
             patch("monthly_notifier.handler.get_channel_id", return_value="C0TEST1234"), \
             patch("monthly_notifier.handler.post_message",
                   side_effect=SlackApiError("channel_not_found")):
            from monthly_notifier.handler import handler
            with pytest.raises(SlackApiError):
                handler({}, None)
