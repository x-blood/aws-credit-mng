# Infrastructure Design — Unit-2: CDK Infrastructure

## インフラ設計サマリー

| 項目 | 内容 |
|---|---|
| IaC ツール | AWS CDK (TypeScript) |
| パッケージマネージャー | npm |
| Lambda バンドル | `lambda.Code.fromAsset` + `BundlingOptions`（CDK が `pip install` を実行して zip 化、Docker 不要） |
| 設定値渡し方 | 環境変数（`SLACK_SECRET_ARN` 等を `process.env` で参照） |
| スタック構成 | 単一スタック（`CreditNotifierStack`） |
| デプロイリージョン | us-east-1 |

---

## CDK プロジェクト構成

```
infra/
├── bin/
│   └── app.ts                    # CDK App エントリーポイント
├── lib/
│   └── credit-notifier-stack.ts  # メイン CDK スタック
├── package.json
├── package-lock.json
├── tsconfig.json
└── cdk.json
```

---

## Lambda 関数定義（Code.fromAsset + BundlingOptions）

`aws-cdk-lib/aws-lambda` の `Function` と `Code.fromAsset` を使用する。
`BundlingOptions` で `pip install -r requirements.txt` を実行し、依存ライブラリを含めた
アセットを生成する。**Docker は不要**（CDK のローカルバンドルのみで完結）。

バンドル方式:
```typescript
const bundling: BundlingOptions = {
  // ローカルバンドル: pip が利用可能な場合はそのまま実行（Docker 不要）
  local: {
    tryBundle(outputDir: string) {
      try {
        execSync(
          `pip install -r requirements.txt -t ${outputDir} --quiet && ` +
          `cp -r . ${outputDir}`,
          { cwd: entryDir, stdio: 'inherit' }
        );
        return true;
      } catch {
        return false; // フォールバック: CDK の Docker バンドルへ
      }
    },
  },
  // フォールバック用 Docker コマンド（ローカルバンドル失敗時のみ使用）
  image: lambda.Runtime.PYTHON_3_12.bundlingImage,
  command: [
    'bash', '-c',
    'pip install -r requirements.txt -t /asset-output --quiet && cp -r . /asset-output',
  ],
};
```

各 Lambda 関数の `code` プロパティに `lambda.Code.fromAsset(entryDir, { bundling })` を指定する。

### monthly_notifier

| 設定項目 | 値 |
|---|---|
| Construct ID | `MonthlyNotifierFunction` |
| 関数名 | `credit-notifier-monthly` |
| code | `lambda.Code.fromAsset('../src/monthly_notifier', { bundling })` |
| handler | `handler.handler` |
| runtime | `Runtime.PYTHON_3_12` |
| メモリ | 256 MB |
| タイムアウト | `Duration.seconds(60)` |
| ログ保持期間 | `RetentionDays.THREE_MONTHS`（90日） |
| DLQ | `credit-notifier-dlq`（共用） |
| レイヤー | Lambda Extension（Parameters and Secrets） |

環境変数:
```typescript
{
  AWS_ACCOUNT_ID: this.account,
  SLACK_SECRET_ARN: process.env.SLACK_SECRET_ARN!,
  SLACK_CHANNEL_ID: process.env.SLACK_CHANNEL_ID ?? '',
  MONTHS_BACK: '3',
}
```

### threshold_checker

| 設定項目 | 値 |
|---|---|
| Construct ID | `ThresholdCheckerFunction` |
| 関数名 | `credit-notifier-threshold` |
| code | `lambda.Code.fromAsset('../src/threshold_checker', { bundling })` |
| handler | `handler.handler` |
| runtime | `Runtime.PYTHON_3_12` |
| メモリ | 256 MB |
| タイムアウト | `Duration.seconds(60)` |
| ログ保持期間 | `RetentionDays.THREE_MONTHS` |
| DLQ | `credit-notifier-dlq`（共用） |
| レイヤー | Lambda Extension |

環境変数:
```typescript
{
  AWS_ACCOUNT_ID: this.account,
  SLACK_SECRET_ARN: process.env.SLACK_SECRET_ARN!,
  SLACK_CHANNEL_ID: process.env.SLACK_CHANNEL_ID ?? '',
  THRESHOLD_AMOUNT: '1000.0',
}
```

### expiry_checker

| 設定項目 | 値 |
|---|---|
| Construct ID | `ExpiryCheckerFunction` |
| 関数名 | `credit-notifier-expiry` |
| code | `lambda.Code.fromAsset('../src/expiry_checker', { bundling })` |
| handler | `handler.handler` |
| runtime | `Runtime.PYTHON_3_12` |
| メモリ | 256 MB |
| タイムアウト | `Duration.seconds(60)` |
| ログ保持期間 | `RetentionDays.THREE_MONTHS` |
| DLQ | `credit-notifier-dlq`（共用） |
| レイヤー | Lambda Extension |

環境変数:
```typescript
{
  AWS_ACCOUNT_ID: this.account,
  SLACK_SECRET_ARN: process.env.SLACK_SECRET_ARN!,
  SLACK_CHANNEL_ID: process.env.SLACK_CHANNEL_ID ?? '',
}
```

---

## SQS DLQ

| 設定項目 | 値 |
|---|---|
| Construct ID | `CreditNotifierDlq` |
| キュー名 | `credit-notifier-dlq` |
| メッセージ保持期間 | `Duration.days(14)` |
| 可視性タイムアウト | `Duration.seconds(300)` |
| 暗号化 | SQS_MANAGED（デフォルト） |

---

## EventBridge Scheduler × 3

`aws-cdk-lib/aws-scheduler` を使用する。
各 Scheduler に専用の実行ロール（`SchedulerExecutionRole`）を付与し、
ターゲット Lambda のみ `lambda:InvokeFunction` を許可する。

| Construct ID | スケジューラ名 | cron 式 | ターゲット Lambda |
|---|---|---|---|
| `MonthlySchedule` | `credit-notifier-monthly-schedule` | `cron(0 9 1 * ? *)` | MonthlyNotifierFunction |
| `ThresholdSchedule` | `credit-notifier-threshold-schedule` | `cron(0 0 * * ? *)` | ThresholdCheckerFunction |
| `ExpirySchedule` | `credit-notifier-expiry-schedule` | `cron(0 1 * * ? *)` | ExpiryCheckerFunction |

設定:
- フレキシブルタイムウィンドウ: OFF（`FLEXIBLE_TIME_WINDOW_MODE.OFF`）
- リトライポリシー: 最大3回、最大イベント保持期間24時間

---

## IAM ロール設計

### Lambda 実行ロール（3 Lambda 共用）

CDK の `PythonFunction` が自動生成する実行ロールに以下のポリシーを付与する。

```typescript
// Billing API Read 権限
lambdaRole.addToPolicy(new iam.PolicyStatement({
  sid: 'BillingCreditsRead',
  effect: iam.Effect.ALLOW,
  actions: ['billing:GetCredits', 'billing:GetCreditAllocationHistory'],
  resources: ['*'],
}));

// Secrets Manager 特定 ARN にスコープ
lambdaRole.addToPolicy(new iam.PolicyStatement({
  sid: 'SecretsManagerAccess',
  effect: iam.Effect.ALLOW,
  actions: ['secretsmanager:GetSecretValue'],
  resources: [
    `arn:aws:secretsmanager:us-east-1:${this.account}:secret:credit-notifier/slack*`
  ],
}));

// SQS DLQ への送信権限
dlq.grantSendMessages(lambdaRole);
```

CloudWatch Logs は `PythonFunction` が自動で `logs:CreateLogGroup` 等を付与する。

### Scheduler 実行ロール（各 Scheduler に個別作成）

```typescript
const schedulerRole = new iam.Role(this, 'SchedulerExecutionRole', {
  assumedBy: new iam.ServicePrincipal('scheduler.amazonaws.com'),
});
targetFunction.grantInvoke(schedulerRole);
```

---

## Lambda Extension レイヤー

```typescript
const extensionLayer = lambda.LayerVersion.fromLayerVersionArn(
  this,
  'ParametersSecretsExtension',
  `arn:aws:lambda:us-east-1:177933569100:layer:AWS-Parameters-and-Secrets-Lambda-Extension:12`
);
// 各 PythonFunction の layers に追加する
```

---

## 環境変数（デプロイ前に設定が必要なもの）

CDK デプロイ実行前に以下を shell で export する:

```bash
export SLACK_SECRET_ARN="arn:aws:secretsmanager:us-east-1:XXXXXXXXXXXX:secret:credit-notifier/slack-XXXXXX"
export SLACK_CHANNEL_ID="C0123456789"   # オプション（Secrets Manager内の値を使う場合は不要）
```

`AWS_ACCOUNT_ID` は CDK が `this.account` から自動取得するため不要。
