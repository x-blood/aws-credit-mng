# Domain Entities — Unit-1: Lambda Application

## エンティティ一覧

### Credit（クレジット）

AWS Billing API の `GetCredits` レスポンスの `CreditData` オブジェクトに対応するドメインエンティティ。

```
Credit {
  creditId:             str        # クレジット一意識別子
  creditType:           str        # クレジット種別
  creditStatus:         str        # 状態: "ACTIVE" | "EXPIRED" | "EXHAUSTED" | 他
  initialAmount:        Money      # 初期金額
  remainingAmount:      Money      # 確定残高（24時間リフレッシュ）
  estimatedAmount:      Money      # 見込み残高
  startDate:            datetime   # 有効開始日
  endDate:              datetime   # 有効期限
  exhaustDate:          datetime?  # 使い切り日（使い切り済みの場合）
  applicableProductNames: list[str] # 適用対象サービス名
  creditSharingType:    str        # 共有タイプ
  description:          str        # 説明
}
```

### Money（金額）

金額と通貨コードのペア。

```
Money {
  amount:   float   # 金額（例: 1234.56）
  unit:     str     # 通貨コード（例: "USD"）
}
```

### CreditAllocationHistory（クレジット適用履歴）

AWS Billing API の `GetCreditAllocationHistory` レスポンスに対応するドメインエンティティ。

```
CreditAllocationHistory {
  accountId:          str       # AWSアカウントID
  appliedServiceName: str       # 適用されたサービス名
  billingMonth:       str       # 請求月（YYYY-MM形式）
  creditAmount:       Money     # 当月適用金額
  creditId:           str       # 対応クレジットID
  description:        str       # 説明
  isEstimatedBill:    bool      # 見込み請求かどうか
}
```

### CreditSummary（集計サマリー）

月次通知・閾値チェック用の集計結果。アプリ内部で生成するエンティティ。

```
CreditSummary {
  total_remaining:  Money      # アクティブクレジットの remainingAmount 合計
  credit_count:     int        # アクティブクレジット数
  nearest_expiry:   date?      # 最短の endDate（アクティブクレジット中）
  nearest_credit_id: str?      # 最短期限クレジットの ID
}
```

### ExpiryClassification（期限切れ分類）

`expiry_checker` が生成するクレジットの期限分類結果。

```
ExpiryClassification {
  critical: list[Credit]   # 残り 0日（endDate == today）
  warning:  list[Credit]   # 残り 1〜7日（1 <= days_left <= 7）
  info:     list[Credit]   # 残り 8〜30日（8 <= days_left <= 30）
}
```

### SlackMessage（Slack送信メッセージ）

Slack `chat.postMessage` API に渡す送信メッセージ。

```
SlackMessage {
  channel:  str         # Slack チャンネル ID（環境変数 SLACK_CHANNEL_ID）
  blocks:   list[dict]  # Block Kit ペイロード
  text:     str         # フォールバックテキスト（通知プレビュー用）
}
```

---

## エンティティ関係図

```
GetCredits API
    |
    v
list[Credit]
    |
    +---> CreditSummary        (月次通知・閾値チェックで使用)
    |         |
    |         +---> total_remaining (ACTIVE のみ集計)
    |         +---> nearest_expiry
    |
    +---> ExpiryClassification (期限切れチェックで使用)
              |
              +---> critical / warning / info グループ
                    (remainingAmount > 0 かつ 0〜30日以内)

GetCreditAllocationHistory API
    |
    v
list[CreditAllocationHistory]  (月次通知の適用履歴セクションで使用)

CreditSummary / ExpiryClassification / list[CreditAllocationHistory]
    |
    v
SlackMessage (Block Kit ペイロード)
    |
    v
Slack API
```
