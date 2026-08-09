# Business Rules — Unit-1: Lambda Application

## BR-01: アクティブクレジットの定義

**ルール**: `creditStatus == "ACTIVE"` のクレジットのみを残高集計・期限チェックの対象とする。

**適用箇所**: `monthly_notifier`（残高集計）、`threshold_checker`（閾値判定）、`expiry_checker`（期限分類）

**実装**:
```python
active_credits = [c for c in credits if c['creditStatus'] == 'ACTIVE']
```

---

## BR-02: 残高合計の集計

**ルール**: アクティブクレジットの `remainingAmount.amount` を合算して総残高を算出する。
通貨は USD 統一とする（複数通貨が混在する場合は警告ログを出力する）。

**適用箇所**: `monthly_notifier`（`_summarize_credits`）、`threshold_checker`

**実装**:
```python
total = sum(c['remainingAmount']['amount'] for c in active_credits)
```

---

## BR-03: 閾値判定

**ルール**: `total_remaining < THRESHOLD_AMOUNT` の場合にアラートを送信する。
`THRESHOLD_AMOUNT` は環境変数から取得し、デフォルトは `1000.0`（USD）とする。
閾値以下が継続する場合も毎日アラートを送信する（状態管理なし）。

**適用箇所**: `threshold_checker`

**実装**:
```python
threshold = float(os.environ.get('THRESHOLD_AMOUNT', '1000.0'))
should_alert = total_remaining < threshold
```

---

## BR-04: 期限切れ分類の境界値

**ルール**: アクティブかつ `remainingAmount > 0` のクレジットについて、
`endDate` までの残日数で以下に分類する。

| レベル | 条件 | 絵文字 |
|---|---|---|
| critical | `days_left == 0`（当日） | 🔴 |
| warning | `1 <= days_left <= 7` | 🟡 |
| info | `8 <= days_left <= 30` | 🔵 |
| 対象外 | `days_left > 30` または `days_left < 0` | — |

**残日数の計算**: `days_left = (endDate.date() - today).days`

**適用箇所**: `expiry_checker`（`_classify_expiring_credits`）

---

## BR-05: 期限切れ通知の対象絞り込み

**ルール**: 以下の条件を**すべて**満たすクレジットのみを期限切れチェックの対象とする。
1. `creditStatus == "ACTIVE"`
2. `remainingAmount.amount > 0`
3. `0 <= days_left <= 30`

**適用箇所**: `expiry_checker`

---

## BR-06: partialResults 時の動作

**ルール**: `GetCreditAllocationHistory` のレスポンスで `partialResults == True` の場合、
通知メッセージ内に警告セクションを追加して送信する。通知は中止しない。

**警告テキスト**: `⚠️ 一部の月データの取得に失敗しました。履歴データが不完全な可能性があります。`
`failedMonths` が空でない場合、失敗月のリストも合わせて表示する。

**適用箇所**: `monthly_notifier`

---

## BR-07: Slack チャンネル設定

**ルール**: 全 Lambda 関数（monthly / threshold / expiry）は同一の環境変数
`SLACK_CHANNEL_ID` から送信先チャンネルを取得する。
値が未設定の場合は `ValueError` を raise して Lambda を失敗させる。

**適用箇所**: 全 Lambda（`common/slack_client.py` の初期化時に検証）

---

## BR-08: Billing API リトライポリシー

**ルール**: `ThrottlingException` が発生した場合、指数バックオフでリトライする。

| リトライ回数 | 待機秒数 |
|---|---|
| 1回目 | 1秒 |
| 2回目 | 2秒 |
| 3回目 | 4秒 |
| 4回目 | 8秒 |
| 5回目 | 16秒 |
| 6回目以降 | 上限32秒で打ち切り、例外 raise |

**適用箇所**: `common/billing_client.py`（`_retry_with_backoff`）

---

## BR-09: Secrets Manager シークレット構造

**ルール**: Secrets Manager のシークレット値は以下の JSON 形式とする。

```json
{
  "slack_bot_token": "xoxb-...",
  "slack_channel_id": "C0123456789"
}
```

`SLACK_SECRET_ARN` 環境変数にシークレット ARN を設定する。
`SLACK_CHANNEL_ID` 環境変数が設定されていない場合は、シークレット内の `slack_channel_id` を使用する。

**適用箇所**: `common/secrets.py`、`common/slack_client.py`

---

## BR-10: ログ出力ルール

**ルール**: 以下の情報はログに出力してはならない。
- Slack OAuth Token 値
- Secrets Manager から取得した生の JSON 値
- AWS アカウント ID（CloudWatch Logs は IAM で保護されているが念のため）

**適用箇所**: 全コンポーネント

---

## BR-11: 最短期限クレジットの選定

**ルール**: `CreditSummary.nearest_expiry` は、アクティブクレジットの中で
`endDate` が最も早いクレジットの `endDate.date()` とする。
該当クレジットが存在しない場合は `None` とする。

**適用箇所**: `monthly_notifier`（`_summarize_credits`）
