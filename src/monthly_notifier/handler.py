"""
月次クレジット残高レポート Lambda ハンドラー。
EventBridge Scheduler のトリガー: cron(0 9 1 * ? *)
FR-01, FR-02, FR-03
BR-01: ACTIVE クレジットのみ対象。
BR-02: remainingAmount を合算して残高合計を算出する。
BR-11: nearest_expiry = ACTIVE クレジット中の最小 endDate。
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from common.billing_client import get_credits
from common.credit_utils import get_currency, get_remaining_amount, is_active_credit, parse_date
from common.slack_client import SlackApiError, get_channel_id, post_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> None:
    """
    Lambda エントリーポイント — 月次クレジットレポートを Slack に送信する。

    Args:
        event: EventBridge Scheduler イベントペイロード（内容は無視）。
        context: Lambda コンテキストオブジェクト。

    Raises:
        Exception: DLQ へ退避させるため例外をそのまま伝播する。
    """
    account_id = os.environ["AWS_ACCOUNT_ID"]
    channel_id = get_channel_id()

    # FR-01: クレジット残高一覧を取得する（管理アカウント配下のクレジットを集約）
    credits = get_credits(account_id, payer_flag=True)

    # Block Kit ペイロードを構築して送信する
    now = datetime.now(tz=timezone.utc)
    summary = _summarize_credits(credits)
    blocks = _build_monthly_blocks(summary)

    report_month = now.strftime("%-m月") if os.name != "nt" else now.strftime("%m月")
    fallback = f"月次AWSクレジットレポート（{now.year}年{report_month}）"

    try:
        post_message(channel_id, blocks, text=fallback)
    except SlackApiError as exc:
        logger.error("Failed to send monthly report: %s", exc)
        raise


def _summarize_credits(credits: list) -> dict:
    """
    ACTIVE クレジットを集計して残高合計・件数・最短期限を返す (BR-01, BR-02, BR-11)。

    Returns:
        以下のキーを持つ dict:
          total_remaining: ACTIVE クレジットの残高合計 (float)
          currency: 通貨コード (str)
          credit_count: ACTIVE クレジット件数 (int)
          nearest_expiry: 最短期限日 (date | None)
          nearest_credit_id: 最短期限クレジットの ID (str | None)
    """
    # BR-01: ENABLED かつ有効期限内のクレジットのみを対象にする
    active = [c for c in credits if is_active_credit(c)]

    # BR-02: remainingAmount（確定残高）と estimatedAmount（推定残高）を集計する
    total_remaining = sum(get_remaining_amount(c) for c in active)
    total_estimated = sum(
        float(c.get("estimatedAmount", {}).get("currencyAmount", "0")) for c in active
    )
    total_used = total_remaining - total_estimated  # 未確定の使用見込み = 確定残高 - 推定残高

    # 通貨コードを取得する
    currency = get_currency(active[0]) if active else "USD"

    nearest_credit = min(active, key=lambda c: parse_date(c.get("endDate"))) if active else None

    return {
        "total_remaining": total_remaining,
        "total_estimated": total_estimated,
        "total_used": total_used,
        "currency": currency,
        "credit_count": len(active),
        "nearest_expiry": parse_date(nearest_credit["endDate"]).date() if nearest_credit else None,
        "nearest_credit_id": nearest_credit.get("creditId") if nearest_credit else None,
    }


def _build_monthly_blocks(summary: dict) -> list:
    """月次クレジットレポート用の Slack Block Kit ペイロードを構築する。"""
    now = datetime.now(tz=timezone.utc)
    header_text = f"📊 月次AWSクレジットレポート（{now.year}年{now.month}月）"

    nearest_expiry_str = (
        str(summary["nearest_expiry"]) if summary["nearest_expiry"] else "N/A"
    )
    nearest_id_str = summary["nearest_credit_id"] or "N/A"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text},
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*残高合計（確定）*\n`${summary['total_remaining']:,.2f} {summary['currency']}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*推定残高（未確定分を反映）*\n`${summary['total_estimated']:,.2f} {summary['currency']}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*未確定の使用見込み*\n`${summary['total_used']:,.2f} {summary['currency']}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*アクティブクレジット数*\n`{summary['credit_count']}件`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*有効期限最短*\n`{nearest_expiry_str}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*最短期限クレジットID*\n`{nearest_id_str}`",
                },
            ],
        },
        {"type": "divider"},
    ]

    # 次回通知日を計算してフッターに表示する
    next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"自動生成 | 次回通知: {next_month.strftime('%Y-%m-01')} 09:00 UTC",
                }
            ],
        }
    )

    return blocks
