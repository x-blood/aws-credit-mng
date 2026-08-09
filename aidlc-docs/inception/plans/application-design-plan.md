# Application Design Plan

## Design Scope
AWS Credits 月次Slack通知システム（Greenfield / Serverless）

コンポーネント設計の方向性を確定するため、以下の質問にお答えください。
各 `[Answer]:` タグの後に選択肢の文字を記入してください。

---

## Design Plan Checkboxes

- [x] Q1〜Q5の回答収集
- [x] components.md 生成
- [x] component-methods.md 生成
- [x] services.md 生成
- [x] component-dependency.md 生成
- [x] application-design.md（統合版）生成

---

## Question 1: Lambda 関数の分割方針

3つの通知ロール（月次・日次閾値・日次期限切れ）に対するLambda関数の構成を選択してください。

A) 3関数分離（月次通知 / 日次閾値チェック / 日次期限切れチェック）— 各関数が独立してデプロイ・スケール可能

B) 2関数（月次通知 / 日次チェック共通）— 日次閾値と期限切れを1関数に統合し、環境変数でモード切替

C) 1関数（全モード統合）— EventBridgeイベントのpayloadでモードを判定して動作を切替

D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 2: 共有コードの管理方針

Billing API呼び出し・Slack通知・エラーハンドリングなどの共通処理の管理方法を選択してください。

A) Lambda Layer — 共通コードをLayerとしてパッケージし、複数Lambda関数で共有

B) 同一パッケージ内モジュール — 共通コードを `src/common/` などのモジュールとして各Lambdaが直接インポート

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 3: Slack通知メッセージの構築責任

Slack Block Kitメッセージの構築処理をどのコンポーネントが担うべきか選択してください。

A) 各Lambda関数内で独立して構築（月次・閾値・期限それぞれが専用のBlock Kitを構築）

B) 共有Notifierコンポーネントが一元的に構築（メッセージテンプレートを共有コンポーネントが管理）

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4: Secrets Manager アクセス方針

Slack OAuth TokenのSecrets Manager参照方法を選択してください。

A) 各Lambda関数が起動時に直接取得（シンプル、関数ごとに独立）

B) Lambda Extension（AWS Parameters and Secrets Lambda Extension）でキャッシュ（APIコール削減、レスポンス改善）

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 5: CDK スタック分割方針

CDKインフラコードのスタック構成を選択してください。

A) 単一スタック（全リソースを1つの CDK Stack に定義）— シンプル、小規模向き

B) 2スタック分割（Lambda/アプリスタック + Scheduler/インフラスタック）— 依存関係が明確

C) Other (please describe after [Answer]: tag below)

[Answer]: A
