"""
AWS Credits API のレスポンス処理共通ユーティリティ。

実 API のレスポンスでは日付が "2027-11-30 23:59:59+00:00"（スペース区切り）で返る。
Python の datetime.fromisoformat() は "T" 区切りを期待するため、
normalize_date_str() でスペースを T に変換してからパースする必要がある。
"""
from datetime import datetime, timezone


def parse_date(value) -> datetime:
    """
    AWS API が返す日付値を UTC の datetime に変換する。

    対応フォーマット:
      - "2027-11-30 23:59:59+00:00"  （実 API のスペース区切り形式）
      - "2027-11-30T23:59:59+00:00"  （ISO-8601 T 区切り形式）
      - "2027-11-30T23:59:59Z"        （Z 末尾形式）
      - Unix エポック秒（int/float）
      - datetime オブジェクト（そのまま返す）

    Args:
        value: 日付を表す値。

    Returns:
        UTC タイムゾーン付きの datetime。パース失敗時は datetime.min を返す。
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str) and value:
        # スペース区切りと Z 末尾を正規化してからパースする
        normalized = value.replace(" ", "T").replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def is_active_credit(credit: dict, now: datetime | None = None) -> bool:
    """
    クレジットが現在有効かどうか判定する（BR-01）。

    条件:
      - creditStatus == "ENABLED"
      - endDate が現在日時より未来

    Args:
        credit: GetCredits API が返す CreditData dict。
        now: 判定基準日時（省略時は UTC 現在時刻）。

    Returns:
        有効な場合 True。
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    if credit.get("creditStatus") != "ENABLED":
        return False
    end_dt = parse_date(credit.get("endDate", ""))
    return end_dt >= now  # 当日期限切れ（days_left == 0）も有効として扱う


def get_remaining_amount(credit: dict) -> float:
    """
    クレジットの確定残高を float で返す（BR-02）。

    実 API では remainingAmount.currencyAmount が文字列で返る。

    Args:
        credit: GetCredits API が返す CreditData dict。

    Returns:
        残高（float）。取得できない場合は 0.0。
    """
    return float(credit.get("remainingAmount", {}).get("currencyAmount", "0"))


def get_currency(credit: dict) -> str:
    """
    クレジットの通貨コードを返す。

    Args:
        credit: GetCredits API が返す CreditData dict。

    Returns:
        通貨コード文字列（例: "USD"）。取得できない場合は "USD"。
    """
    return credit.get("remainingAmount", {}).get("currencyCode", "USD")
