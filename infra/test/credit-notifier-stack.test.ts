import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { CreditNotifierStack } from '../lib/credit-notifier-stack';

// テスト用の環境変数を設定する
beforeAll(() => {
  process.env.SLACK_BOT_TOKEN_PARAM  = '/credit-notifier/slack-bot-token';
  process.env.SLACK_CHANNEL_ID_PARAM = '/credit-notifier/slack-channel-id';
  process.env.CDK_DEFAULT_ACCOUNT = '123456789012';
  process.env.CDK_DEFAULT_REGION = 'us-east-1';
  // バンドル処理をスキップしてテスト実行を高速化する
  process.env.CDK_BUNDLING_SKIP = '1';
});

afterAll(() => {
  delete process.env.SLACK_BOT_TOKEN_PARAM;
  delete process.env.SLACK_CHANNEL_ID_PARAM;
  delete process.env.CDK_DEFAULT_ACCOUNT;
  delete process.env.CDK_DEFAULT_REGION;
  delete process.env.CDK_BUNDLING_SKIP;
});

// テスト用スタックとテンプレートを一度だけ生成する
const getTemplate = (): Template => {
  const app = new cdk.App();
  const stack = new CreditNotifierStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  return Template.fromStack(stack);
};

let template: Template;

beforeAll(() => {
  template = getTemplate();
});

// -----------------------------------------------------------------------
// Lambda 関数のアサーション
// -----------------------------------------------------------------------

describe('Lambda Functions', () => {
  test('Lambda 関数が 3 つ作成される', () => {
    template.resourceCountIs('AWS::Lambda::Function', 3);
  });

  test('全 Lambda のメモリは 256MB', () => {
    template.allResourcesProperties('AWS::Lambda::Function', {
      MemorySize: 256,
    });
  });

  test('全 Lambda のタイムアウトは 60 秒', () => {
    template.allResourcesProperties('AWS::Lambda::Function', {
      Timeout: 60,
    });
  });

  test('monthly_notifier のハンドラーが正しい', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'credit-notifier-monthly',
      Handler: 'monthly_notifier.handler.handler',
      Runtime: 'python3.12',
    });
  });

  test('threshold_checker のハンドラーが正しい', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'credit-notifier-threshold',
      Handler: 'threshold_checker.handler.handler',
      Runtime: 'python3.12',
    });
  });

  test('expiry_checker のハンドラーが正しい', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'credit-notifier-expiry',
      Handler: 'expiry_checker.handler.handler',
      Runtime: 'python3.12',
    });
  });

  test('monthly_notifier に MONTHS_BACK 環境変数がある', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'credit-notifier-monthly',
      Environment: {
        Variables: Match.objectLike({
          MONTHS_BACK: '3',
        }),
      },
    });
  });

  test('threshold_checker に THRESHOLD_AMOUNT 環境変数がある', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'credit-notifier-threshold',
      Environment: {
        Variables: Match.objectLike({
          THRESHOLD_AMOUNT: '1000.0',
        }),
      },
    });
  });

  test('全 Lambda に SLACK_BOT_TOKEN_PARAM 環境変数がある', () => {
    const functions = template.findResources('AWS::Lambda::Function');
    const fnValues = Object.values(functions);
    const appFunctions = fnValues.filter(
      (f: any) => f.Properties?.FunctionName?.startsWith('credit-notifier-'),
    );
    appFunctions.forEach((f: any) => {
      expect(f.Properties.Environment.Variables.SLACK_BOT_TOKEN_PARAM).toBeDefined();
    });
  });
});

// -----------------------------------------------------------------------
// SQS DLQ のアサーション
// -----------------------------------------------------------------------

describe('SQS Dead Letter Queue', () => {
  test('DLQ が 1 つ作成される', () => {
    // Lambda ログ保持用の CustomResource が SQS を作ることがあるため名前で特定する
    template.hasResourceProperties('AWS::SQS::Queue', {
      QueueName: 'credit-notifier-dlq',
    });
  });

  test('DLQ のメッセージ保持期間は 14 日（1209600 秒）', () => {
    template.hasResourceProperties('AWS::SQS::Queue', {
      QueueName: 'credit-notifier-dlq',
      MessageRetentionPeriod: 1209600,
    });
  });
});

// -----------------------------------------------------------------------
// IAM ポリシーのアサーション
// -----------------------------------------------------------------------

describe('IAM Policy', () => {
  test('billing:GetCredits 権限がある', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: Match.arrayWith([
              'billing:GetCredits',
              'billing:GetCreditAllocationHistory',
              'aws-portal:ViewBilling',
            ]),
            Effect: 'Allow',
          }),
        ]),
      },
    });
  });

  test('SSM Parameter Store は /credit-notifier/* のみに限定される', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: 'ssm:GetParameter',
            Effect: 'Allow',
            Resource: Match.stringLikeRegexp('credit-notifier'),
          }),
        ]),
      },
    });
  });
});

// -----------------------------------------------------------------------
// EventBridge Scheduler のアサーション
// -----------------------------------------------------------------------

describe('EventBridge Schedulers', () => {
  test('Scheduler が 3 つ作成される', () => {
    template.resourceCountIs('AWS::Scheduler::Schedule', 3);
  });

  test('月次スケジュールの cron 式が正しい', () => {
    template.hasResourceProperties('AWS::Scheduler::Schedule', {
      Name: 'credit-notifier-monthly-schedule',
      ScheduleExpression: 'cron(0 9 1 * ? *)',
    });
  });

  test('閾値チェックスケジュールの cron 式が正しい', () => {
    template.hasResourceProperties('AWS::Scheduler::Schedule', {
      Name: 'credit-notifier-threshold-schedule',
      ScheduleExpression: 'cron(0 0 * * ? *)',
    });
  });

  test('期限切れチェックスケジュールの cron 式が正しい', () => {
    template.hasResourceProperties('AWS::Scheduler::Schedule', {
      Name: 'credit-notifier-expiry-schedule',
      ScheduleExpression: 'cron(0 1 * * ? *)',
    });
  });
});

// -----------------------------------------------------------------------
// CloudFormation Outputs のアサーション
// -----------------------------------------------------------------------

describe('CloudFormation Outputs', () => {
  test('Lambda ARN が 3 つ出力される', () => {
    template.hasOutput('MonthlyFunctionArn', {});
    template.hasOutput('ThresholdFunctionArn', {});
    template.hasOutput('ExpiryFunctionArn', {});
  });

  test('DLQ URL が出力される', () => {
    template.hasOutput('DlqUrl', {});
  });
});
