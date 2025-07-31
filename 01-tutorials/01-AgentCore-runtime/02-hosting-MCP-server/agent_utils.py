"""
Amazon Bedrock AgentCore 用のユーティリティモジュール

このモジュールは後方互換性のために維持されています。
新しいコードでは utils パッケージを直接インポートしてください。
"""

import logging


from utils import (
    AWSAuthenticator,
    BaseMCPClient,
    TokenCache,
    TokenRefreshable,
    UUIDFixer,
    start_token_refresh_task,
)

# ロギングの設定
logger = logging.getLogger("agent_utils")

# すべてのクラスと関数をエクスポート
__all__ = [
    "AWSAuthenticator",
    "BaseMCPClient",
    "TokenCache",
    "TokenRefreshable",
    "UUIDFixer",
    "start_token_refresh_task",
]
