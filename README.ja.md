# Amazon Bedrock AgentCore サンプル

Amazon Bedrock AgentCore サンプルリポジトリへようこそ！

> [!CAUTION]
> このリポジトリで提供されている例は、実験的および教育目的のみを意図しています。これらは概念や技術を示すものであり、本番環境での直接使用を意図したものではありません。[プロンプトインジェクション](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html)から保護するために、Amazon Bedrock Guardrailsを設置してください。

**Amazon Bedrock AgentCore**は、任意のエージェントフレームワークと任意のLLMモデルを使用して、エージェントを安全かつスケーラブルに展開・運用するための完全な機能セットです。
これにより、開発者はAIエージェントを迅速に本番環境に導入し、ビジネス価値の実現を加速することができます。

Amazon Bedrock AgentCoreは、エージェントをより効果的かつ有能にするためのツールと機能、エージェントを安全にスケールするための目的に特化したインフラストラクチャ、
そして信頼性の高いエージェントを運用するためのコントロールを提供します。

Amazon Bedrock AgentCoreの機能は組み合わせ可能で、人気のあるオープンソースフレームワークやあらゆるモデルと連携するため、
オープンソースの柔軟性とエンタープライズグレードのセキュリティおよび信頼性の間で選択する必要はありません。

このコレクションは、Amazon Bedrock AgentCoreの機能を理解し、実装し、アプリケーションに統合するのに役立つ例とチュートリアルを提供します。

## 📁 リポジトリ構造

### 📚 [`01-tutorials/`](./01-tutorials/)
**インタラクティブな学習と基礎**

このフォルダには、ハンズオン例を通じてAmazon Bedrock AgentCoreの基本を教えるノートブックベースのチュートリアルが含まれています。

構造はAgentCoreコンポーネントによって分けられています：
* **Runtime**: Amazon Bedrock AgentCore Runtimeは、フレームワーク、プロトコル、またはモデルの選択に関係なく、AIエージェントとツールの両方を展開およびスケールするための安全でサーバーレスなランタイム機能であり、迅速なプロトタイピング、シームレスなスケーリング、市場投入時間の短縮を可能にします。
* **Gateway**: AIエージェントは、データベースの検索からメッセージの送信まで、実世界のタスクを実行するためのツールを必要とします。Amazon Bedrock AgentCore Gatewayは、API、Lambda関数、既存のサービスを自動的にMCP互換のツールに変換するため、開発者は統合を管理することなく、これらの重要な機能をエージェントに迅速に利用可能にすることができます。
* **Memory**: Amazon Bedrock AgentCore Memoryは、完全に管理されたメモリインフラストラクチャとニーズに合わせてメモリをカスタマイズする機能により、開発者が豊かでパーソナライズされたエージェントエクスペリエンスを構築することを容易にします。
* **Identity**: Amazon Bedrock AgentCore Identityは、SlackやZoomなどのAWSサービスとサードパーティアプリケーション全体でシームレスなエージェントのアイデンティティとアクセス管理を提供し、Okta、Entra、Amazon Cognitoなどの標準的なアイデンティティプロバイダーをサポートします。
* **Tools**: Amazon Bedrock AgentCoreは、エージェントAIアプリケーション開発を簡素化するための2つの組み込みツールを提供します：Amazon Bedrock AgentCore **Code Interpreter**ツールは、AIエージェントがコードを安全に記述および実行できるようにし、その精度を向上させ、複雑なエンドツーエンドのタスクを解決する能力を拡張します。Amazon Bedrock AgentCore **Browser Tool**は、AIエージェントがウェブサイトをナビゲートし、複数ステップのフォームを完了し、完全に管理された安全なサンドボックス環境内で低レイテンシーで人間のような精度で複雑なウェブベースのタスクを実行できるようにするエンタープライズグレードの機能です。
* **Observability**: Amazon Bedrock AgentCore Observabilityは、統合された運用ダッシュボードを通じて、エージェントのパフォーマンスを追跡、デバッグ、監視するのに役立ちます。OpenTelemetry互換のテレメトリとエージェントワークフローの各ステップの詳細な視覚化をサポートすることで、Amazon Bedrock AgentCore Observabilityは開発者がエージェントの動作に簡単に可視性を得て、スケールで品質基準を維持できるようにします。

**エンドツーエンドの例**フォルダは、ユースケースにおいて異なる機能を組み合わせる方法の簡単な例を提供します。

提供されている例は、AIエージェントアプリケーションを構築する前に基礎となる概念を理解したい初心者や学習者に最適です。

### 💡 [`02-use-cases/`](./02-use-cases/)
**エンドツーエンドアプリケーション**

Amazon Bedrock AgentCoreの機能を実際のビジネス問題を解決するために適用する方法を示す実用的なユースケース実装を探索してください。

各ユースケースには、AgentCoreコンポーネントに焦点を当てた完全な実装と詳細な説明が含まれています。

### 🔌 [`03-integrations/`](./03-integrations/)
**フレームワークとプロトコルの統合**

Strands Agents、LangChain、CrewAIなどの人気のあるエージェントフレームワークとAmazon Bedrock AgentCore機能を統合する方法を学びます。

A2Aによるエージェント間通信と異なるマルチエージェントコラボレーションパターンを設定します。エージェントインターフェースを統合し、
異なるエントリーポイントでAmazon Bedrock AgentCoreを使用する方法を学びます。

## 🚀 クイックスタート

1. **リポジトリをクローンする**

   ```bash
   git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
   ```

2. **環境をセットアップする**

   ```bash
   pip install bedrock-agentcore
   ```

3. **チュートリアルを始める**
   ```bash
   cd 01-tutorials
   jupyter notebook
   ```

## 📋 前提条件

- Python 3.10以上
- AWSアカウント
- Jupyter Notebook（チュートリアル用）

## 🤝 貢献

貢献を歓迎します！以下の詳細については[貢献ガイドライン](CONTRIBUTING.md)をご覧ください：

- 新しいサンプルの追加
- 既存の例の改善
- 問題の報告
- 機能強化の提案

## 📄 ライセンス

このプロジェクトはMITライセンスの下でライセンスされています - 詳細は[LICENSE](LICENSE)ファイルをご覧ください。

## 🆘 サポート

- **問題**: バグの報告や機能リクエストは[GitHub Issues](https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues)を通じて行ってください
- **ドキュメント**: 特定のガイダンスについては個々のフォルダのREADMEをチェックしてください

## 🔄 更新

このリポジトリは積極的に維持され、新しい機能と例で更新されています。最新の追加情報を入手するには、リポジトリをウォッチしてください。

## 翻訳と修正

- uv を利用
   - uv add -r requirements.txt
- arm64 以外のプラットフォーム対応


