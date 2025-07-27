# ARM64ビルド環境セットアップツール

このツールは、Amazon Bedrock AgentCoreのARM64ビルド環境をセットアップするためのものです。Bedrock AgentCoreはARM64アーキテクチャを必要としますが、多くの開発環境はAMD64（x86_64）アーキテクチャで動作しています。このツールを使用することで、AMD64環境でもARM64ビルドを実行できるようになります。

## 背景

Amazon Bedrock AgentCoreは、エージェントをホスティングするためのランタイム環境を提供します。このランタイム環境はARM64アーキテクチャを必要としますが、多くの開発環境はAMD64（x86_64）アーキテクチャで動作しています。このアーキテクチャの不一致により、以下のようなエラーが発生することがあります：

```
⚠️  [WARNING] Platform mismatch: Current system is 'linux/amd64' but Bedrock AgentCore requires 'linux/arm64'.
```

## 解決策

このツールは、以下の方法でこの問題を解決します：

1. QEMUエミュレーションを設定して、ARM64アーキテクチャのコンテナをAMD64（x86_64）ホスト上で実行できるようにします。
2. 環境変数`DOCKER_DEFAULT_PLATFORM`を`linux/arm64`に設定して、Dockerビルドプロセスがarm64アーキテクチャをターゲットにするようにします。
3. テスト用のDockerfileを作成してビルドし、設定が正しく機能していることを確認します。
4. Bedrock AgentCore用のサンプルコードを生成します。

## 使用方法

### 1. セットアップスクリプトの実行

```bash
cd /home/coder/amazon-bedrock-agentcore-samples
python scripts/setup_arm64_build.py
```

このスクリプトは以下を行います：

- 現在のプラットフォームを確認
- プラットフォームがarm64でない場合、QEMUエミュレーションを設定
- DOCKER_DEFAULT_PLATFORMを設定
- テスト用のDockerfileを作成してビルド
- ビルドが成功したかどうかを確認
- Bedrock AgentCore用のサンプルコードを生成

### 2. サンプルコードの使用

セットアップスクリプトが正常に実行されると、`scripts/bedrock_agentcore_arm64_sample.py`というサンプルコードが生成されます。このコードは、Bedrock AgentCoreでARM64ビルドを実行するための基本的なテンプレートを提供します。

```python
# 環境変数を設定
import os
os.environ['DOCKER_DEFAULT_PLATFORM'] = 'linux/arm64'

# AgentCore Runtimeを初期化
from bedrock_agentcore_starter_toolkit import Runtime
agentcore_runtime = Runtime()

# AgentCore Runtimeを設定
response = agentcore_runtime.configure(
    entrypoint="your_entrypoint.py",  # エントリポイントファイルを指定
    execution_role="your_execution_role_arn",  # 実行ロールのARNを指定
    auto_create_ecr=True,
    requirements_file="requirements.txt",  # 要件ファイルを指定
    region="your_region",  # リージョンを指定
    agent_name="your_agent_name"  # エージェント名を指定
)

# AgentCore Runtimeを起動
launch_result = agentcore_runtime.launch()
print(launch_result)
```

このコードを使用する際は、以下の点に注意してください：

1. エントリポイントファイル、実行ロールのARN、リージョン、エージェント名を指定します。
2. スクリプトを実行します。

### 3. Jupyter Notebookでの使用

Jupyter Notebookを使用している場合は、以下のコードをセルに追加して実行します：

```python
# 環境変数を設定
import os
os.environ['DOCKER_DEFAULT_PLATFORM'] = 'linux/arm64'

# 以下、通常のAgentCore Runtimeの設定と起動のコード
```

## 注意事項

- QEMUエミュレーションは、システムを再起動するまで有効です。システムを再起動した場合は、再度QEMUエミュレーションを設定する必要があります。
- Docker buildxが利用可能であることを確認してください。利用できない場合は、インストールが必要です。
- ARM64ビルドは、AMD64ビルドよりも時間がかかる場合があります。これは、エミュレーションによるオーバーヘッドが原因です。

## トラブルシューティング

### QEMUエミュレーションが設定できない場合

以下のコマンドを実行して、QEMUエミュレーションを手動で設定します：

```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

### Docker buildxが利用できない場合

以下のコマンドを実行して、Docker buildxをインストールします：

```bash
docker buildx create --use
```

### ARM64ビルドが失敗する場合

以下の点を確認してください：

1. QEMUエミュレーションが正しく設定されているか
2. Docker buildxがARM64プラットフォームをサポートしているか
3. 環境変数DOCKER_DEFAULT_PLATFORMが正しく設定されているか

## 参考リンク

- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html)
- [Docker buildx ドキュメント](https://docs.docker.com/buildx/working-with-buildx/)
- [QEMU ドキュメント](https://www.qemu.org/docs/master/)
