# Business Logic Model — Unit-1: Lambda Application

## 1. monthly_notifier — 月次通知ロジック

### 処理フロー

```
handler(event, context)
  |
  +-- 1. get_credits(account_id, start_date=365日前)
  |         → list[Credit]
  |
  +-- 2. get_credit_allocation_history(account_id, start_date=90日前, end_date=now)
  |         → list[CreditAllocationHistory], partial_results: bool, failed_months: list
  |
  +-- 3. _summarize_credits(credits)
  |         → CreditSummary
  |         ルール: BR-01（ACTIVE のみ）、BR-02（残高集計）、BR-11（最短期限）
  |
  +-- 4. _build_monthly_blocks(summary, history, partial_results, failed_months)
  |         → list[dict] (Slack Block Kit)
  |         ルール: BR-06（partialResults 警告）
  |
  +-- 5. post_message(channel_id, blocks, text="月次AWSクレジットレポート")
  |         ルール: BR-07（チャンネル設定）
  |
  [例外発生時] → raise → Lambda が DLQ に退避
```

### _summarize_credits のロジック

```
入力: list[Credit]
1. active = [c for c in credits if c.creditStatus == "ACTIVE"]  (BR-01)
2. total_remaining = sum(c.remainingAmount.amount for c in active)  (BR-02)
3. credit_count = len(active)
4. nearest = min(active, key=lambda c: c.endDate) if active else None  (BR-11)
5. return CreditSummary(total_remaining, credit_count, nearest.endDate.date(), nearest.creditId)
```

### _build_monthly_blocks の Block Kit 構造

```
[header]  "📊 月次AWSクレジットレポート（YYYY年M月）"
[divider]
[section fields]
  - *残高合計（確定）*  `$X,XXX.XX`
  - *アクティブクレジット数*  `N件`
  - *有効期限最短*  `YYYY-MM-DD`（なければ "N/A"）
  - *最短期限クレジットID*  `cr-xxxxxx`（なければ "N/A"）
[divider]
[section] "📅 直近3ヶ月の適用履歴"
  - 月ごとに billingMonth / appliedServiceName / creditAmount を表示
  - isEstimatedBill == True の行には "(見込み)" を付記
[section] ⚠️ 警告（partial_results == True の場合のみ追加）  (BR-06)
  - "⚠️ 一部の月データの取得に失敗しました。履歴データが不完全な可能性があります。"
  - failed_months が空でなければ失敗月リストも表示
[context]
  "自動生成 | 次回通知: YYYY-MM-01 09:00 UTC"
```

---

## 2. threshold_checker — 残高閾値チェックロジック

### 処理フロー

```
handler(event, context)
  |
  +-- 1. threshold = float(os.environ.get("THRESHOLD_AMOUNT", "1000.0"))  (BR-03)
  |
  +-- 2. get_credits(account_id, start_date=365日前)
  |         → list[Credit]
  |
  +-- 3. active = [c for c in credits if c.creditStatus == "ACTIVE"]  (BR-01)
  |
  +-- 4. total_remaining = sum(c.remainingAmount.amount for c in active)  (BR-02)
  |
  +-- 5. if total_remaining < threshold:  (BR-03)
  |         _build_threshold_blocks(active, total_remaining, threshold)
  |         → list[dict]
  |         post_message(channel_id, blocks, text="クレジット残高アラート")
  |
  +-- 6. else: ログ出力のみ（"残高 $X,XXX.XX は閾値 $X,XXX.XX を上回っています"）
  |
  [例外発生時] → raise → Lambda が DLQ に退避
```

### _build_threshold_blocks の Block Kit 構造

```
[header]  "⚠️ クレジット残高アラート"
[divider]
[section fields]
  - *現在の残高*  `$X,XXX.XX`
  - *設定閾値*    `$X,XXX.XX`
  - *不足額*      `$X,XXX.XX`（threshold - total_remaining）
[section] アクティブクレジット一覧（上位5件まで）
  - creditId / remainingAmount / endDate
[context]
  "自動検知 | 毎日 00:00 UTC チェック"
```

---

## 3. expiry_checker — 期限切れチェックロジック

### 処理フロー

```
handler(event, context)
  |
  +-- 1. today = date.today()（UTC）
  |
  +-- 2. get_credits(account_id, start_date=365日前)
  |         → list[Credit]
  |
  +-- 3. _classify_expiring_credits(credits, today)
  |         → ExpiryClassification  (BR-04, BR-05)
  |
  +-- 4. classified に1件以上あれば:
  |         _build_expiry_blocks(classified)
  |         → list[dict]
  |         post_message(channel_id, blocks, text="クレジット期限切れアラート")
  |
  +-- 5. else: ログ出力のみ（"期限切れ間近のクレジットはありません"）
  |
  [例外発生時] → raise → Lambda が DLQ に退避
```

### _classify_expiring_credits のロジック

```
入力: list[Credit], today: date
1. filtered = [c for c in credits
               if c.creditStatus == "ACTIVE"
               and c.remainingAmount.amount > 0]          (BR-01, BR-05)
2. for c in filtered:
     days_left = (c.endDate.date() - today).days          (BR-04)
     if days_left == 0:    → critical
     elif 1 <= days_left <= 7: → warning
     elif 8 <= days_left <= 30: → info
     else: スキップ
3. return ExpiryClassification(critical, warning, info)
```

### _build_expiry_blocks の Block Kit 構造

```
[header]  "🔔 クレジット期限切れアラート"
[divider]
[section] 🔴 CRITICAL（当日期限切れ）— critical リストの各クレジット
  - creditId / remainingAmount / endDate
[section] 🟡 WARNING（7日以内）— warning リストの各クレジット
  - creditId / remainingAmount / endDate / 残り日数
[section] 🔵 INFO（30日以内）— info リストの各クレジット
  - creditId / remainingAmount / endDate / 残り日数
  ※ 各セクションは該当クレジットが1件以上ある場合のみ追加
[context]
  "自動検知 | 毎日 01:00 UTC チェック"
```

---

## 4. common/billing_client — Billing API クライアントロジック

### get_credits のロジック

```
入力: account_id, start_date (datetime), payer_flag=False
1. params = { accountId, startDate(unix epoch), payerAccountFlag }
2. _retry_with_backoff(lambda: billing_client.get_credits(**params))  (BR-08)
3. return response["credits"]
```

### get_credit_allocation_history のロジック

```
入力: account_id, start_date, end_date, credit_id=None
1. all_records = []
2. next_token = None
3. loop:
     params = { accountId, startDate, endDate, maxResults=1000 }
     if credit_id: params["creditId"] = credit_id
     if next_token: params["nextToken"] = next_token
     response = _retry_with_backoff(lambda: billing_client.get_credit_allocation_history(**params))
     all_records += response["creditAllocationHistoryList"]
     next_token = response.get("nextToken")
     if not next_token: break
4. partial = response.get("partialResults", False)
5. failed = response.get("failedMonths", [])
6. if partial: logger.warning(f"partialResults=True, failedMonths={failed}")
7. return all_records, partial, failed
```

### _retry_with_backoff のロジック

```
入力: func (callable), max_retries=6
1. wait = 1  # 秒
2. for attempt in range(max_retries):
     try: return func()
     except ThrottlingException:
       if attempt == max_retries - 1: raise
       time.sleep(min(wait, 32))
       wait *= 2
```

---

## 5. common/slack_client — Slack 通知クライアントロジック

### post_message のロジック

```
入力: channel_id, blocks, text=""
1. token = _get_token()
2. payload = { "channel": channel_id, "blocks": blocks, "text": text }
3. response = requests.post(
     "https://slack.com/api/chat.postMessage",
     headers={"Authorization": f"Bearer {token}"},
     json=payload,
     timeout=10
   )
4. if response.status_code == 429:
     retry_after = int(response.headers.get("Retry-After", "1"))
     time.sleep(retry_after)
     → 1回のみリトライ
5. response.raise_for_status()
6. body = response.json()
7. if not body.get("ok"):
     raise SlackApiError(body.get("error", "unknown"))
```

### _get_token のロジック

```
1. secret_arn = os.environ["SLACK_SECRET_ARN"]  (BR-07)
2. secret = get_secret(secret_arn)  (common/secrets.py 経由)
3. return secret["slack_bot_token"]
   ※ token 値はログに出力しない (BR-10)
```

---

## 6. common/secrets — シークレット取得ロジック

### get_secret のロジック

```
入力: secret_arn
1. ext_url = f"http://localhost:2773/secretsmanager/get?secretId={secret_arn}"
   headers = {"X-Aws-Parameters-Secrets-Token": os.environ.get("AWS_SESSION_TOKEN", "")}
2. try:
     response = requests.get(ext_url, headers=headers, timeout=1)
     response.raise_for_status()
     return json.loads(response.json()["SecretString"])
   except Exception:
     # Extension 未起動 or タイムアウト → Boto3 で直接取得（フォールバック）
     client = boto3.client("secretsmanager")
     resp = client.get_secret_value(SecretId=secret_arn)
     return json.loads(resp["SecretString"])
   ※ 戻り値はログに出力しない (BR-10)
```
