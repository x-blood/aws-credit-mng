"""
日次クレジット残高閾値チェック Lambda ハンドラー。
EventBridge Scheduler のトリガー: cron(0 0 * * ? *)
FR-04
BR-01: ENABLED かつ有効期限内のクレジットのみ対象。
BR-02: remainingAmount を合算して残高合計を算出する。
BR-03: 閾値を下回っている限り毎日アラートを送信する（状態管理なし）。
"""
import logging
import os
from datetime import datetime, timezone

from common.billing_client import get_credits
from common.credit_utils import get_remaining_amount, is_active_credit
from common.slack_client import SlackApiError, get_channel_id, post_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 閾値のデフォルト値（USD）
_DEFAULT_THRESHOLD = 20.0


def handler(event: dict, context) -> None:
    """
    Lambda エントリーポイント — 残高が閾値を下回った場合のみ Slack アラートを送信する (BR-03)。

    Args:
        event: EventBridge Scheduler イベントペイロード（内容は無視）。
        context: Lambda コンテキストオブジェクト。

    Raises:
        Exception: DLQ へ退避させるため例外をそのまま伝播する。
    """
    account_id = os.environ["AWS_ACCOUNT_ID"]
    # 環境変数から閾値を取得する（未設定時はデフォルト値を使用）
    threshold = float(os.environ.get("THRESHOLD_AMOUNT", str(_DEFAULT_THRESHOLD)))
    channel_id = get_channel_id()

    # FR-01: クレジット残高一覧を取得する（管理アカウント配下のクレジットを集約）
    credits = get_credits(account_id, payer_flag=True)

    # BR-01: ENABLED かつ有効期限内のクレジットのみを対象にする
    active = [c for c in credits if is_active_credit(c)]

    # BR-02: remainingAmount を合算する
    total_remaining = sum(get_remaining_amount(c) for c in active)

    if _check_threshold(total_remaining, threshold):  # BR-03
        logger.warning(
            "Credit balance $%.2f is below threshold $%.2f — sending alert.",
            total_remaining,
            threshold,
        )
        blocks = _build_threshold_blocks(active, total_remaining, threshold)
        try:
            post_message(channel_id, blocks, text="クレジット残高アラート")
        except SlackApiError as exc:
            logger.error("Failed to send threshold alert: %s", exc)
            raise
    else:
        logger.info(
            "Credit balance $%.2f is above threshold $%.2f — no alert needed.",
            total_remaining,
            threshold,
        )


def _check_threshold(total_remaining: float, threshold: float) -> bool:
    """残高が閾値を厳密に下回っているか判定する (BR-03)。"""
    return total_remaining < threshold


def _build_threshold_blocks(
    active_credits: list, total_remaining: float, threshold: float
) -> list:
    """閾値アラート用の Slack Block Kit ペイロードを構築する。"""
    shortfall = threshold - total_remaining
    now = datetime.now(tz=timezone.utc)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⚠️ クレジット残高アラート"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*現在の残高*\n`${total_remaining:,.2f} USD`"},
                {"type": "mrkdwn", "text": f"*設定閾値*\n`${threshold:,.2f} USD`"},
                {"type": "mrkdwn", "text": f"*不足額*\n`${shortfall:,.2f} USD`"},
            ],
        },
    ]

    # アクティブクレジットの上位5件を表示する
    if active_credits:
        lines = []
        for credit in active_credits[:5]:
            cid = credit.get("creditId", "N/A")
            remaining = credit.get("remainingAmount", {})
            amt = f"${float(remaining.get('currencyAmount', '0')):,.2f} {remaining.get('currencyCode', 'USD')}"
            end_date = credit.get("endDate", "N/A")
            lines.append(f"• `{cid}` — {amt} (期限: {end_date})")

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*アクティブクレジット（上位5件）*\n" + "\n".join(lines),
                },
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"自動検知 | {now.strftime('%Y-%m-%d')} 00:00 UTC チェック",
                }
            ],
        }
    )

    return blocks
