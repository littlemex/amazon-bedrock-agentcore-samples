# Amazon Bedrock AgentCore Runtime での MCP サーバーのホスティング

## 概要

このチュートリアルでは、Amazon Bedrock AgentCore Runtime で MCP（Model Context Protocol）サーバーをホストする方法を学びます。Amazon Bedrock AgentCore Python SDK を使用して、MCP ツールを Amazon Bedrock AgentCore と互換性のある MCP サーバーとしてラップします。

Amazon Bedrock AgentCore Python SDK は MCP サーバーの実装の詳細を処理するため、ツールのコア機能に集中できます。このSDKはあなたのコードを AgentCore 標準化された MCP プロトコル契約に変換し、直接通信を可能にします。

### チュートリアルの詳細

| 情報               | 詳細                                                   |
|:------------------|:--------------------------------------------------------|
| チュートリアルタイプ | ツールのホスティング                                     |
| ツールタイプ       | MCP サーバー                                            |
| チュートリアルコンポーネント | AgentCore Runtime での MCP サーバーのホスティング   |
| チュートリアル分野   | 分野横断的                                             |
| 例の複雑さ         | 簡単                                                   |
| 使用 SDK          | Amazon BedrockAgentCore Python SDK と MCP              |

### チュートリアルのアーキテクチャ

このチュートリアルでは、MCP サーバーを AgentCore ランタイムにデプロイする方法について説明します。

デモンストレーションのために、3 つのツール（`add_numbers`、`multiply_numbers`、`greet_user`）を持つシンプルな MCP サーバーを使用します。

<div style="text-align:left">
    <img src="images/hosting_mcp_server.png" width="40%"/>
</div>

### チュートリアルの主な機能

* カスタムツールを使用した MCP サーバーの作成
* MCP サーバーのローカルでのテスト
* Amazon Bedrock AgentCore Runtime での MCP サーバーのホスティング
* 認証を使用したデプロイ済み MCP サーバーの呼び出し

## 前提条件

このチュートリアルを実行するには以下が必要です：

* Python 3.10+
* 設定済みの AWS 認証情報
* Amazon Bedrock AgentCore SDK
* MCP (Model Context Protocol) ライブラリ
* 実行中の Docker

## MCP（Model Context Protocol）の理解

MCPは、AI モデルが外部データやツールに安全にアクセスできるようにするプロトコルです。主要な概念：

* **ツール**：AI がアクションを実行するために呼び出せる関数
* **Streamable HTTP**：AgentCore Runtime で使用される転送プロトコル
* **セッション分離**：各クライアントは `Mcp-Session-Id` ヘッダーを介して分離されたセッションを取得
* **ステートレス操作**：サーバーはスケーラビリティのためにステートレス操作をサポートする必要がある

AgentCore Runtime は、MCP サーバーがデフォルトパスとして `0.0.0.0:8000/mcp` でホストされることを想定しています。

## 実装手順

### 1. MCP サーバーの作成

以下のコードは、3つのシンプルなツールを持つMCPサーバーを実装しています。このサーバーはミドルウェアを使用して、エラーハンドリングやCORS対応などの機能を提供します。

```python
import logging
import asyncio
from fastmcp import FastMCP
import anyio
from fastmcp.server.middleware import Middleware, MiddlewareContext

# ロギングの設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# MCPサーバーの設定
mcp = FastMCP(
    name="MCPServer"
)

# 各種ミドルウェアを追加
# ...（省略）...

@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together"""
    logger.info(f"Adding {a} and {b}")
    return a + b

@mcp.tool()
def multiply_numbers(a: int, b: int) -> int:
    """Multiply two numbers together"""
    logger.info(f"Multiplying {a} and {b}")
    return a * b

@mcp.tool()
def greet_user(name: str) -> str:
    """Greet a user by name"""
    logger.info(f"Greeting user: {name}")
    return f"こんにちは, {name}! はじめまして."

# エラーハンドリングミドルウェアを追加
# ...（省略）...

if __name__ == "__main__":
    logger.info("MCPサーバーを起動しています...")
    try:
        # FastMCPの設定
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            stateless_http=True,  # ステートレスモード
            uvicorn_config={
                "timeout_keep_alive": 600  # Keep-Alive接続のタイムアウト
            }
        )
    except Exception as e:
        logger.error(f"サーバー実行中にエラーが発生しました: {e}")
```

### 2. ローカルでのテスト

MCPサーバーをローカルで実行し、テストするには以下の手順に従います：

```bash
# ローカルでMCPサーバーを起動
uv run mcp_server.py

# 別のターミナルでクライアントを実行してテスト
uv run mcp_client.py
```

`mcp_client.py` は以下のようなコードで、ローカルのMCPサーバーに接続してツールを呼び出します：

```python
import asyncio
import logging
import argparse
import sys
from typing import Dict, Any

from agent_utils import BaseMCPClient

# クライアントの実装
class MCPClient(BaseMCPClient):
    # ...（省略）...
    pass

async def main():
    parser = argparse.ArgumentParser(description='MCPクライアント')
    parser.add_argument('--mode', choices=['local', 'remote'], default='local', help='接続モード（local/remote）')
    # ...（その他の引数）...
    args = parser.parse_args()
    
    try:
        if args.mode == 'remote':
            # リモートモードの場合
            client = await MCPClient.create_remote_client(
                region=args.region,
                ssm_parameter=args.ssm_parameter,
                secret_id=args.secret_id,
                use_uuid_fixer=args.use_uuid_fixer,
                use_token_cache=args.use_token_cache,
                token_cache_file=args.token_cache_file,
                token_refresh_interval=args.token_refresh_interval
            )
        else:
            # ローカルモードの場合
            client = MCPClient(
                url=args.url, 
                use_uuid_fixer=args.use_uuid_fixer,
                use_token_cache=args.use_token_cache,
                token_cache_file=args.token_cache_file
            )
        
        await client.connect()
        # ここで他の操作を実行...
        await client.close()
            
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. AgentCore Runtime へのデプロイ

MCPサーバーをAWS上のAgentCore Runtimeにデプロイするには、`redeploy_agent.py`スクリプトを使用します：

```bash
# AWS認証情報を設定
export AWS_PROFILE=xxx

# デプロイを実行
uv run redeploy_agent.py
```

`redeploy_agent.py`スクリプトは以下の処理を行います：

1. 既存のエージェントを削除（存在する場合）
2. Amazon Cognito User Poolの設定
3. IAMロールの作成
4. AgentCore Runtimeの設定
5. カスタムDockerfileの適用
6. MCPサーバーのデプロイ
7. CloudWatch Logsグループの設定
8. X-Rayトレースセグメント送信先の設定
9. 設定情報の保存

### 4. リモートからのテスト

デプロイされたMCPサーバーをリモートからテストするには：

```bash
# リモートモードでクライアントを実行
uv run mcp_client.py --mode=remote --use-uuid-fixer
```

`--use-uuid-fixer`オプションは、UUIDの形式の問題を解決するために使用されます。

## MCP Inspectorの使用

MCP Inspectorを使用してローカルサーバーを検査するには：

```bash
npx @modelcontextprotocol/inspector mcp_server.py
```

注意: MCP Inspectorは6247と6277のポートを使用します。Amazon EC2でポートフォワードを行う場合は、両方のポートをフォワードする必要があります。

## 依存関係の管理

requirements.txtからpyproject.tomlに依存関係を移行するには：

```bash
uv add -r requirements.txt -r dev-requirements.txt
```

## トラブルシューティング

一般的な問題と解決策については、[TROUBLESHOOTING.md](TROUBLESHOOTING.md)を参照してください。

## クリーンアップ

チュートリアルで作成したリソースをクリーンアップするには、`redeploy_agent.py`スクリプトの最後にあるクリーンアップセクションを参考にしてください。主なリソースは以下の通りです：

1. AgentCore Runtime
2. ECRリポジトリ
3. IAMロールとポリシー
4. SSMパラメータ
5. Secrets Managerのシークレット

## まとめ

このチュートリアルでは、以下のことを学びました：

* FastMCPを使用したMCPサーバーの構築
* AgentCore Runtimeとの互換性のためのステートレスHTTPトランスポートの設定
* Amazon Cognitoによる認証の設定
* AWS上でのMCPサーバーのデプロイと管理
* ローカルとリモートの両方でのテスト
* ツール呼び出しのためのMCPクライアントの使用

デプロイされたMCPサーバーは、より大規模なAIアプリケーションやワークフローに統合できるようになりました！
