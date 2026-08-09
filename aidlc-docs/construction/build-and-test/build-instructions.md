# Build Instructions

## 前提条件

| 項目 | 要件 |
|---|---|
| Python | 3.12 以上（Lambda ランタイムと合わせる） |
| Node.js | 20.x 以上 |
| npm | 10.x 以上 |
| AWS CLI | v2（`aws configure` でプロファイル設定済み） |
| AWS CDK CLI | v2（`npm install -g aws-cdk`） |
| pip | Python に付属 |
| Docker | オプション（ローカル pip が利用できない環境のみ） |

## 環境変数（デプロイ前に設定）

```bash
export SLACK_SECRET_ARN="arn:aws:secretsmanager:us-east-1:XXXXXXXXXXXX:secret:credit-notifier/slack-XXXXXX"
export SLACK_CHANNEL_ID="C0123456789"   # Secrets Manager 内の値を使う場合は省略可
```

---

## ビルドステップ

### Step 1: Python 依存関係インストール

```bash
cd /Users/yasuyukisato/tech/my/aws-credit-mng
pip install -r requirements-dev.txt
```

**期待される出力**: `Requirement already satisfied: ...` または `Successfully installed ...`

### Step 2: CDK 依存関係インストール

```bash
cd infra
npm install
```

**期待される出力**: `added N packages`（node_modules/ が生成される）

### Step 3: TypeScript コンパイルチェック

```bash
cd infra
npx tsc --noEmit
```

**期待される出力**: 出力なし（エラーなし）

### Step 4: CDK テンプレート合成（ローカル検証）

```bash
cd infra
SLACK_SECRET_ARN=$SLACK_SECRET_ARN cdk synth
```

**期待される出力**: `CreditNotifierStack` の CloudFormation テンプレート YAML が標準出力に表示される

### Step 5: CDK Bootstrap（初回のみ）

```bash
cdk bootstrap aws://XXXXXXXXXXXX/us-east-1
```

**期待される出力**: `✅  Environment aws://XXXXXXXXXXXX/us-east-1 bootstrapped.`

### Step 6: デプロイ

```bash
cd infra
SLACK_SECRET_ARN=$SLACK_SECRET_ARN cdk deploy
```

**期待される出力**:
```
✅  CreditNotifierStack

Outputs:
CreditNotifierStack.MonthlyFunctionArn = arn:aws:lambda:us-east-1:...
CreditNotifierStack.ThresholdFunctionArn = arn:aws:lambda:us-east-1:...
CreditNotifierStack.ExpiryFunctionArn = arn:aws:lambda:us-east-1:...
CreditNotifierStack.DlqUrl = https://sqs.us-east-1.amazonaws.com/...
```

---

## ビルドアーティファクト

| アーティファクト | 場所 | 説明 |
|---|---|---|
| Lambda zip | CDK アセットバケット（自動） | `cdk deploy` 時に S3 アップロード |
| CloudFormation テンプレート | `infra/cdk.out/` | `cdk synth` の出力 |

---

## トラブルシューティング

### `SLACK_SECRET_ARN` が未設定でデプロイ失敗

```
Error: 環境変数 SLACK_SECRET_ARN が設定されていません
```

→ `export SLACK_SECRET_ARN=...` を実行してから再度 `cdk deploy`

### pip バンドル中に `requirements.txt` が見つからない

```
ERROR: Could not open requirements file: No such file or directory: 'requirements.txt'
```

→ `src/` ディレクトリに `requirements.txt` が存在することを確認

### CDK Bootstrap 未実施

```
Error: This stack uses assets, so the toolkit stack must be deployed
```

→ `cdk bootstrap aws://XXXXXXXXXXXX/us-east-1` を実行
