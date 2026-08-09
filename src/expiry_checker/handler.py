"""
日次クレジット期限切れチェック Lambda ハンドラー。
EventBridge Scheduler のトリガー: cron(0 1 * * ? *)
FR-05
BR-01: ACTIVE クレジットのみ対象。
BR-04: critical=0日, warning=1〜7日, info=8〜30日。
BR-05: remainingAmount > 0 のクレジットのみ対象。
"""
import logging
import os
from datetime import date, datetime, timezone

from common.billing_client import get_credits
from common.credit_utils import get_remaining_amount, is_active_credit, parse_date
from common.slack_client import SlackApiError, get_channel_id, post_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> None:
    """
    Lambda エントリーポイント — 期限切れ間近のクレジットを分類して Slack アラートを送信する。

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

    today = datetime.now(tz=timezone.utc).date()
    # BR-04, BR-05 に基づいてクレジットを期限レベルで分類する
    classified = _classify_expiring_credits(credits, today)

    total_flagged = (
        len(classified["critical"])
        + len(classified["warning"])
        + len(classified["info"])
    )

    if total_flagged > 0:
        logger.info(
            "Found %d expiring credit(s): critical=%d, warning=%d, info=%d.",
            total_flagged,
            len(classified["critical"]),
            len(classified["warning"]),
            len(classified["info"]),
        )
        blocks = _build_expiry_blocks(classified, today)
        try:
            post_message(channel_id, blocks, text="クレジット期限切れアラート")
        except SlackApiError as exc:
            logger.error("Failed to send expiry alert: %s", exc)
            raise
    else:
        logger.info("No expiring credits found within 30 days.")


def _classify_expiring_credits(credits: list, today: date) -> dict:
    """
    残日数に基づいてクレジットを期限切れレベルで分類する (BR-04, BR-05)。

    ACTIVE かつ remainingAmount > 0 かつ 0 <= 残日数 <= 30 のクレジットのみを対象とする。

    Returns:
        'critical', 'warning', 'info' をキーとする dict。
        各値は (credit, days_left) タプルのリスト。
    """
    result: dict = {"critical": [], "warning": [], "info": []}

    for credit in credits:
        # BR-01, BR-05: ENABLED かつ有効期限内かつ remainingAmount > 0 のみ対象
        if not is_active_credit(credit):
            continue
        remaining_amount = get_remaining_amount(credit)
        if remaining_amount <= 0:
            continue

        end_date_raw = credit.get("endDate")
        if not end_date_raw:
            continue

        end_date = parse_date(end_date_raw).date()
        days_left = (end_date - today).days

        # BR-04: 残日数に基づいてレベルを決定する
        if days_left == 0:
            result["critical"].append((credit, days_left))
        elif 1 <= days_left <= 7:
            result["warning"].append((credit, days_left))
        elif 8 <= days_left <= 30:
            result["info"].append((credit, days_left))
        # 残り31日以上または既に期限切れの場合はスキップする

    return result


def _build_expiry_blocks(classified: dict, today: date) -> list:
    """期限切れアラート用の Slack Block Kit ペイロードを構築する。"""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🔔 クレジット期限切れアラート"},
        },
        {"type": "divider"},
    ]

    # 各レベルのラベルと絵文字を定義する
    level_config = [
        ("critical", "🔴 CRITICAL（当日期限切れ）"),
        ("warning", "🟡 WARNING（7日以内）"),
        ("info", "🔵 INFO（30日以内）"),
    ]

    for level_key, level_label in level_config:
        items = classified[level_key]
        # 該当クレジットが存在するレベルのみセクションを追加する
        if not items:
            continue

        lines = []
        for credit, days_left in items:
            cid = credit.get("creditId", "N/A")
            remaining = credit.get("remainingAmount", {})
            amt = f"${float(remaining.get('currencyAmount', '0')):,.2f} {remaining.get('currencyCode', 'USD')}"
            end_date = credit.get("endDate", "N/A")
            if level_key == "critical":
                lines.append(f"• `{cid}` — {amt} (期限: {end_date})")
            else:
                lines.append(f"• `{cid}` — {amt} (期限: {end_date}, 残り{days_left}日)")

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{level_label}*\n" + "\n".join(lines),
                },
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"自動検知 | {today.isoformat()} 01:00 UTC チェック",
                }
            ],
        }
    )

    return blocks
