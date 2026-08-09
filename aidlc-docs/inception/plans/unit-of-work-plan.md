# Unit of Work Plan

## 分解スコープ
Application Design で確定した構成に基づき、システムを開発単位（Unit of Work）に分解する。

---

## Plan Checkboxes

### Part 1 - Planning
- [x] コンテキスト分析（Application Design の設計決定を反映）
- [x] Q1〜Q2の質問作成
- [x] ユーザー回答収集
- [x] 回答の矛盾・曖昧さ分析

### Part 2 - Generation
- [x] unit-of-work.md 生成
- [x] unit-of-work-dependency.md 生成
- [x] unit-of-work-story-map.md 生成
- [x] 完成確認

---

## 確定済みの設計決定（Application Design より）

Application Design フェーズで以下が既に確定しているため、
Units Generation の質問は境界確認に絞る。

| 決定事項 | 内容 |
|---|---|
| Lambda 分割 | 3関数分離（monthly / threshold / expiry）|
| 共有コード | `src/common/` モジュール |
| IaC | AWS CDK（Node.js / TypeScript）|
| Lambda ランタイム | Python 3.12 |
| スタック | 単一 CDK スタック |

---

## Question 1: Unit 境界の確認

Application Design の設計を踏まえ、開発単位の分割を確認してください。

A) Unit-1: Lambda アプリ（Python）/ Unit-2: CDK インフラ（TypeScript）の2ユニット  
   — Workflow Planning で提案した分割。アプリとインフラを独立して開発・テスト可能

B) Unit-1 のみ（単一ユニット）— Lambda コードと CDK を1ユニットとして一体管理

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 2: ディレクトリ構成の確認

Application Design で提案したプロジェクト構成を確認してください。

A) 提案通り（`src/` に Python Lambda、`infra/` に CDK TypeScript、`tests/` に pytest）

B) モノレポ構成（`packages/lambda/`、`packages/infra/` のような構成）

C) Other (please describe after [Answer]: tag below)

[Answer]: A
