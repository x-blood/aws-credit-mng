# Requirements Clarification Questions

docs/quick.md のブログドラフト内容を踏まえ、実装に向けて以下の質問にお答えください。
各質問の `[Answer]:` タグの後に、選択肢の文字（A、B、Cなど）を記入してください。
選択肢に合うものがない場合は最後の「Other」を選び、内容を記述してください。

---

## Question 1
Slack通知の実装方式を選択してください。

A) Incoming Webhook（シンプル、単一チャネル固定、Secrets Manager でURL管理）

B) AWS Chatbot + SNS（マネージド、Webhook管理不要、Block Kitカード自動生成）

C) chat.postMessage API（複数チャネル動的送信可能、OAuth トークン管理が必要）

D) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 2
通知スケジュールを選択してください。

A) 月次のみ（毎月1日 09:00 UTC）— ブログドラフト通りの構成

B) 月次 + 残高閾値アラート（月次定期通知に加え、残高が一定額を下回った場合に即時通知）

C) 日次（毎日残高をモニタリングして通知）

D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 3
Cost Explorer 連携（部門別クレジットレポート）を含めますか？

A) Yes — 部門別クレジット消費レポートをSlack通知に統合する（Cost Categories 設定が必要）

B) No — シンプルに残高通知のみ（`GetCredits` + `GetCreditAllocationHistory`のみ使用）

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 4
AWSアカウント構成を教えてください。

A) 単一アカウント（シングルアカウント構成）

B) Organizations + Consolidated Billing（管理アカウントから複数アカウントを集約）

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 5
IaCツール（Infrastructure as Code）の選択肢を教えてください。

A) AWS CDK（Python）— Lambda、EventBridge、Secrets Manager、IAM をコードで管理

B) AWS SAM（Serverless Application Model）— サーバーレス特化のテンプレート

C) Terraform — マルチクラウド対応のIaC

D) マネジメントコンソール / AWS CLI のみ（IaCなし）

E) Other (please describe after [Answer]: tag below)

[Answer]: E AWS CDK (Node.js)

---

## Question 6
Lambda 関数のランタイムを選択してください。

A) Python 3.12（ブログドラフトのコード例と同じ）

B) Python 3.11

C) Node.js 20.x（TypeScript）

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 7
クレジット期限切れアラート機能を含めますか？

A) Yes — 期限30日前・7日前・当日にエスカレーション通知（別途 EventBridge Scheduler ルール追加）

B) No — 月次通知内でのみ期限情報を表示する

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 8: Security Extensions
このプロジェクトにセキュリティ拡張ルールを適用しますか？

A) Yes — セキュリティルールをブロッキング制約として適用（本番グレードのアプリに推奨）

B) No — セキュリティルールをスキップ（PoC・プロトタイプに適）

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 9: Resiliency Extensions
このプロジェクトに AWS Well-Architected Framework に基づく耐障害性ベースラインを適用しますか？

A) Yes — 耐障害性ベストプラクティスを設計ガイダンスとして適用（ビジネスクリティカルなワークロードに推奨）

B) No — 耐障害性ベースラインをスキップ（PoC・プロトタイプに適）

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 10: Property-Based Testing Extension
プロパティベーステスト（PBT）ルールを適用しますか？

A) Yes — 全PBTルールをブロッキング制約として適用

B) Partial — 純粋関数とシリアライゼーションのみに適用

C) No — PBTルールをスキップ（シンプルな統合レイヤーに適）

X) Other (please describe after [Answer]: tag below)

[Answer]: C
