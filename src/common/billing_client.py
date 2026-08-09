"""
AWS Billing API クライアント。
指数バックオフリトライとページネーションをサポートする。
BR-08: ThrottlingException → 指数バックオフ（初回1秒、上限32秒、最大6回）。
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# リトライ設定 (BR-08)
_MAX_RETRIES = 6
_BASE_WAIT_SEC = 1
_MAX_WAIT_SEC = 32

_billing_client = None


def _get_client():
    """キャッシュ済みの Billing API Boto3 クライアントを返す（us-east-1 固定エンドポイント）。"""
    global _billing_client
    if _billing_client is None:
        _billing_client = boto3.client("billing", region_name="us-east-1")
    return _billing_client


def get_credits(
    account_id: str,
    start_date: Optional[datetime] = None,
    payer_flag: bool = False,
) -> list:
    """
    billing:GetCredits を呼び出してクレジット一覧を取得する。

    Args:
        account_id: 12桁の AWS アカウント ID 文字列。
        start_date: 取得対象の最古のクレジット開始日。省略時は365日前。
        payer_flag: True の場合、Consolidated Billing 配下のクレジットを集約する。

    Returns:
        API レスポンスの CreditData dict のリスト。

    Raises:
        ClientError: ThrottlingException のリトライ上限超過、またはその他のエラー発生時。
    """
    if start_date is None:
        start_date = datetime.now(tz=timezone.utc) - timedelta(days=365)

    params = {
        "accountId": account_id,
        "startDate": int(start_date.timestamp()),
        "payerAccountFlag": payer_flag,
    }

    response = _retry_with_backoff(
        lambda: _get_client().get_credits(**params),
        operation="GetCredits",
    )
    return response.get("credits", [])


def get_credit_allocation_history(
    account_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    credit_id: Optional[str] = None,
) -> tuple[list, bool, list]:
    """
    billing:GetCreditAllocationHistory をページネーション込みで呼び出す。

    Args:
        account_id: 12桁の AWS アカウント ID 文字列。
        start_date: 履歴取得ウィンドウの開始日。省略時は90日前。
        end_date: 履歴取得ウィンドウの終了日。省略時は現在日時。
        credit_id: 特定クレジットへのフィルタ（省略可）。

    Returns:
        (records, partial_results, failed_months) のタプル:
            records: CreditAllocationHistory dict のリスト。
            partial_results: 一部月のデータ取得失敗時に True (BR-06)。
            failed_months: 取得失敗した請求月文字列のリスト。
    """
    if start_date is None:
        start_date = datetime.now(tz=timezone.utc) - timedelta(days=90)
    if end_date is None:
        end_date = datetime.now(tz=timezone.utc)

    all_records: list = []
    next_token: Optional[str] = None
    partial_results = False
    failed_months: list = []

    while True:
        params: dict = {
            "accountId": account_id,
            "startDate": int(start_date.timestamp()),
            "endDate": int(end_date.timestamp()),
            "maxResults": 1000,
        }
        if credit_id:
            params["creditId"] = credit_id
        if next_token:
            params["nextToken"] = next_token

        response = _retry_with_backoff(
            lambda p=params: _get_client().get_credit_allocation_history(**p),
            operation="GetCreditAllocationHistory",
        )

        all_records.extend(response.get("creditAllocationHistoryList", []))
        partial_results = response.get("partialResults", False)
        failed_months = response.get("failedMonths", [])

        # データ完全性の警告ログを出力する (BR-06)
        if partial_results:
            logger.warning(
                "partialResults=True for GetCreditAllocationHistory; "
                "failedMonths=%s",
                failed_months,
            )

        next_token = response.get("nextToken")
        if not next_token:
            break

    return all_records, partial_results, failed_months


def _retry_with_backoff(func, operation: str = "BillingAPI"):
    """
    ThrottlingException 発生時に指数バックオフでリトライするラッパー関数 (BR-08)。

    Args:
        func: Boto3 API 呼び出しをラップするゼロ引数のコーラブル。
        operation: ログメッセージ用のオペレーション名。

    Returns:
        成功した API レスポンス dict。

    Raises:
        ClientError: 全リトライ消耗時、またはスロットリング以外のエラー発生時。
    """
    wait = _BASE_WAIT_SEC
    for attempt in range(_MAX_RETRIES):
        try:
            return func()
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code != "ThrottlingException":
                raise
            if attempt == _MAX_RETRIES - 1:
                logger.error(
                    "%s: ThrottlingException after %d retries — giving up.",
                    operation,
                    _MAX_RETRIES,
                )
                raise
            sleep_sec = min(wait, _MAX_WAIT_SEC)
            logger.warning(
                "%s: ThrottlingException on attempt %d/%d — retrying in %ds.",
                operation,
                attempt + 1,
                _MAX_RETRIES,
                sleep_sec,
            )
            time.sleep(sleep_sec)
            wait *= 2
