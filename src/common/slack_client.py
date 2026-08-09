"""
Slack chat.postMessage クライアント。
BR-07: SLACK_BOT_TOKEN_PARAM と SLACK_CHANNEL_ID_PARAM が未設定の場合は ValueError を送出する。
BR-10: OAuth トークンはログに出力してはならない。
"""
import logging
import os
import time

import requests

from common.secrets import get_parameter

logger = logging.getLogger(__name__)

SLACK_API_URL = "https://slack.com/api/chat.postMessage"
_REQUEST_TIMEOUT_SEC = 10
# Rate Limit (429) 時の最大リトライ回数
_RATE_LIMIT_MAX_RETRIES = 1


def post_message(channel_id: str, blocks: list, text: str = "") -> None:
    """
    Block Kit メッセージを Slack チャンネルへ chat.postMessage API で送信する。

    Args:
        channel_id: Slack チャンネル ID（例: "C0123456789"）。
        blocks: Slack Block Kit ペイロードのリスト。
        text: 通知プレビュー・アクセシビリティ用のフォールバックテキスト。

    Raises:
        ValueError: 必須環境変数が未設定の場合 (BR-07)。
        SlackApiError: HTTP エラーまたは Slack API エラーレスポンスの場合。
    """
    token = _get_token()

    payload = {
        "channel": channel_id,
        "blocks": blocks,
        "text": text,
    }

    # BR-10: トークンはヘッダーに使用するがログには出力しない
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
        response = requests.post(
            SLACK_API_URL,
            headers=headers,
            json=payload,
            timeout=_REQUEST_TIMEOUT_SEC,
        )

        # Rate Limit 超過時は Retry-After ヘッダーの秒数だけ待機してリトライする
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "1"))
            if attempt < _RATE_LIMIT_MAX_RETRIES:
                logger.warning(
                    "Slack rate-limited (429); retrying after %ds.", retry_after
                )
                time.sleep(retry_after)
                continue
            raise SlackApiError(f"Rate limited after {attempt + 1} attempt(s)")

        response.raise_for_status()

        body = response.json()
        if not body.get("ok"):
            error_code = body.get("error", "unknown_error")
            raise SlackApiError(f"Slack API error: {error_code}")

        logger.info("Slack message sent to channel %s.", channel_id)
        return


def _get_token() -> str:
    """
    SSM Parameter Store から Slack ボット OAuth トークンを取得する (BR-07, BR-10)。

    Returns:
        Slack ボットトークン文字列。

    Raises:
        ValueError: SLACK_BOT_TOKEN_PARAM が未設定の場合。
    """
    param_name = os.environ.get("SLACK_BOT_TOKEN_PARAM")
    if not param_name:
        raise ValueError(
            "SLACK_BOT_TOKEN_PARAM environment variable is required but not set."
        )
    # BR-10: トークン値は返すがログには出力しない
    return get_parameter(param_name)


def get_channel_id() -> str:
    """
    SSM Parameter Store または環境変数から Slack チャンネル ID を取得する (BR-07)。

    SLACK_CHANNEL_ID が直接設定されている場合はそれを使用する。
    未設定の場合は SLACK_CHANNEL_ID_PARAM で指定されたパラメータ名から取得する。

    Returns:
        Slack チャンネル ID 文字列。

    Raises:
        ValueError: SLACK_CHANNEL_ID も SLACK_CHANNEL_ID_PARAM も未設定の場合。
    """
    # 直接値が設定されていればそれを使用する（テスト時など）
    channel_id = os.environ.get("SLACK_CHANNEL_ID")
    if channel_id:
        return channel_id

    # SSM パラメータから取得する
    param_name = os.environ.get("SLACK_CHANNEL_ID_PARAM")
    if not param_name:
        raise ValueError(
            "Either SLACK_CHANNEL_ID or SLACK_CHANNEL_ID_PARAM environment variable is required."
        )
    return get_parameter(param_name)


class SlackApiError(Exception):
    """Slack API がエラーレスポンスを返した場合に送出される例外。"""
    pass
