import * as path from 'path';
import { execSync } from 'child_process';
import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as scheduler from '@aws-cdk/aws-scheduler-alpha';
import * as targets from '@aws-cdk/aws-scheduler-targets-alpha';
import { Construct } from 'constructs';

// Lambda Parameters and Secrets Extension ARN（us-east-1）
const PARAMS_SECRETS_EXTENSION_ARN =
  'arn:aws:lambda:us-east-1:177933569100:layer:AWS-Parameters-and-Secrets-Lambda-Extension:12';

// 本プロジェクト専用 SSM パラメータ名（us-east-1）
const SSM_BOT_TOKEN_PARAM    = '/credit-notifier/slack-bot-token';
const SSM_CHANNEL_ID_PARAM   = '/credit-notifier/slack-channel-id';

export class CreditNotifierStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ---- SQS Dead Letter Queue ----
    // Lambda 失敗時のイベント退避先（3 Lambda 共用）
    const dlq = new sqs.Queue(this, 'CreditNotifierDlq', {
      queueName: 'credit-notifier-dlq',
      retentionPeriod: cdk.Duration.days(14),
      visibilityTimeout: cdk.Duration.seconds(300), // Lambda タイムアウト × 5
      encryption: sqs.QueueEncryption.SQS_MANAGED,
    });

    // ---- Lambda Extension レイヤー（SSM Parameter Store キャッシュ用）----
    const extensionLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'ParametersSecretsExtension',
      PARAMS_SECRETS_EXTENSION_ARN,
    );

    // ---- Lambda 実行ロール（3 関数共用、最小権限）----
    const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        // CloudWatch Logs 基本ポリシー
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Billing API Read 権限（リソースレベル権限なし）
    // aws-portal:ViewBilling は旧 Billing コンソール API との互換性のために必要
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'BillingCreditsRead',
      effect: iam.Effect.ALLOW,
      actions: [
        'billing:GetCredits',
        'billing:GetCreditAllocationHistory',
        'aws-portal:ViewBilling',
      ],
      resources: ['*'],
    }));

    // SSM Parameter Store: /credit-notifier/* のみに限定
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'SSMParameterAccess',
      effect: iam.Effect.ALLOW,
      actions: ['ssm:GetParameter'],
      resources: [
        `arn:aws:ssm:us-east-1:${this.account}:parameter/credit-notifier/*`,
      ],
    }));

    // DLQ への SendMessage 権限
    dlq.grantSendMessages(lambdaRole);

    // ---- BundlingOptions: pip でローカルバンドル（Docker 不要）----
    // CDK_BUNDLING_SKIP=1 の場合（テスト時）はバンドルをスキップする
    const skipBundling = process.env.CDK_BUNDLING_SKIP === '1';
    // requirements.txt はプロジェクトルートにある
    const requirementsTxt = path.join(__dirname, '..', '..', 'requirements.txt');

    const makeBundling = (entryDir: string): cdk.BundlingOptions | undefined => {
      if (skipBundling) return undefined;
      return {
        local: {
          tryBundle(outputDir: string): boolean {
            try {
              execSync(
                // requirements.txt のパスを明示的に指定する
                `pip install -r ${requirementsTxt} -t ${outputDir} --quiet && cp -r . ${outputDir}`,
                { cwd: entryDir, stdio: 'inherit' },
              );
              return true;
            } catch {
              // pip が利用不可の場合は Docker フォールバックへ
              return false;
            }
          },
        },
        // Docker フォールバック（ローカルバンドル失敗時のみ使用）
        image: lambda.Runtime.PYTHON_3_12.bundlingImage,
        command: [
          'bash', '-c',
          // Docker 内では /asset-input/ 直下に requirements.txt をコピーして使う
          `cp ${requirementsTxt} /asset-input/requirements.txt && pip install -r /asset-input/requirements.txt -t /asset-output --quiet && cp -r . /asset-output`,
        ],
      };
    };

    // src/ 全体をバンドルして各ハンドラーを指定する
    const srcDir = path.join(__dirname, '..', '..', 'src');

    // ---- 共通 Lambda プロパティ ----
    const commonLambdaProps = {
      runtime: lambda.Runtime.PYTHON_3_12,
      memorySize: 256,
      timeout: cdk.Duration.seconds(60),
      role: lambdaRole,
      deadLetterQueue: dlq,
      layers: [extensionLayer],
      environment: {
        AWS_ACCOUNT_ID: this.account,
        // SSM パラメータ名を環境変数として渡す（値は Lambda 起動時に取得）
        SLACK_BOT_TOKEN_PARAM:  SSM_BOT_TOKEN_PARAM,
        SLACK_CHANNEL_ID_PARAM: SSM_CHANNEL_ID_PARAM,
      },
    };

    // ---- CloudWatch Log Groups（明示的に作成して保持期間を設定）----
    const makeLogGroup = (functionName: string) =>
      new logs.LogGroup(this, `${functionName}LogGroup`, {
        logGroupName: `/aws/lambda/${functionName}`,
        retention: logs.RetentionDays.THREE_MONTHS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      });

    // ---- monthly_notifier Lambda ----
    const monthlyFn = new lambda.Function(this, 'MonthlyNotifierFunction', {
      ...commonLambdaProps,
      functionName: 'credit-notifier-monthly',
      description: 'Monthly AWS credit balance report to Slack',
      code: lambda.Code.fromAsset(srcDir, { bundling: makeBundling(srcDir) }),
      handler: 'monthly_notifier.handler.handler',
      logGroup: makeLogGroup('credit-notifier-monthly'),
      environment: {
        ...commonLambdaProps.environment,
        MONTHS_BACK: '3',
      },
    });

    // ---- threshold_checker Lambda ----
    const thresholdFn = new lambda.Function(this, 'ThresholdCheckerFunction', {
      ...commonLambdaProps,
      functionName: 'credit-notifier-threshold',
      description: 'Daily credit balance threshold check and Slack alert',
      code: lambda.Code.fromAsset(srcDir, { bundling: makeBundling(srcDir) }),
      handler: 'threshold_checker.handler.handler',
      logGroup: makeLogGroup('credit-notifier-threshold'),
      environment: {
        ...commonLambdaProps.environment,
        THRESHOLD_AMOUNT: '20.0',
      },
    });

    // ---- expiry_checker Lambda ----
    const expiryFn = new lambda.Function(this, 'ExpiryCheckerFunction', {
      ...commonLambdaProps,
      functionName: 'credit-notifier-expiry',
      description: 'Daily credit expiry check and Slack escalation alert',
      code: lambda.Code.fromAsset(srcDir, { bundling: makeBundling(srcDir) }),
      handler: 'expiry_checker.handler.handler',
      logGroup: makeLogGroup('credit-notifier-expiry'),
    });

    // ---- EventBridge Scheduler ヘルパー関数 ----
    // 各 Scheduler に専用の実行ロールを作成して最小権限を維持する
    const createScheduler = (
      constructId: string,
      scheduleName: string,
      cronExpression: scheduler.CronOptionsWithTimezone,
      targetFn: lambda.IFunction,
      description: string,
    ): void => {
      const schedulerRole = new iam.Role(this, `${constructId}Role`, {
        assumedBy: new iam.ServicePrincipal('scheduler.amazonaws.com'),
        description: `Execution role for EventBridge Scheduler: ${scheduleName}`,
      });
      targetFn.grantInvoke(schedulerRole);

      new scheduler.Schedule(this, constructId, {
        scheduleName,
        description,
        // flexibleTimeWindow は OFF（固定時刻で起動する）
        schedule: scheduler.ScheduleExpression.cron(cronExpression),
        target: new targets.LambdaInvoke(targetFn, {
          role: schedulerRole,
          retryAttempts: 3,
          maxEventAge: cdk.Duration.hours(24),
        }),
        enabled: true,
      });
    };

    // 毎月1日 09:00 UTC — 月次レポート
    createScheduler(
      'MonthlySchedule',
      'credit-notifier-monthly-schedule',
      { minute: '0', hour: '9', day: '1', month: '*', year: '*' },
      monthlyFn,
      'Monthly credit report to Slack on the 1st at 09:00 UTC',
    );

    // 毎日 00:00 UTC — 残高閾値チェック
    createScheduler(
      'ThresholdSchedule',
      'credit-notifier-threshold-schedule',
      { minute: '0', hour: '0', day: '*', month: '*', year: '*' },
      thresholdFn,
      'Daily credit balance threshold check at 00:00 UTC',
    );

    // 毎日 01:00 UTC — 期限切れチェック
    createScheduler(
      'ExpirySchedule',
      'credit-notifier-expiry-schedule',
      { minute: '0', hour: '1', day: '*', month: '*', year: '*' },
      expiryFn,
      'Daily credit expiry check at 01:00 UTC',
    );

    // ---- CloudFormation Outputs ----
    new cdk.CfnOutput(this, 'MonthlyFunctionArn', {
      value: monthlyFn.functionArn,
      description: 'Monthly notifier Lambda function ARN',
    });
    new cdk.CfnOutput(this, 'ThresholdFunctionArn', {
      value: thresholdFn.functionArn,
      description: 'Threshold checker Lambda function ARN',
    });
    new cdk.CfnOutput(this, 'ExpiryFunctionArn', {
      value: expiryFn.functionArn,
      description: 'Expiry checker Lambda function ARN',
    });
    new cdk.CfnOutput(this, 'DlqUrl', {
      value: dlq.queueUrl,
      description: 'Dead Letter Queue URL',
    });
  }
}
