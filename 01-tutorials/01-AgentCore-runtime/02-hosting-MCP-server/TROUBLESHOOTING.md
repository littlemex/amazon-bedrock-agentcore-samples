# MCPサーバーのトラブルシューティングガイド

このドキュメントでは、Amazon Bedrock AgentCore MCPサーバーで発生する可能性のある問題と、その解決方法について説明します。

## 一般的なエラーと解決策

### 1. 内部サーバーエラー（Internal Server Error）

```json
{"jsonrpc":"2.0","error":{"code":-32603,"message":"An internal error occurred while processing the request."},"id":"2f5b7691-c69e-455c-9747-4679224d2028"}
```

このエラーは様々な原因で発生する可能性がありますが、主な原因は以下の通りです：

#### 1.1 CloudWatch Logsへの権限不足

エラーメッセージ例：
```
User: arn:aws:sts::320462930492:assumed-role/agentcore-mcp_server-role/Genesis-serviceExecutor-56c66ad5-c4a2-48d9-aad1-46d25cd4c067 is not authorized to perform: logs:PutLogEvents on resource: arn:aws:logs:us-east-1:320462930492:log-group:agents/mcp-server-logs:log-stream:default
```

**解決策**：
- `utils.py`の`create_agentcore_role`関数を修正して、`agents/mcp-server-logs`ロググループへの書き込み権限を追加します。
- 既に修正済みの場合は、エージェントを再デプロイして新しいIAMロールポリシーを適用します。

#### 1.2 CloudWatch Logsグループの不足

エラーメッセージ例：
```
ERROR:amazon.opentelemetry.distro.exporter.otlp.aws.logs.otlp_aws_logs_exporter:Failed to export logs batch code: 400, reason: 'The specified log group does not exist.
```

**解決策**：
- `setup_log_groups.py`スクリプトを実行して、必要なCloudWatch Logsグループを作成します。
- または、エージェントを再デプロイして、デプロイプロセスの一部としてロググループを作成します。

#### 1.3 Content-Typeヘッダーの問題

エラーメッセージ例：
```
WARNING Missing Content-Type transport_security.py:92 header in POST request
```

**解決策**：
- クライアント側でリクエストを送信する際に、適切なContent-Typeヘッダー（通常は`application/json`）を設定していることを確認します。
- `my_mcp_client_remote.py`を使用している場合は、リクエストヘッダーが正しく設定されていることを確認します。
- セッションIDを明示的に設定します：
  ```python
  session_id = str(uuid.uuid4())
  headers = {
      "authorization": f"Bearer {bearer_token}",
      "Content-Type": "application/json",
      "x-session-id": session_id
  }
  ```
- FastMCPサーバー側でミドルウェアを追加して、Content-Typeヘッダーを自動的に処理します：
  ```python
  @mcp.middleware
  async def add_content_type_header(request, call_next):
      if "content-type" not in request.headers:
          request.headers["content-type"] = "application/json"
      return await call_next(request)
  ```

### 2. OpenTelemetry関連のエラー

#### 2.1 トレースセグメントの送信先エラー

エラーメッセージ例：
```
ERROR:opentelemetry.exporter.otlp.proto.http.trace_exporter:Failed to export batch code: 400, reason: �The OTLP API is supported with CloudWatch Logs as a Trace Segment Destination. Please enable the CloudWatch Logs destination for your traces using the UpdateTraceSegmentDestination API
```

**解決策**：
1. X-RayのトレースセグメントをCloudWatch Logsに送信するように設定します：
   ```python
   # setup_trace_destination.py を作成して実行
   import boto3
   
   xray_client = boto3.client('xray')
   xray_client.update_trace_segment_destination(
       Destination="CloudWatchLogs"
   )
   ```

2. CloudWatch Logsリソースポリシーを設定して、X-RayがCloudWatch Logsにアクセスできるようにします：
   ```python
   logs_client = boto3.client('logs')
   policy_document = {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Principal": {"Service": "xray.amazonaws.com"},
               "Action": ["logs:PutLogEvents", "logs:CreateLogStream"],
               "Resource": [
                   f"arn:aws:logs:{region}:{account_id}:log-group:aws/spans:*",
                   f"arn:aws:logs:{region}:{account_id}:log-group:/aws/application-signals/data:*"
               ]
           }
       ]
   }
   logs_client.put_resource_policy(
       policyName="TransactionSearchPolicy",
       policyDocument=json.dumps(policy_document)
   )
   ```

3. IAMロールポリシーにX-Ray APIへのアクセス権限を追加します：
   ```json
   {
       "Sid": "OTELPermissions",
       "Effect": "Allow",
       "Action": [
           "xray:PutTraceSegments",
           "xray:PutTelemetryRecords",
           "xray:GetSamplingRules",
           "xray:GetSamplingTargets",
           "xray:GetSamplingStatisticSummaries",
           "xray:GetTraceSegmentDestination",
           "xray:UpdateTraceSegmentDestination",
           "xray:UpdateIndexingRule"
       ],
       "Resource": "*"
   }
   ```

#### 2.2 aws-opentelemetry-distroパッケージの不足

**解決策**：
- `requirements.txt`に`aws-opentelemetry-distro>=0.10.0`が含まれていることを確認します。
- Dockerfileで`opentelemetry-instrument`コマンドが正しく使用されていることを確認します。

### 3. JSON-RPC関連のエラー

#### 3.1 内部JSON-RPCエラー（-32603）

エラーメッセージ例：
```json
{"jsonrpc":"2.0","error":{"code":-32603,"message":"An internal error occurred while processing the request."},"id":"c6c4d0cb-757b-4c13-87c3-d11818a14cb7"}
```

このエラーは、JSON-RPCの内部エラーコード-32603で、サーバー側で処理できない例外が発生したことを示します。

**解決策**：
1. **エラーハンドリングの強化**：
   ```python
   @mcp.exception_handler(Exception)
   def handle_general_exception(exc: Exception):
       import traceback
       logger.error(f"未処理の例外が発生しました: {exc}\n{traceback.format_exc()}")
       return {"error": str(exc)}
   ```

2. **リクエストIDの形式を修正**：
   - 数値ではなく文字列のUUIDを使用する
   ```python
   request_id = str(uuid.uuid4())
   payload = {
       "jsonrpc": "2.0",
       "method": "initialize",
       "params": {},
       "id": request_id
   }
   ```

3. **デバッグログの強化**：
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### 4. ストリーム処理関連のエラー

#### 4.1 ClosedResourceError

エラーメッセージ例：
```
"severityText": "ERROR",
"body": "Error in message router",
"attributes": {
    "exception.type": "ClosedResourceError",
    "code.file.path": "/usr/local/lib/python3.10/site-packages/mcp/server/streamable_http.py",
    "code.function.name": "message_router",
    "exception.stacktrace": "Traceback (most recent call last):
      ...
      File "/usr/local/lib/python3.10/site-packages/anyio/streams/memory.py", line 93, in receive_nowait
        raise ClosedResourceError
      anyio.ClosedResourceError
```

このエラーは、MCPサーバーの内部処理に関連するもので、`streamable_http.py`の`message_router`関数内でストリームリソースが既に閉じられているのにアクセスしようとしたことが原因です。クライアントが切断（タイムアウトや強制終了）した場合、サーバー側でストリームが閉じられたことを検出できず、引き続きメッセージを送信しようとすることで発生します。

**解決策**：
1. **MCPサーバーの設定変更**:
   ```python
   # 現在の設定
   mcp = FastMCP(host="0.0.0.0", stateless_http=True)
   
   # 推奨設定
   mcp = FastMCP(
       host="0.0.0.0",
       stateless_http=False,  # ステートフルモードに変更
       connection_timeout=120,  # タイムアウト値を増やす（秒単位）
       keep_alive=True,  # 接続を維持する
       default_headers={
           "Content-Type": "application/json",
           "content-type": "application/json"  # 小文字のヘッダーも追加
       }
   )
   ```

2. **カスタムエラーハンドラーの追加**:
   ```python
   # ClosedResourceErrorを処理するためのカスタムエラーハンドラー
   @mcp.error_handler()
   async def handle_closed_resource_error(error: Exception, ctx):
       """ClosedResourceErrorを処理するカスタムエラーハンドラー"""
       import anyio
       if isinstance(error, (anyio.ClosedResourceError, anyio.BrokenResourceError)):
           logger.warning(f"クライアント接続が閉じられました: {error}")
           return {"status": "error", "message": "クライアント接続が閉じられました"}
       # その他のエラーは通常のエラーハンドリングに委ねる
       return None
   ```

3. **クライアント側の改善**:
   ```python
   # ヘッダーを拡張（小文字のcontent-typeも追加）
   headers = {
       "authorization": f"Bearer {bearer_token}",
       "Content-Type": "application/json",
       "content-type": "application/json",  # 小文字のヘッダーも追加
       "Accept": "application/json, text/event-stream",
       "Mcp-Session-Id": f"session-{int(time.time())}"  # セッションIDを明示的に設定
   }
   
   # タイムアウト値を増やす
   async with streamablehttp_client(
       mcp_url, 
       headers, 
       timeout=180,  # タイムアウト値を増やす
       sse_read_timeout=300,  # SSE読み取りタイムアウトも増やす
       terminate_on_close=True  # 終了時に確実に接続を閉じる
   ) as (read_stream, write_stream, get_session_id):
       # ...
   ```

2. **ロギングの強化**:
   ```python
   import logging
   
   # ロギングの設定
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)
   
   # ログ出力の例
   logger.info("MCPサーバーを起動しています...")
   logger.error("エラーが発生しました", exc_info=True)
   ```

3. **コンテナリソースの増加**:
   - AgentCoreランタイムのコンテナに割り当てられるメモリとCPUリソースを増やす（最低2GB推奨）

4. **MCPライブラリのバージョン確認**:
   - 最新の安定版MCPライブラリを使用しているか確認し、必要に応じて更新する
   - `anyio`のバージョンも明示的に指定して、互換性の問題を回避する

## 再デプロイ手順

問題を解決するために、以下の手順でMCPサーバーを再デプロイします：

1. 修正されたコードがあることを確認します：
   - `utils.py`のIAMロールポリシーが更新されていること
   - `setup_log_groups.py`が存在すること
   - `redeploy_agent.py`がロググループ作成を含むように更新されていること
   - `mcp_server.py`がステートフルモードで設定されていること

2. 再デプロイを実行します：
   ```bash
   cd 01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server
   python redeploy_agent.py
   ```

3. デプロイが完了したら、接続テストを実行します：
   ```bash
   python my_mcp_client_remote_fixed.py
   ```

## UUIDフォーマットの問題

MCPサーバーとクライアント間の通信で、UUIDフォーマットに関する問題が発生することがあります。

エラーメッセージ例：
```
pydantic.errors.PydanticCustomError: Input should be a valid UUID, invalid character: expecting a-f, A-F, 0-9, got 'x'
```

**解決策**：
1. **クライアント側でUUIDフォーマットを修正**:
   ```python
   def fix_uuid_format(content):
       """UUIDの形式を修正する（引用符で囲まれていないUUIDを引用符で囲む）"""
       if isinstance(content, bytes):
           text = content.decode('utf-8')
       else:
           text = content
           
       # "id":UUID パターンを検出して修正
       pattern = r'"id":([^",\s\}]+)'
       replacement = r'"id":"\1"'
       fixed_text = re.sub(pattern, replacement, text)
       
       return fixed_text.encode('utf-8') if isinstance(content, bytes) else fixed_text
   ```

2. **モンキーパッチを適用**:
   ```python
   # JSONRPCMessageのmodel_validate_jsonメソッドをモンキーパッチ
   original_model_validate_json = JSONRPCMessage.model_validate_json
   
   # モンキーパッチ: UUIDの形式を修正するメソッド
   @classmethod
   def patched_model_validate_json(cls, json_data, **kwargs):
       fixed_json = fix_uuid_format(json_data)
       return original_model_validate_json(json_data=fixed_json, **kwargs)
   
   # モンキーパッチを適用
   JSONRPCMessage.model_validate_json = patched_model_validate_json
   ```

## ログの収集と分析

問題のトラブルシューティングに役立つログを収集するには、以下のスクリプトを使用します：

1. 基本的なログ収集：
   ```bash
   python collect_mcp_logs.py
   ```

2. 詳細なログ収集と分析：
   ```bash
   python collect_mcp_logs_advanced.py
   ```

3. 特定のエージェントIDに関連するログの収集：
   ```bash
   python collect_mcp_logs_specific.py
   ```

これらのスクリプトは、CloudWatchログからエラー情報を収集し、問題の診断に役立つ情報を提供します。

## その他の問題

上記の解決策で問題が解決しない場合は、以下を確認してください：

1. AWS認証情報が正しく設定されていること
2. 必要なIAM権限がすべて付与されていること
3. ネットワーク接続が正常であること
4. リージョン設定が一貫していること

詳細なトラブルシューティングが必要な場合は、AWS CloudWatchログを確認して、より詳細なエラー情報を取得してください。
