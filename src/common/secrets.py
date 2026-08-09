"""
SSM Parameter Store ユーティリティ。
Lambda Extension キャッシュ（高速パス）と Boto3 直接取得（フォールバック）をサポートする。
BR-10: パラメータ値はログに出力してはならない。
"""
import logging
import os
from urllib.parse import quote

import boto3
import requests

logger = logging.getLogger(__name__)

# Lambda Extension のローカルエンドポイント（SSM Parameters and Secrets Extension）
_EXTENSION_BASE_URL = "http://localhost:2773"
_EXTENSION_TIMEOUT_SEC = 1.0


def get_parameter(param_name: str, region: str | None = None) -> str:
    """
    SSM Parameter Store からパラメータ値を取得する。
    Lambda Extension キャッシュを優先し、利用不可の場合は Boto3 にフォールバックする。

    Args:
        param_name: SSM パラメータ名（例: /blogsummary/slack_bot_token）。
        region: パラメータが存在するリージョン（省略時は Lambda デプロイリージョン）。

    Returns:
        パラメータ値の文字列。

    Raises:
        RuntimeError: いずれの方法でも取得できない場合。
    """
    try:
        return _get_via_extension(param_name)
    except Exception as ext_err:
        logger.warning(
            "Lambda Extension unavailable (%s); falling back to SSM API.",
            type(ext_err).__name__,
        )
        return _get_via_boto3(param_name, region)


def _get_via_extension(param_name: str) -> str:
    """Lambda Parameters and Secrets Extension 経由で SSM パラメータを取得する。"""
    session_token = os.environ.get("AWS_SESSION_TOKEN", "")
    # パラメータ名を URL エンコードしてクエリに含める
    encoded_name = quote(param_name, safe="")
    url = f"{_EXTENSION_BASE_URL}/systemsmanager/parameters/get?name={encoded_name}&withDecryption=true"
    response = requests.get(
        url,
        headers={"X-Aws-Parameters-Secrets-Token": session_token},
        timeout=_EXTENSION_TIMEOUT_SEC,
    )
    response.raise_for_status()
    # BR-10: レスポンスボディをログに出力しない
    return response.json()["Parameter"]["Value"]


def _get_via_boto3(param_name: str, region: str | None = None) -> str:
    """Boto3 SSM クライアントで直接パラメータを取得する（フォールバック）。"""
    kwargs: dict = {"region_name": region} if region else {}
    client = boto3.client("ssm", **kwargs)
    response = client.get_parameter(Name=param_name, WithDecryption=True)
    # BR-10: レスポンスボディをログに出力しない
    return response["Parameter"]["Value"]
