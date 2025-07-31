import asyncio
import logging
import re
import argparse
import json
import sys
import boto3
import time
from boto3.session import Session
from typing import Optional, Dict, Any, Callable, ClassVar, Tuple

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import JSONRPCMessage

# ロギングの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_client_remote2")

class UUIDFixer:
    """UUIDフォーマットの問題を修正するためのユーティリティクラス"""
    
    _original_validate_json: ClassVar[Optional[Callable]] = None
    
    @staticmethod
    def fix_uuid_format(content: Any) -> Any:
        """UUIDの形式を修正する（引用符で囲まれていないUUIDを引用符で囲む）"""
        if isinstance(content, bytes):
            text = content.decode('utf-8')
        else:
            text = content
        
        # 詳細なログ出力
        logger.debug(f"修正前の生データ: {repr(text[:300])}...")
        
        # 問題のある部分を特定するための正規表現パターン
        # 1. "id":UUID パターンを検出して修正
        pattern1 = r'"id":([^",\s\}\]]+)'
        replacement1 = r'"id":"\1"'
        fixed_text = re.sub(pattern1, replacement1, text)
        logger.debug(f"パターン1適用後: {repr(fixed_text[:300])}...")
        
        # 2. エラー行の列116付近の問題を修正するための特別なパターン
        # 例: {"jsonrpc":"2.0","error...4dfc-825d-4d51afa4da30}
        pattern2 = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})}'
        replacement2 = r'"\1"}'
        fixed_text = re.sub(pattern2, replacement2, fixed_text)
        logger.debug(f"パターン2適用後: {repr(fixed_text[:300])}...")
        
        # 3. エラーメッセージから特定した列116付近の問題に対する特別な修正
        # 例: "error...42e6-aa5b-b6c9f3f32620}
        pattern3 = r'"error([^"]*?)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})}'
        replacement3 = r'"error\1"\2"}'
        fixed_text = re.sub(pattern3, replacement3, fixed_text)
        logger.debug(f"パターン3適用後: {repr(fixed_text[:300])}...")
        
        # 4. 一般的なUUIDパターンを検出して引用符で囲む
        pattern4 = r'([^":\s,\{\[])([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})([^":\s,\}\]])'
        replacement4 = r'\1"\2"\3'
        fixed_text = re.sub(pattern4, replacement4, fixed_text)
        logger.debug(f"パターン4適用後: {repr(fixed_text[:300])}...")
        
        # 5. 行末のUUIDパターンを検出して引用符で囲む
        pattern5 = r'([^":\s,\{\[])([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'
        replacement5 = r'\1"\2"'
        fixed_text = re.sub(pattern5, replacement5, fixed_text)
        logger.debug(f"パターン5適用後: {repr(fixed_text[:300])}...")
        
        # 6. 行頭のUUIDパターンを検出して引用符で囲む
        pattern6 = r'^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})([^":\s,\}\]])'
        replacement6 = r'"\1"\2'
        fixed_text = re.sub(pattern6, replacement6, fixed_text)
        logger.debug(f"パターン6適用後: {repr(fixed_text[:300])}...")
        
        # 7. 特定のエラーパターンを修正
        if "error" in fixed_text and "column 116" in text:
            # 列116付近の文字を詳細に調査
            if len(fixed_text) > 120:
                logger.debug(f"列116付近の文字: {repr(fixed_text[110:120])}")
                
                # 特定の位置に引用符を挿入
                try:
                    chars = list(fixed_text)
                    if 115 < len(chars) and chars[115] not in ['"', "'"]:
                        chars.insert(115, '"')
                        logger.debug("列115に引用符を挿入しました")
                    if 117 < len(chars) and chars[117] not in ['"', "'"]:
                        chars.insert(117, '"')
                        logger.debug("列117に引用符を挿入しました")
                    fixed_text = ''.join(chars)
                except Exception as e:
                    logger.error(f"特定位置への引用符挿入中にエラーが発生: {e}")
        
        if fixed_text != text:
            logger.info("UUID形式を修正しました")
            logger.debug(f"修正前: {repr(text[:200])}...")
            logger.debug(f"修正後: {repr(fixed_text[:200])}...")
            
            # JSONとして解析できるか確認
            try:
                json.loads(fixed_text)
                logger.info("修正後のJSONは有効です")
            except json.JSONDecodeError as e:
                logger.warning(f"修正後のJSONは依然として無効です: {e}")
        
        return fixed_text.encode('utf-8') if isinstance(content, bytes) else fixed_text
    
    @classmethod
    def apply_patch(cls) -> None:
        """JSONRPCMessageのmodel_validate_jsonメソッドをモンキーパッチ"""
        if cls._original_validate_json is None:
            cls._original_validate_json = JSONRPCMessage.model_validate_json
            
            @classmethod
            def patched_model_validate_json(mcls, json_data, **kwargs):
                try:
                    # 元のデータをログ出力
                    if isinstance(json_data, bytes):
                        logger.debug(f"元のJSON (bytes): {repr(json_data[:300])}...")
                    else:
                        logger.debug(f"元のJSON (str): {repr(json_data[:300])}...")
                    
                    # UUIDフォーマットを修正
                    fixed_json = cls.fix_uuid_format(json_data)
                    
                    # 修正後のデータをログ出力
                    if isinstance(fixed_json, bytes):
                        logger.debug(f"修正後のJSON (bytes): {repr(fixed_json[:300])}...")
                    else:
                        logger.debug(f"修正後のJSON (str): {repr(fixed_json[:300])}...")
                    
                    try:
                        # 修正したJSONで検証を試みる
                        result = cls._original_validate_json(json_data=fixed_json, **kwargs)
                        logger.info("JSONの検証に成功しました")
                        return result
                    except Exception as e:
                        logger.error(f"修正後のJSONの検証に失敗しました: {e}")
                        
                        # エラーメッセージから問題の箇所を特定
                        error_msg = str(e)
                        if "column" in error_msg and isinstance(fixed_json, (str, bytes)):
                            try:
                                # エラー位置を特定
                                col_match = re.search(r'column (\d+)', error_msg)
                                if col_match:
                                    col_pos = int(col_match.group(1))
                                    logger.debug(f"エラー位置: 列 {col_pos}")
                                    
                                    # エラー周辺の文字を表示
                                    start_pos = max(0, col_pos - 10)
                                    end_pos = min(len(fixed_json), col_pos + 10)
                                    context = fixed_json[start_pos:end_pos]
                                    if isinstance(context, bytes):
                                        context = context.decode('utf-8', errors='replace')
                                    logger.debug(f"エラー周辺の文字: {repr(context)}")
                                    
                                    # 特定の位置に引用符を挿入する緊急修正
                                    if isinstance(fixed_json, bytes):
                                        text = fixed_json.decode('utf-8', errors='replace')
                                    else:
                                        text = fixed_json
                                    
                                    # 問題の位置に引用符を挿入
                                    chars = list(text)
                                    if col_pos < len(chars):
                                        if chars[col_pos-1] not in ['"', "'"]:
                                            chars.insert(col_pos-1, '"')
                                            logger.debug(f"列 {col_pos-1} に引用符を挿入しました")
                                        if col_pos < len(chars) and chars[col_pos] not in ['"', "'"]:
                                            chars.insert(col_pos, '"')
                                            logger.debug(f"列 {col_pos} に引用符を挿入しました")
                                    
                                    emergency_fixed = ''.join(chars)
                                    logger.debug(f"緊急修正後: {repr(emergency_fixed[:300])}...")
                                    
                                    try:
                                        # 緊急修正したJSONで再度検証
                                        result = cls._original_validate_json(json_data=emergency_fixed, **kwargs)
                                        logger.info("緊急修正後のJSONの検証に成功しました")
                                        return result
                                    except Exception as e2:
                                        logger.error(f"緊急修正後のJSONの検証にも失敗しました: {e2}")
                            except Exception as ex:
                                logger.error(f"緊急修正中にエラーが発生しました: {ex}")
                        
                        # 元のJSONデータを使用して再試行
                        logger.info("元のJSONデータを使用して再試行します")
                        return cls._original_validate_json(json_data=json_data, **kwargs)
                except Exception as e:
                    logger.error(f"モンキーパッチ内でエラーが発生しました: {e}")
                    # 元のメソッドを使用
                    return cls._original_validate_json(json_data=json_data, **kwargs)
            
            JSONRPCMessage.model_validate_json = patched_model_validate_json
            logger.info("強化されたUUIDフィクサーを適用しました")
    
    @classmethod
    def remove_patch(cls) -> None:
        """モンキーパッチを元に戻す"""
        if cls._original_validate_json is not None:
            JSONRPCMessage.model_validate_json = cls._original_validate_json
            cls._original_validate_json = None
            logger.info("UUIDフィクサーを削除しました")


class AWSAuthenticator:
    """AWS認証関連の処理を行うクラス"""
    
    def __init__(self, region: Optional[str] = None):
        """
        AWSAuthenticatorを初期化
        
        Args:
            region: AWSリージョン。Noneの場合はデフォルトリージョンを使用
        """
        self.boto_session = Session(region_name=region)
        self.region = self.boto_session.region_name
        logger.info(f"AWSリージョン: {self.region}")
    
    def get_agent_arn_from_ssm(self, parameter_name: str = '/mcp_server/runtime/agent_arn') -> str:
        """
        SSMパラメータストアからエージェントARNを取得
        
        Args:
            parameter_name: SSMパラメータ名
            
        Returns:
            エージェントARN
        """
        try:
            ssm_client = self.boto_session.client('ssm')
            response = ssm_client.get_parameter(Name=parameter_name)
            agent_arn = response['Parameter']['Value']
            logger.info(f"エージェントARNを取得しました: {agent_arn}")
            return agent_arn
        except Exception as e:
            logger.error(f"エージェントARNの取得に失敗しました: {e}")
            raise
    
    def get_bearer_token_from_secrets(self, secret_id: str = 'mcp_server/cognito/credentials') -> str:
        """
        Secrets Managerからベアラートークンを取得
        
        Args:
            secret_id: シークレットID
            
        Returns:
            ベアラートークン
        """
        try:
            secrets_client = self.boto_session.client('secretsmanager')
            response = secrets_client.get_secret_value(SecretId=secret_id)
            secret_value = response['SecretString']
            parsed_secret = json.loads(secret_value)
            bearer_token = parsed_secret['bearer_token']
            logger.info("ベアラートークンを取得しました")
            return bearer_token
        except Exception as e:
            logger.error(f"ベアラートークンの取得に失敗しました: {e}")
            raise
    
    def get_remote_mcp_url(self, agent_arn: str) -> str:
        """
        リモートMCPサーバーのURLを生成
        
        Args:
            agent_arn: エージェントARN
            
        Returns:
            MCPサーバーのURL
        """
        encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
        mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
        logger.info(f"MCPサーバーURL: {mcp_url}")
        return mcp_url
    
    def create_auth_headers(self, bearer_token: str) -> Dict[str, str]:
        """
        認証ヘッダーを作成
        
        Args:
            bearer_token: ベアラートークン
            
        Returns:
            認証ヘッダー
        """
        # セッションIDを生成
        session_id = f"session-{int(time.time())}"
        logger.info(f"セッションID: {session_id}")
        
        headers = {
            "authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "content-type": "application/json",  # 小文字のヘッダーも追加
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id,  # セッションIDを明示的に設定
            "X-Session-Id": session_id,  # 別の形式でもセッションIDを設定
            "x-amz-date": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),  # AWS署名用の日付ヘッダー
            "x-amz-content-sha256": "UNSIGNED-PAYLOAD"  # 署名のためのSHA256ヘッダー
        }
        return headers


class MCPClient:
    """MCPクライアントのラッパークラス"""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None, use_uuid_fixer: bool = False):
        """
        MCPクライアントを初期化
        
        Args:
            url: MCPサーバーのURL
            headers: リクエストヘッダー
            use_uuid_fixer: UUIDフィクサーを使用するかどうか
        """
        self.url = url
        self.headers = headers or {}
        self.use_uuid_fixer = use_uuid_fixer
    
    @classmethod
    async def create_remote_client(
        cls,
        region: Optional[str] = None,
        ssm_parameter: str = '/mcp_server/runtime/agent_arn',
        secret_id: str = 'mcp_server/cognito/credentials',
        use_uuid_fixer: bool = True
    ) -> 'MCPClient':
        """
        リモートMCPクライアントを作成
        
        Args:
            region: AWSリージョン
            ssm_parameter: エージェントARNを取得するSSMパラメータ名
            secret_id: ベアラートークンを取得するシークレットID
            use_uuid_fixer: UUIDフィクサーを使用するかどうか
            
        Returns:
            MCPClient: 初期化されたMCPクライアント
        """
        try:
            # AWS認証情報を取得
            authenticator = AWSAuthenticator(region=region)
            agent_arn = authenticator.get_agent_arn_from_ssm(parameter_name=ssm_parameter)
            bearer_token = authenticator.get_bearer_token_from_secrets(secret_id=secret_id)
            
            # URLとヘッダーを生成
            url = authenticator.get_remote_mcp_url(agent_arn)
            headers = authenticator.create_auth_headers(bearer_token)
            
            # クライアントを作成して返す
            return cls(url=url, headers=headers, use_uuid_fixer=use_uuid_fixer)
        except Exception as e:
            logger.error(f"リモートクライアントの作成に失敗しました: {e}")
            raise
        
    def _is_token_expired(self, token: str) -> bool:
        """
        トークンの有効期限が切れているかどうかを確認
        
        Args:
            token: JWTトークン
            
        Returns:
            有効期限が切れている場合はTrue、そうでない場合はFalse
        """
        try:
            # トークンをデコードして有効期限を確認
            import base64
            import json
            import time
            
            # JWTの2番目の部分（ペイロード）を取得
            payload = token.split('.')[1]
            # Base64デコード（パディングを調整）
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            claims = json.loads(decoded)
            
            # 有効期限を確認
            if 'exp' in claims:
                exp_time = claims['exp']
                current_time = time.time()
                if current_time > exp_time:
                    logger.warning(f"トークンの有効期限が切れています。有効期限: {exp_time}, 現在時刻: {current_time}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"トークンの有効期限確認中にエラーが発生しました: {e}")
            # エラーが発生した場合は、安全のためトークンを更新する
            return True
    
    async def connect(self) -> None:
        """MCPサーバーに接続してツール一覧を取得"""
        logger.info(f"MCPサーバーに接続します: {self.url}")
        
        # ヘッダーにContent-Typeが含まれていることを確認
        if "Content-Type" not in self.headers and "content-type" not in self.headers:
            self.headers["Content-Type"] = "application/json"
            self.headers["content-type"] = "application/json"  # 小文字のヘッダーも追加
        
        # 認証トークンの有効期限を確認し、必要に応じて更新
        if "authorization" in self.headers:
            token = self.headers["authorization"].replace("Bearer ", "")
            if self._is_token_expired(token):
                logger.warning("認証トークンの有効期限が切れています。新しいトークンを取得します。")
                try:
                    # Secrets Managerから新しいトークンを取得
                    authenticator = AWSAuthenticator()
                    bearer_token = authenticator.get_bearer_token_from_secrets()
                    self.headers["authorization"] = f"Bearer {bearer_token}"
                    logger.info("認証トークンを更新しました")
                except Exception as e:
                    logger.error(f"認証トークンの更新に失敗しました: {e}")
        
        logger.debug(f"Headers: {self.headers}")
        
        if self.use_uuid_fixer:
            UUIDFixer.apply_patch()
        
        # リトライ回数と間隔を設定
        max_retries = 3
        retry_delay = 2.0
        
        for retry_count in range(max_retries + 1):
            try:
                logger.info(f"Creating streamable HTTP client... (試行 {retry_count + 1}/{max_retries + 1})")
                async with streamablehttp_client(
                    self.url, 
                    self.headers, 
                    timeout=400,  # タイムアウト値を増やす
                    terminate_on_close=False,
                    sse_read_timeout=600  # SSE読み取りタイムアウトも増やす
                ) as (read_stream, write_stream, get_session_id):
                    logger.info("Streamable HTTP client created successfully")
                    
                    logger.info("Creating client session...")
                    async with ClientSession(read_stream, write_stream) as session:
                        logger.info("🔄 Initializing MCP session...")
                        await session.initialize()
                        logger.info("✓ MCP session initialized")
                        
                        # セッションIDを取得して表示
                        session_id = get_session_id()
                        if session_id:
                            logger.info(f"Session ID: {session_id}")
                        
                        logger.info("🔄 Listing available tools...")
                        tool_result = await session.list_tools()
                        
                        logger.info("📋 Available MCP Tools:")
                        logger.info("=" * 50)
                        for tool in tool_result.tools:
                            logger.info(f"🔧 {tool.name}")
                            logger.info(f"   Description: {tool.description}")
                            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                                properties = tool.inputSchema.get('properties', {})
                                if properties:
                                    logger.info(f"   Parameters: {list(properties.keys())}")
                        
                        logger.info(f"✅ Successfully connected to MCP server!")
                        logger.info(f"Found {len(tool_result.tools)} tools available.")
                
                # 接続に成功したらループを抜ける
                break
                
            except Exception as e:
                if retry_count < max_retries:
                    logger.warning(f"接続に失敗しました（試行 {retry_count + 1}/{max_retries + 1}）: {e}")
                    logger.info(f"{retry_delay}秒後に再試行します...")
                    await asyncio.sleep(retry_delay)
                    # 次の試行では待機時間を増やす
                    retry_delay *= 1.5
                else:
                    logger.error(f"❌ Error connecting to MCP server after {max_retries + 1} attempts: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise
        
            finally:
                if self.use_uuid_fixer:
                    UUIDFixer.remove_patch()


async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='MCPクライアント')
    parser.add_argument('--mode', choices=['local', 'remote'], default='local', help='接続モード（local/remote）')
    parser.add_argument('--url', default="http://localhost:18000/mcp", help='ローカルMCPサーバーのURL')
    parser.add_argument('--region', help='AWSリージョン（リモートモード用）')
    parser.add_argument('--ssm-parameter', default='/mcp_server/runtime/agent_arn', help='エージェントARNを取得するSSMパラメータ名')
    parser.add_argument('--secret-id', default='mcp_server/cognito/credentials', help='ベアラートークンを取得するシークレットID')
    parser.add_argument('--use-uuid-fixer', action='store_true', help='UUIDフィクサーを使用する')
    args = parser.parse_args()
    
    try:
        if args.mode == 'remote':
            # リモートモードの場合
            client = await MCPClient.create_remote_client(
                region=args.region,
                ssm_parameter=args.ssm_parameter,
                secret_id=args.secret_id,
                use_uuid_fixer=args.use_uuid_fixer
            )
        else:
            # ローカルモードの場合
            client = MCPClient(url=args.url, use_uuid_fixer=args.use_uuid_fixer)
        
        await client.connect()
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
