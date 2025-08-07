import asyncio
import logging
import argparse
import sys
from typing import Dict, Any

from agent_utils import BaseMCPClient

# ロギングの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_client_remote3")


class MCPClient(BaseMCPClient):
    """
    BaseMCPClientを継承したMCPクライアント
    
    このクラスは、特定のプロジェクト向けの拡張機能や
    カスタマイズを追加するために使用できます。
    """
    
    # 必要に応じて、特定のプロジェクト向けのメソッドをここに追加
    
    async def execute_custom_tool(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        """
        カスタムツールを実行する例
        
        Args:
            tool_name: 実行するツールの名前
            **kwargs: ツールに渡す引数
            
        Returns:
            Dict[str, Any]: ツールの実行結果
        """
        logger.info(f"カスタムツール '{tool_name}' を実行します...")
        
        # 引数を辞書に変換
        arguments = dict(kwargs)
        
        # 基底クラスのexecute_toolメソッドを使用
        result = await self.execute_tool(tool_name, arguments)
        
        # 結果を加工する例
        if isinstance(result, dict) and "data" in result:
            logger.info(f"カスタムツール '{tool_name}' の実行結果を加工します")
            # 結果の加工処理をここに追加
        
        return result


async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='MCPクライアント')
    parser.add_argument('--mode', choices=['local', 'remote'], default='local', help='接続モード（local/remote）')
    parser.add_argument('--url', default="http://localhost:18000/mcp", help='ローカルMCPサーバーのURL')
    parser.add_argument('--region', help='AWSリージョン（リモートモード用）')
    parser.add_argument('--ssm-parameter', default='/mcp_server/runtime/agent_arn', help='エージェントARNを取得するSSMパラメータ名')
    parser.add_argument('--secret-id', default='mcp_server/cognito/credentials', help='ベアラートークンを取得するシークレットID')
    parser.add_argument('--use-uuid-fixer', action='store_true', help='UUIDフィクサーを使用する')
    parser.add_argument('--use-token-cache', action='store_true', default=True, help='トークンキャッシュを使用する')
    parser.add_argument('--token-cache-file', default=".token_cache.json", help='トークンキャッシュファイルのパス')
    parser.add_argument('--token-refresh-interval', type=int, default=1800, help='トークン自動更新の間隔（秒）。0で無効化')
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
        
        # クライアントを閉じる
        await client.close()
            
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
