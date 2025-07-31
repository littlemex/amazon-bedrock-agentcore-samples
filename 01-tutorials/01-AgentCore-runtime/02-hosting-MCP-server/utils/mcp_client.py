"""
MCPクライアント関連の機能を提供するモジュール
"""

import asyncio
import contextlib
import logging
from collections.abc import Coroutine
from typing import Any, Callable, Optional, TypeVar

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import JSONRPCMessage

from .aws_auth import AWSAuthenticator, TokenRefreshable
from .uuid_fixer import UUIDFixer

# ロギングの設定
logger = logging.getLogger("agent_utils.mcp_client")

# 関数の戻り値の型ヒントのための型変数
T = TypeVar("T")


async def start_token_refresh_task(
    client: TokenRefreshable, interval_seconds: int = 1800
) -> asyncio.Task:
    """
    バックグラウンドでトークンを定期的に更新するタスクを開始

    Args:
        client: トークン更新機能を持つクライアント
        interval_seconds: 更新間隔(秒)

    Returns:
        asyncio.Task: 更新タスク
    """

    async def refresh_task():
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                logger.info(f"定期的なトークン更新を実行します(間隔: {interval_seconds}秒)")
                await client.refresh_token()
            except asyncio.CancelledError:
                logger.info("トークン更新タスクがキャンセルされました")
                break
            except Exception as e:
                logger.error(f"定期的なトークン更新中にエラーが発生しました: {e}")
                await asyncio.sleep(60)  # エラー後は1分待機してから再試行

    task = asyncio.create_task(refresh_task())
    return task


class BaseMCPClient:
    """MCPクライアントの基本クラス"""

    def __init__(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        use_uuid_fixer: bool = False,
        region: Optional[str] = None,
        secret_id: str = "mcp_server/cognito/credentials",
        use_token_cache: bool = True,
        token_cache_file: str = ".token_cache.json",
    ):
        """
        BaseMCPClientを初期化

        Args:
            url: MCPサーバーのURL
            headers: リクエストヘッダー
            use_uuid_fixer: UUIDフィクサーを使用するかどうか
            region: AWSリージョン
            secret_id: ベアラートークンを取得するシークレットID
            use_token_cache: トークンキャッシュを使用するかどうか
            token_cache_file: トークンキャッシュファイルのパス
        """
        self.url = url
        self.headers = headers or {}
        self.use_uuid_fixer = use_uuid_fixer
        self.session_id = None  # セッションIDを保持するための変数
        self.region = region
        self.secret_id = secret_id
        self.use_token_cache = use_token_cache
        self.token_cache_file = token_cache_file
        self.authenticator = AWSAuthenticator(
            region=region, use_cache=use_token_cache, cache_file=token_cache_file
        )
        self._token_refresh_task = None  # トークン更新タスク

    @classmethod
    async def create_remote_client(
        cls,
        region: Optional[str] = None,
        ssm_parameter: str = "/mcp_server/runtime/agent_arn",
        secret_id: str = "mcp_server/cognito/credentials",
        use_uuid_fixer: bool = True,
        use_token_cache: bool = True,
        token_cache_file: str = ".token_cache.json",
        token_refresh_interval: int = 1800,
    ) -> "BaseMCPClient":
        """
        リモートMCPクライアントを作成

        Args:
            region: AWSリージョン
            ssm_parameter: エージェントARNを取得するSSMパラメータ名
            secret_id: ベアラートークンを取得するシークレットID
            use_uuid_fixer: UUIDフィクサーを使用するかどうか
            use_token_cache: トークンキャッシュを使用するかどうか
            token_cache_file: トークンキャッシュファイルのパス
            token_refresh_interval: トークン自動更新の間隔(秒)

        Returns:
            BaseMCPClient: 初期化されたMCPクライアント
        """
        try:
            # AWS認証情報を取得
            authenticator = AWSAuthenticator(
                region=region, use_cache=use_token_cache, cache_file=token_cache_file
            )
            agent_arn = authenticator.get_agent_arn_from_ssm(parameter_name=ssm_parameter)
            bearer_token = authenticator.get_bearer_token_from_secrets(secret_id=secret_id)

            # URLとヘッダーを生成
            url = authenticator.get_remote_mcp_url(agent_arn)
            headers = authenticator.create_auth_headers(bearer_token)

            # クライアントを作成
            client = cls(
                url=url,
                headers=headers,
                use_uuid_fixer=use_uuid_fixer,
                region=region,
                secret_id=secret_id,
                use_token_cache=use_token_cache,
                token_cache_file=token_cache_file,
            )

            # トークン自動更新タスクを開始
            if token_refresh_interval > 0:
                client._token_refresh_task = await start_token_refresh_task(
                    client, token_refresh_interval
                )

            return client
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
        return self.authenticator.is_token_expired(token)

    async def execute_with_token_refresh(
        self, operation_func: Callable[..., Coroutine[Any, Any, T]], *args: Any, **kwargs: Any
    ) -> T:
        """
        トークン更新機能付きで操作を実行する

        Args:
            operation_func: 実行する関数
            *args, **kwargs: 関数に渡す引数

        Returns:
            関数の実行結果
        """
        max_retries = 2  # トークン更新後の再試行回数

        for attempt in range(max_retries + 1):
            try:
                # 操作を実行
                return await operation_func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()

                # 403エラーまたは認証エラーの場合
                if attempt < max_retries and (
                    "403" in error_str or "forbidden" in error_str or "unauthorized" in error_str
                ):
                    logger.warning(
                        f"認証エラーが発生しました(試行 {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    # トークンを更新して再試行
                    success = await self.refresh_token()
                    if not success:
                        logger.error("トークン更新に失敗したため、再試行を中止します")
                        raise
                    logger.info("トークンを更新しました。操作を再試行します...")
                else:
                    # その他のエラーはそのまま再スロー
                    raise

    async def connect(self) -> None:
        """MCPサーバーに接続してツール一覧を取得, ステートレスモード対応"""
        logger.info(f"MCPサーバーに接続します: {self.url}")

        # ヘッダーの準備
        self._prepare_headers()

        # 認証トークンの確認と更新
        await self._check_and_refresh_token()

        logger.debug(f"Headers: {self.headers}")

        # UUIDフィクサーを適用（セッション全体で一貫して使用）
        if self.use_uuid_fixer:
            UUIDFixer.apply_patch(JSONRPCMessage)
            logger.info("セッション全体でUUIDフィクサーを適用します")

        try:
            # トークン更新機能付きで実行
            await self.execute_with_token_refresh(self._connect_internal)
        finally:
            # UUIDフィクサーを削除
            if self.use_uuid_fixer:
                UUIDFixer.remove_patch(JSONRPCMessage)
                logger.info("UUIDフィクサーを削除しました")

    async def _connect_internal(self) -> None:
        """内部接続処理"""
        # ステップ1: セッションの初期化
        await self._initialize_session()

        # ステップ2: ツールリストの取得
        await self._get_tools_list()

    def _prepare_headers(self) -> None:
        """ヘッダーを準備"""
        # ヘッダーにContent-Typeが含まれていることを確認
        if "Content-Type" not in self.headers and "content-type" not in self.headers:
            self.headers["Content-Type"] = "application/json"
            self.headers["content-type"] = "application/json"  # 小文字のヘッダーも追加

    async def refresh_token(self) -> bool:
        """
        認証トークンを更新する

        Returns:
            bool: 更新に成功した場合はTrue、失敗した場合はFalse
        """
        try:
            logger.info("認証トークンを更新しています...")
            bearer_token = self.authenticator.get_bearer_token_from_secrets(
                secret_id=self.secret_id
            )
            self.headers["authorization"] = f"Bearer {bearer_token}"
            logger.info("認証トークンを更新しました")
            return True
        except Exception as e:
            logger.error(f"認証トークンの更新に失敗しました: {e}")
            return False

    async def _check_and_refresh_token(self) -> None:
        """認証トークンの有効期限を確認し、必要に応じて更新"""
        if "authorization" in self.headers:
            token = self.headers["authorization"].replace("Bearer ", "")
            if self._is_token_expired(token):
                logger.warning("認証トークンの有効期限が切れています。新しいトークンを取得します。")
                await self.refresh_token()

    async def _initialize_session(self) -> None:
        """セッションを初期化し、セッションIDを保存"""
        logger.info("🔄 セッションを初期化しています...")

        # リトライ回数と間隔を設定
        max_retries = 3
        retry_delay = 2.0

        for retry_count in range(max_retries + 1):
            try:
                logger.info(
                    f"Creating streamable HTTP client for initialization... (試行 {retry_count + 1}/{max_retries + 1})"
                )
                async with streamablehttp_client(
                    self.url,
                    self.headers,
                    timeout=400,
                    terminate_on_close=False,
                    sse_read_timeout=600,
                ) as (read_stream, write_stream, get_session_id):
                    logger.info("Streamable HTTP client created successfully")

                    async with ClientSession(read_stream, write_stream) as session:
                        logger.info("🔄 Initializing MCP session...")
                        await session.initialize()
                        logger.info("✓ MCP session initialized")

                        # セッションIDを取得して保存
                        self.session_id = get_session_id()
                        if self.session_id:
                            logger.info(f"Session ID: {self.session_id}")
                            # 次のリクエストのためにヘッダーにセッションIDを設定
                            self.headers["Mcp-Session-Id"] = self.session_id
                            self.headers["X-Session-Id"] = self.session_id

                # 初期化に成功したらループを抜ける
                break

            except Exception as e:
                if retry_count < max_retries:
                    logger.warning(
                        f"初期化に失敗しました (試行 {retry_count + 1}/{max_retries + 1}): {e}"
                    )
                    logger.info(f"{retry_delay}秒後に再試行します...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    logger.error(
                        f"❌ Error initializing MCP session after {max_retries + 1} attempts: {e}"
                    )
                    import traceback

                    logger.error(traceback.format_exc())
                    raise

        # 初期化後に少し待機 (サーバー側の処理完了を待機)
        await asyncio.sleep(1)

    async def _get_tools_list(self) -> None:
        """ツールリストを取得"""
        logger.info("🔄 ツールリストを取得しています...")

        # リトライ回数と間隔を設定
        max_retries = 3
        retry_delay = 2.0

        for retry_count in range(max_retries + 1):
            try:
                logger.info(
                    f"Creating streamable HTTP client for tool listing... (試行 {retry_count + 1}/{max_retries + 1})"
                )
                async with streamablehttp_client(
                    self.url,
                    self.headers,
                    timeout=400,
                    terminate_on_close=False,
                    sse_read_timeout=600,
                ) as (read_stream, write_stream, _):
                    logger.info("Streamable HTTP client created successfully")

                    async with ClientSession(read_stream, write_stream) as session:
                        # 初期化をスキップしてツールリストを直接取得
                        logger.info("🔄 Listing available tools...")
                        tool_result = await session.list_tools()

                        logger.info("📋 Available MCP Tools:")
                        logger.info("=" * 50)
                        for tool in tool_result.tools:
                            logger.info(f"🔧 {tool.name}")
                            logger.info(f"   Description: {tool.description}")
                            if hasattr(tool, "inputSchema") and tool.inputSchema:
                                properties = tool.inputSchema.get("properties", {})
                                if properties:
                                    logger.info(f"   Parameters: {list(properties.keys())}")

                        logger.info("✅ Successfully connected to MCP server!")
                        logger.info(f"Found {len(tool_result.tools)} tools available.")

                # ツールリスト取得に成功したらループを抜ける
                break

            except Exception as e:
                if retry_count < max_retries:
                    logger.warning(
                        f"ツールリスト取得に失敗しました (試行 {retry_count + 1}/{max_retries + 1}): {e}"
                    )
                    logger.info(f"{retry_delay}秒後に再試行します...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    logger.error(
                        f"❌ Error getting tool list after {max_retries + 1} attempts: {e}"
                    )
                    import traceback

                    logger.error(traceback.format_exc())
                    raise

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        ツールを実行する

        Args:
            tool_name: 実行するツールの名前
            arguments: ツールに渡す引数

        Returns:
            Dict[str, Any]: ツールの実行結果
        """
        logger.info(f"🔄 ツール '{tool_name}' を実行しています...")

        # UUIDフィクサーを適用
        if self.use_uuid_fixer:
            UUIDFixer.apply_patch(JSONRPCMessage)

        try:
            async with streamablehttp_client(
                self.url, self.headers, timeout=400, terminate_on_close=False, sse_read_timeout=600
            ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
                result = await session.execute_tool(tool_name, arguments)
                logger.info(f"✅ ツール '{tool_name}' の実行が完了しました")
                return result
        except Exception as e:
            logger.error(f"❌ ツール '{tool_name}' の実行中にエラーが発生しました: {e}")
            import traceback

            logger.error(traceback.format_exc())
            raise
        finally:
            # UUIDフィクサーを削除
            if self.use_uuid_fixer:
                UUIDFixer.remove_patch(JSONRPCMessage)

    async def access_resource(self, resource_uri: str) -> dict[str, Any]:
        """
        リソースにアクセスする

        Args:
            resource_uri: アクセスするリソースのURI

        Returns:
            Dict[str, Any]: リソースの内容
        """
        logger.info(f"🔄 リソース '{resource_uri}' にアクセスしています...")

        # UUIDフィクサーを適用
        if self.use_uuid_fixer:
            UUIDFixer.apply_patch(JSONRPCMessage)

        try:
            async with streamablehttp_client(
                self.url, self.headers, timeout=400, terminate_on_close=False, sse_read_timeout=600
            ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
                result = await session.access_resource(resource_uri)
                logger.info(f"✅ リソース '{resource_uri}' へのアクセスが完了しました")
                return result
        except Exception as e:
            logger.error(f"❌ リソース '{resource_uri}' へのアクセス中にエラーが発生しました: {e}")
            import traceback

            logger.error(traceback.format_exc())
            raise
        finally:
            # UUIDフィクサーを削除
            if self.use_uuid_fixer:
                UUIDFixer.remove_patch(JSONRPCMessage)

    async def close(self) -> None:
        """クライアントを閉じる"""
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._token_refresh_task
            logger.info("トークン更新タスクをキャンセルしました")
