# Amazon Bedrock AgentCore ユーティリティライブラリ

このパッケージは、Amazon Bedrock AgentCoreを使用するための便利なユーティリティを提供します。主な機能は以下の通りです：

- ローカルとデプロイされたエージェントを同じインターフェースで呼び出す
- デプロイされたエージェントのステータス確認
- エージェントの削除
- コマンドラインインターフェース

## インストール

このパッケージは、Amazon Bedrock AgentCore Samplesリポジトリの一部として提供されています。以下のコマンドでインストールできます：

```bash
# リポジトリのクローン
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
cd amazon-bedrock-agentcore-samples

# 依存関係のインストール
pip install -r requirements.txt
```

## 使用方法

### Pythonコードでの使用例

#### ローカルエージェントの呼び出し

```python
from scripts.utils.agentcore_client import AgentCoreClient

# ローカルエージェントを使用
client = AgentCoreClient(local_entrypoint="path/to/strands_claude.py")
response = client.invoke({"prompt": "今の天気は?"})
print(response["content"])
```

#### デプロイされたエージェントの呼び出し

```python
from scripts.utils.agentcore_client import AgentCoreClient

# デプロイされたエージェントを使用
client = AgentCoreClient(
    agent_arn="arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/myAgent",
    region="us-west-2"
)
response = client.invoke({"prompt": "今の天気は?"})
print(response["content"])
```

#### エージェントのデプロイ

```python
from scripts.utils.deploy_utils import deploy_agent, wait_for_status

# エージェントをデプロイ
result = deploy_agent(
    entrypoint="path/to/strands_claude.py",
    execution_role="arn:aws:iam::123456789012:role/AgentCoreRole",
    requirements_file="requirements.txt",
    region="us-west-2",
    agent_name="myAgent"
)

# デプロイが完了するまで待機
wait_for_status(
    agent_id=result.agent_id,
    target_status=["READY"],
    region="us-west-2"
)

print(f"Agent deployed: {result.agent_arn}")
```

#### エージェントの削除

```python
from scripts.utils.deploy_utils import delete_agent

# エージェントを削除
response = delete_agent(
    agent_id="myAgent",
    ecr_uri="123456789012.dkr.ecr.us-west-2.amazonaws.com/myAgent",
    role_name="AgentCoreRole",
    region="us-west-2"
)

print("Agent deleted")
```

### コマンドラインでの使用例

#### エージェントの呼び出し

```bash
# ローカルエージェントの呼び出し
python -m scripts.utils.cli invoke --local-entrypoint "path/to/strands_claude.py" --payload '{"prompt": "今の天気は?"}'

# デプロイされたエージェントの呼び出し
python -m scripts.utils.cli invoke --agent-arn "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/myAgent" --region "us-west-2" --payload '{"prompt": "今の天気は?"}'
```

#### エージェントのデプロイ

```bash
python -m scripts.utils.cli deploy --entrypoint "path/to/strands_claude.py" --execution-role "arn:aws:iam::123456789012:role/AgentCoreRole" --requirements-file "requirements.txt" --region "us-west-2" --agent-name "myAgent"
```

#### エージェントのステータス確認

```bash
python -m scripts.utils.cli status --agent-id "myAgent" --region "us-west-2"
```

#### エージェントのステータスが特定の状態になるまで待機

```bash
python -m scripts.utils.cli wait --agent-id "myAgent" --status "READY" --region "us-west-2"
```

#### エージェントの削除

```bash
python -m scripts.utils.cli delete --agent-id "myAgent" --ecr-uri "123456789012.dkr.ecr.us-west-2.amazonaws.com/myAgent" --role-name "AgentCoreRole" --region "us-west-2"
```

#### デプロイされたエージェントの一覧表示

```bash
python -m scripts.utils.cli list --region "us-west-2"
```

## Jupyter Notebookでの使用例

Jupyter Notebookでは、以下のように使用できます：

```python
# 必要なモジュールをインポート
from scripts.utils.agentcore_client import AgentCoreClient
from scripts.utils.deploy_utils import deploy_agent, wait_for_status, delete_agent

# エージェントをデプロイ
result = deploy_agent(
    entrypoint="strands_claude.py",
    execution_role=agentcore_iam_role['Role']['Arn'],
    requirements_file="requirements.txt",
    region=region,
    agent_name="myAgent"
)

# デプロイが完了するまで待機
wait_for_status(
    agent_id=result.agent_id,
    target_status=["READY"],
    region=region
)

# クライアントを初期化
client = AgentCoreClient(
    agent_arn=result.agent_arn,
    region=region
)

# エージェントを呼び出し
response = client.invoke({"prompt": "今の天気は?"})

# レスポンスを表示
from IPython.display import Markdown, display
if isinstance(response["content"], dict) and "message" in response["content"]:
    display(Markdown(response["content"]["message"]))
else:
    display(Markdown(str(response["content"])))

# エージェントを削除
delete_agent(
    agent_id=result.agent_id,
    ecr_uri=result.ecr_uri,
    region=region
)
```

## API リファレンス

### AgentCoreClient

```python
class AgentCoreClient:
    def __init__(self, agent_arn=None, local_entrypoint=None, region=None):
        """
        AgentCoreClientの初期化
        
        Parameters:
        - agent_arn: デプロイされたエージェントのARN（デプロイモード用）
        - local_entrypoint: ローカルエージェントのエントリポイント（ローカルモード用）
        - region: AWSリージョン
        """
        
    def invoke(self, payload):
        """
        エージェントを呼び出す（統一インターフェース）
        
        Parameters:
        - payload: エージェントに送信するペイロード
        
        Returns:
        - response: エージェントからのレスポンス（統一フォーマット）
        """
        
    def get_status(self):
        """
        エージェントのステータスを取得
        
        Returns:
        - status: エージェントのステータス情報
        """
```

### deploy_utils

```python
def deploy_agent(entrypoint, execution_role, requirements_file=None, region=None, agent_name=None):
    """
    エージェントをデプロイ
    
    Parameters:
    - entrypoint: エントリポイントファイルのパス
    - execution_role: 実行ロールのARN
    - requirements_file: 要件ファイルのパス（オプション）
    - region: AWSリージョン（オプション）
    - agent_name: エージェント名（オプション）
    
    Returns:
    - launch_result: デプロイ結果
    """
    
def check_status(agent_id, region=None):
    """
    エージェントのステータスを確認
    
    Parameters:
    - agent_id: エージェントID
    - region: AWSリージョン（オプション）
    
    Returns:
    - response: ステータス情報
    """
    
def wait_for_status(agent_id, target_status=['READY'], region=None, timeout=600, interval=10):
    """
    特定のステータスになるまで待機
    
    Parameters:
    - agent_id: エージェントID
    - target_status: 待機するステータスのリスト（デフォルト: ['READY']）
    - region: AWSリージョン（オプション）
    - timeout: タイムアウト秒数（デフォルト: 600秒）
    - interval: チェック間隔秒数（デフォルト: 10秒）
    
    Returns:
    - response: 最終ステータス情報
    """
    
def delete_agent(agent_id, ecr_uri=None, role_name=None, region=None):
    """
    エージェントを削除
    
    Parameters:
    - agent_id: エージェントID
    - ecr_uri: ECR URI（オプション）
    - role_name: IAMロール名（オプション）
    - region: AWSリージョン（オプション）
    
    Returns:
    - response: 削除結果
    """
    
def list_agents(region=None):
    """
    デプロイされたエージェントの一覧を取得
    
    Parameters:
    - region: AWSリージョン（オプション）
    
    Returns:
    - agents: エージェントのリスト
    """
```

## コマンドラインインターフェース

```
usage: cli.py [-h] {invoke,deploy,status,wait,delete,list} ...

Amazon Bedrock AgentCore CLI

positional arguments:
  {invoke,deploy,status,wait,delete,list}
                        Command to execute
    invoke              Invoke an agent
    deploy              Deploy an agent
    status              Check agent status
    wait                Wait for agent status
    delete              Delete an agent
    list                List deployed agents

optional arguments:
  -h, --help            show this help message and exit
```

## 注意事項

- このパッケージを使用するには、AWS認証情報が適切に設定されている必要があります。
- ローカルエージェントを呼び出す場合は、必要なパッケージがインストールされている必要があります。
- ARM64アーキテクチャのサポートが自動的に有効になります。
