# Functional Design Plan — Unit-1: Lambda Application

## 対象ユニット
Unit-1: Lambda Application（Python 3.12）

## Plan Checkboxes
- [x] ユニットコンテキスト分析
- [x] 質問作成
- [x] ユーザー回答収集
- [x] 回答の矛盾・曖昧さ分析
- [x] business-logic-model.md 生成
- [x] business-rules.md 生成
- [x] domain-entities.md 生成

---

## 確定済みの設計内容（Application Design / 要件定義より）

以下は既に確定しており、質問不要：
- Lambda 3関数分離（monthly / threshold / expiry）
- `common/billing_client.py`：指数バックオフリトライ、ページネーション、partialResults 検証
- `common/slack_client.py`：chat.postMessage API、OAuth Token
- `common/secrets.py`：Lambda Extension キャッシュ
- DLQ：例外 raise → Lambda が SQS DLQ に自動退避

---

## Question 1: 月次通知の残高集計ロジック

月次レポートで「残高合計」を集計する際の対象クレジットを選択してください。

A) 全クレジット（`creditStatus` に関わらず全件）の `remainingAmount` を合算

B) アクティブなクレジットのみ（`creditStatus == "ACTIVE"` のみ）の `remainingAmount` を合算

C) `remainingAmount` と `estimatedAmount` を両方表示（確定残高 + 見込み残高として並列表示）

D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 2: 閾値チェックの通知頻度制御

毎日残高が閾値を下回り続ける場合、アラートの通知頻度をどう制御しますか？

A) 毎日通知（閾値を下回っている限り毎日アラート送信、DynamoDB等の状態管理なし）

B) 初回のみ通知（閾値を下回った最初の1回のみ送信し、残高が回復するまで再通知しない。DynamoDB などで状態管理が必要）

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3: 期限切れ分類の境界値定義

`expiry_checker` の期限分類における「〇日以内」の境界値を確認してください。

A) critical: 残り 0日（当日）、warning: 残り 1〜7日、info: 残り 8〜30日

B) critical: 残り 0〜1日（当日・翌日）、warning: 残り 2〜7日、info: 残り 8〜30日

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4: 期限切れアラートの通知対象

`expiry_checker` で通知する際、既に残高が0になったクレジットを対象に含めますか？

A) 含めない（`remainingAmount > 0` のクレジットのみ対象）

B) 含める（残高が0でも期限切れ間近であれば通知対象とする）

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 5: Slack 通知の送信先チャンネル

各Lambda関数が通知するSlackチャンネルの設定方法を選択してください。

A) 全通知を同一チャンネルへ（1つの環境変数 `SLACK_CHANNEL_ID` で全Lambda共通）

B) 通知タイプ別に別チャンネル（月次レポート用・アラート用を分けて設定）

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 6: partialResults 時の月次通知の扱い

`GetCreditAllocationHistory` の `partialResults = true`（一部データ欠損）の場合、月次通知をどう扱いますか？

A) 通知を送信し、メッセージ内に「⚠️ データが不完全です（一部月のデータ取得に失敗）」と明記する

B) 通知を中止し、DLQ に退避してアラートを上げる

C) Other (please describe after [Answer]: tag below)

[Answer]: A
