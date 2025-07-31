"""
AWS認証関連の処理を行うユーティリティモジュール
"""

import json
import logging
import time
from typing import Optional, Protocol

from boto3.session import Session

from .token_cache import TokenCache

# ロギングの設定
logger = logging.getLogger("agent_utils.aws_auth")


class TokenRefreshable(Protocol):
    """トークン更新機能を持つクライアントのプロトコル"""

    async def refresh_token(self) -> bool:
        """
        トークンを更新する

        Returns:
            bool: 更新に成功した場合はTrue、失敗した場合はFalse
        """
        ...


class AWSAuthenticator:
    """AWS認証関連の処理を行うクラス"""

    def __init__(
        self,
        region: Optional[str] = None,
        use_cache: bool = True,
        cache_file: str = ".token_cache.json",
    ):
        """
        AWSAuthenticatorを初期化

        Args:
            region: AWSリージョン。Noneの場合はデフォルトリージョンを使用
            use_cache: トークンキャッシュを使用するかどうか
            cache_file: キャッシュファイルのパス
        """
        self.boto_session = Session(region_name=region)
        self.region = self.boto_session.region_name
        self.use_cache = use_cache
        self.token_cache = TokenCache(cache_file) if use_cache else None
        logger.info(f"AWSリージョン: {self.region}")

    def get_agent_arn_from_ssm(self, parameter_name: str = "/mcp_server/runtime/agent_arn") -> str:
        """
        SSMパラメータストアからエージェントARNを取得

        Args:
            parameter_name: SSMパラメータ名

        Returns:
            エージェントARN
        """
        try:
            ssm_client = self.boto_session.client("ssm")
            response = ssm_client.get_parameter(Name=parameter_name)
            agent_arn = response["Parameter"]["Value"]
            logger.info(f"エージェントARNを取得しました: {agent_arn}")
            return agent_arn
        except Exception as e:
            logger.error(f"エージェントARNの取得に失敗しました: {e}")
            raise

    def get_bearer_token_from_secrets(
        self, secret_id: str = "mcp_server/cognito/credentials"
    ) -> str:
        """
        Secrets Managerからベアラートークンを取得

        Args:
            secret_id: シークレットID

        Returns:
            ベアラートークン
        """
        # キャッシュからトークンを取得
        if self.use_cache and self.token_cache:
            cached_token = self.token_cache.get_token()
            if cached_token:
                return cached_token

        try:
            secrets_client = self.boto_session.client("secretsmanager")
            response = secrets_client.get_secret_value(SecretId=secret_id)
            secret_value = response["SecretString"]
            parsed_secret = json.loads(secret_value)
            bearer_token = parsed_secret["bearer_token"]
            logger.info("Secrets Managerからベアラートークンを取得しました")

            # トークンをキャッシュに保存
            if self.use_cache and self.token_cache:
                self.token_cache.save_token(bearer_token)

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
        encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
        mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
        logger.info(f"MCPサーバーURL: {mcp_url}")
        return mcp_url

    def create_auth_headers(self, bearer_token: str) -> dict[str, str]:
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
            "x-amz-content-sha256": "UNSIGNED-PAYLOAD",  # 署名のためのSHA256ヘッダー
        }
        return headers

    def is_token_expired(self, token: str) -> bool:
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

            # JWTの2番目の部分(ペイロード)を取得
            payload = token.split(".")[1]
            # Base64デコード(パディングを調整)
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            claims = json.loads(decoded)

            # 有効期限を確認
            if "exp" in claims:
                exp_time = claims["exp"]
                current_time = time.time()
                if current_time > exp_time:
                    logger.warning(
                        f"トークンの有効期限が切れています。有効期限: {exp_time}, 現在時刻: {current_time}"
                    )
                    return True

            return False
        except Exception as e:
            logger.error(f"トークンの有効期限確認中にエラーが発生しました: {e}")
            # エラーが発生した場合は、安全のためトークンを更新する
            return True
