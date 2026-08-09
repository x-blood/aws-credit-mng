#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { CreditNotifierStack } from '../lib/credit-notifier-stack';

const app = new cdk.App();

new CreditNotifierStack(app, 'CreditNotifierStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'us-east-1',
  },
  description: 'AWS Credit balance notification system (Lambda + EventBridge Scheduler)',
});
