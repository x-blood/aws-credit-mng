"""
Unit tests for expiry_checker/handler.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import date, timedelta, datetime, timezone
from unittest.mock import patch

import pytest

from expiry_checker.handler import _build_expiry_blocks, _classify_expiring_credits
from tests.conftest import make_credit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# テスト基準日を「今日」に動的に設定する（固定日付だと有効期限判定がずれる）
TODAY = datetime.now(tz=timezone.utc).date()


def credit_expiring_in(days: int, remaining: float = 1000.0) -> dict:
    end = TODAY + timedelta(days=days)
    # 時刻を 23:59:59 にして当日中は有効とする（00:00:00 だと当日判定が失敗する）
    return make_credit(
        credit_id=f"cr-{days:03d}d",
        remaining=remaining,
        end_date=end.strftime("%Y-%m-%d 23:59:59+00:00"),
    )


# ---------------------------------------------------------------------------
# _classify_expiring_credits (BR-04, BR-05)
# ---------------------------------------------------------------------------

class TestClassifyExpiringCredits:
    def test_critical_is_today(self):
        result = _classify_expiring_credits([credit_expiring_in(0)], TODAY)
        assert len(result["critical"]) == 1
        assert result["warning"] == []
        assert result["info"] == []

    def test_warning_boundary_1_day(self):
        result = _classify_expiring_credits([credit_expiring_in(1)], TODAY)
        assert len(result["warning"]) == 1

    def test_warning_boundary_7_days(self):
        result = _classify_expiring_credits([credit_expiring_in(7)], TODAY)
        assert len(result["warning"]) == 1

    def test_info_boundary_8_days(self):
        result = _classify_expiring_credits([credit_expiring_in(8)], TODAY)
        assert len(result["info"]) == 1

    def test_info_boundary_30_days(self):
        result = _classify_expiring_credits([credit_expiring_in(30)], TODAY)
        assert len(result["info"]) == 1

    def test_31_days_excluded(self):
        result = _classify_expiring_credits([credit_expiring_in(31)], TODAY)
        assert result == {"critical": [], "warning": [], "info": []}

    def test_already_expired_excluded(self):
        result = _classify_expiring_credits([credit_expiring_in(-1)], TODAY)
        assert result == {"critical": [], "warning": [], "info": []}

    def test_zero_remaining_excluded(self):  # BR-05
        credit = credit_expiring_in(5, remaining=0.0)
        result = _classify_expiring_credits([credit], TODAY)
        assert result == {"critical": [], "warning": [], "info": []}

    def test_inactive_credit_excluded(self):  # BR-01
        credit = make_credit(status="EXPIRED", end_date=(TODAY + timedelta(days=3)).strftime("%Y-%m-%d 00:00:00+00:00"))
        result = _classify_expiring_credits([credit], TODAY)
        assert result == {"critical": [], "warning": [], "info": []}

    def test_multiple_levels(self):
        credits = [
            credit_expiring_in(0),   # critical
            credit_expiring_in(5),   # warning
            credit_expiring_in(20),  # info
            credit_expiring_in(45),  # excluded
        ]
        result = _classify_expiring_credits(credits, TODAY)
        assert len(result["critical"]) == 1
        assert len(result["warning"]) == 1
        assert len(result["info"]) == 1


# ---------------------------------------------------------------------------
# _build_expiry_blocks
# ---------------------------------------------------------------------------

class TestBuildExpiryBlocks:
    def test_all_levels_included(self):
        classified = {
            "critical": [(credit_expiring_in(0), 0)],
            "warning": [(credit_expiring_in(3), 3)],
            "info": [(credit_expiring_in(15), 15)],
        }
        blocks = _build_expiry_blocks(classified, TODAY)
        all_text = str(blocks)
        assert "CRITICAL" in all_text
        assert "WARNING" in all_text
        assert "INFO" in all_text

    def test_empty_level_omitted(self):
        classified = {
            "critical": [],
            "warning": [(credit_expiring_in(4), 4)],
            "info": [],
        }
        blocks = _build_expiry_blocks(classified, TODAY)
        all_text = str(blocks)
        assert "CRITICAL" not in all_text
        assert "WARNING" in all_text
        assert "INFO" not in all_text


# ---------------------------------------------------------------------------
# handler integration (mocked dependencies)
# ---------------------------------------------------------------------------

class TestExpiryHandler:
    def test_sends_alert_when_expiring_credits(self, lambda_env):
        credits = [credit_expiring_in(5)]
        # _classify_expiring_credits の戻り値を直接制御する（datetime モックを回避）
        classified = {"critical": [], "warning": [(credits[0], 5)], "info": []}
        with patch("expiry_checker.handler.get_credits", return_value=credits), \
             patch("expiry_checker.handler._classify_expiring_credits", return_value=classified), \
             patch("expiry_checker.handler.get_channel_id", return_value="C0TEST1234"), \
             patch("expiry_checker.handler.post_message") as mock_post:
            from expiry_checker.handler import handler
            handler({}, None)
        mock_post.assert_called_once()

    def test_no_alert_when_no_expiring_credits(self, lambda_env):
        credits = [credit_expiring_in(45)]  # 30日を超えているので対象外
        # 全レベルが空 = 通知なし
        classified = {"critical": [], "warning": [], "info": []}
        with patch("expiry_checker.handler.get_credits", return_value=credits), \
             patch("expiry_checker.handler._classify_expiring_credits", return_value=classified), \
             patch("expiry_checker.handler.get_channel_id", return_value="C0TEST1234"), \
             patch("expiry_checker.handler.post_message") as mock_post:
            from expiry_checker.handler import handler
            handler({}, None)
        mock_post.assert_not_called()
