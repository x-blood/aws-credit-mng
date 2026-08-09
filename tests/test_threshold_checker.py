"""
Unit tests for threshold_checker/handler.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import patch

import pytest

from threshold_checker.handler import _build_threshold_blocks, _check_threshold
from tests.conftest import make_credit


# ---------------------------------------------------------------------------
# _check_threshold (BR-03)
# ---------------------------------------------------------------------------

class TestCheckThreshold:
    def test_below_threshold_returns_true(self):
        assert _check_threshold(999.99, 1000.0) is True

    def test_equal_to_threshold_returns_false(self):
        assert _check_threshold(1000.0, 1000.0) is False  # strictly less-than

    def test_above_threshold_returns_false(self):
        assert _check_threshold(1500.0, 1000.0) is False

    def test_zero_balance_returns_true(self):
        assert _check_threshold(0.0, 1000.0) is True


# ---------------------------------------------------------------------------
# _build_threshold_blocks
# ---------------------------------------------------------------------------

class TestBuildThresholdBlocks:
    def test_contains_header(self):
        blocks = _build_threshold_blocks([], 500.0, 1000.0)
        assert any(b["type"] == "header" for b in blocks)

    def test_shows_shortfall(self):
        blocks = _build_threshold_blocks([], 500.0, 1000.0)
        all_text = str(blocks)
        assert "500" in all_text  # shortfall = 1000 - 500

    def test_lists_top_5_credits(self):
        credits = [make_credit(f"cr-{i:03d}", remaining=float(100 * i)) for i in range(1, 8)]
        blocks = _build_threshold_blocks(credits, 300.0, 1000.0)
        all_text = str(blocks)
        assert "cr-001" in all_text
        assert "cr-005" in all_text
        assert "cr-006" not in all_text  # capped at 5


# ---------------------------------------------------------------------------
# handler integration (mocked dependencies)
# ---------------------------------------------------------------------------

class TestThresholdHandler:
    def test_sends_alert_when_below_threshold(self, lambda_env):
        credits = [make_credit(remaining=500.0)]
        with patch("threshold_checker.handler.get_credits", return_value=credits), \
             patch("threshold_checker.handler.get_channel_id", return_value="C0TEST1234"), \
             patch("threshold_checker.handler.post_message") as mock_post:
            from threshold_checker.handler import handler
            handler({}, None)
        mock_post.assert_called_once()

    def test_no_alert_when_above_threshold(self, lambda_env):
        credits = [make_credit(remaining=5000.0)]
        with patch("threshold_checker.handler.get_credits", return_value=credits), \
             patch("threshold_checker.handler.get_channel_id", return_value="C0TEST1234"), \
             patch("threshold_checker.handler.post_message") as mock_post:
            from threshold_checker.handler import handler
            handler({}, None)
        mock_post.assert_not_called()

    def test_excludes_inactive_credits_from_total(self, lambda_env):
        credits = [
            make_credit("cr-001", status="ENABLED", remaining=500.0),
            make_credit("cr-002", status="DISABLED", remaining=9999.0),
        ]
        with patch("threshold_checker.handler.get_credits", return_value=credits), \
             patch("threshold_checker.handler.get_channel_id", return_value="C0TEST1234"), \
             patch("threshold_checker.handler.post_message") as mock_post:
            from threshold_checker.handler import handler
            handler({}, None)
        # Total ACTIVE = 500 < 1000 → alert should fire
        mock_post.assert_called_once()
