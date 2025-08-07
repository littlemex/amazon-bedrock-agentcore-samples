"""
認証トークンをキャッシュするためのユーティリティモジュール
"""

import json
import logging
import os
import time

# ロギングの設定
logger = logging.getLogger("agent_utils.token_cache")


class TokenCache:
    """認証トークンをキャッシュするクラス"""

    def __init__(self, cache_file: str = ".token_cache.json"):
        """
        TokenCacheを初期化

        Args:
            cache_file: キャッシュファイルのパス
        """
        self.cache_file = cache_file

    def save_token(self, token: str, expires_in: int = 3600) -> None:
        """
        トークンをキャッシュに保存

        Args:
            token: 保存するトークン
            expires_in: トークンの有効期限(秒)
        """
        try:
            import base64

            # JWTからexpを取得
            try:
                payload = token.split(".")[1]
                payload += "=" * (4 - len(payload) % 4)
                decoded = base64.b64decode(payload)
                claims = json.loads(decoded)
                expires_at = claims["exp"] if "exp" in claims else time.time() + expires_in - 300
            except Exception:
                expires_at = time.time() + expires_in - 300  # 5分前に期限切れとみなす

            cache_data = {"token": token, "expires_at": expires_at}
            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f)
            logger.info(
                f"トークンをキャッシュに保存しました(有効期限: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires_at))})"
            )
        except Exception as e:
            logger.warning(f"トークンのキャッシュ保存に失敗しました: {e}")

    def get_token(self) -> str | None:
        """
        キャッシュからトークンを取得

        Returns:
            有効なトークン、または有効期限切れ/キャッシュなしの場合はNone
        """
        try:
            if not os.path.exists(self.cache_file):
                logger.debug("トークンキャッシュファイルが存在しません")
                return None

            with open(self.cache_file) as f:
                cache_data = json.loads(f.read())

            current_time = time.time()
            expires_at = cache_data["expires_at"]

            if current_time < expires_at:
                remaining = int(expires_at - current_time)
                logger.info(f"キャッシュからトークンを取得しました(残り有効期間: {remaining}秒)")
                return cache_data["token"]
            else:
                logger.info("キャッシュのトークンは有効期限切れです")
                return None
        except Exception as e:
            logger.warning(f"キャッシュからのトークン取得に失敗しました: {e}")
            return None
