"""
Shared pytest fixtures for Unit-1 Lambda tests.
"""
import os

import boto3
import pytest
from moto import mock_aws


# ---------------------------------------------------------------------------
# Environment variable fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def aws_credentials():
    """Set fake AWS credentials so moto intercepts all boto3 calls."""
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture()
def lambda_env(monkeypatch):
    """Set required Lambda environment variables."""
    monkeypatch.setenv("AWS_ACCOUNT_ID", "123456789012")
    monkeypatch.setenv("SLACK_BOT_TOKEN_PARAM", "/credit-notifier/slack-bot-token")
    monkeypatch.setenv("SLACK_CHANNEL_ID_PARAM", "/credit-notifier/slack-channel-id")
    monkeypatch.setenv("THRESHOLD_AMOUNT", "1000.0")
    monkeypatch.setenv("MONTHS_BACK", "3")


# ---------------------------------------------------------------------------
# Secrets Manager fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def secrets_manager_with_slack(lambda_env):
    """
    Create a real moto-backed Secrets Manager secret containing Slack credentials.
    Patches common.secrets._get_via_boto3 path (Extension not available in tests).
    """
    import json
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_arn = os.environ["SLACK_SECRET_ARN"]
        client.create_secret(
            Name="credit-notifier/slack",
            SecretString=json.dumps({
                "slack_bot_token": "xoxb-test-token",
                "slack_channel_id": "C0TEST1234",
            }),
        )
        yield client


# ---------------------------------------------------------------------------
# Sample credit data helpers
# ---------------------------------------------------------------------------

def make_credit(
    credit_id: str = "cr-001",
    status: str = "ENABLED",
    remaining: float = 5000.0,
    end_date: str = "2026-12-31 00:00:00+00:00",  # 実 API のスペース区切り形式に合わせる
) -> dict:
    """Return a minimal CreditData dict for testing."""
    return {
        "creditId": credit_id,
        "creditStatus": status,
        "remainingAmount": {"currencyCode": "USD", "currencyAmount": str(remaining)},
        "estimatedAmount": {"currencyCode": "USD", "currencyAmount": str(remaining)},
        "initialAmount": {"currencyCode": "USD", "currencyAmount": str(remaining)},
        "startDate": "2026-01-01 00:00:00+00:00",
        "endDate": end_date,
        "applicableProductNames": ["Amazon EC2"],
        "description": "Test credit",
    }


def make_history_record(
    credit_id: str = "cr-001",
    billing_month: str = "2026-06",
    amount: float = 100.0,
    is_estimated: bool = False,
) -> dict:
    """Return a minimal CreditAllocationHistory dict for testing."""
    return {
        "accountId": "123456789012",
        "creditId": credit_id,
        "billingMonth": billing_month,
        "appliedServiceName": "Amazon EC2",
        "creditAmount": {"currencyCode": "USD", "currencyAmount": str(amount)},
        "isEstimatedBill": is_estimated,
        "description": "Test allocation",
    }
