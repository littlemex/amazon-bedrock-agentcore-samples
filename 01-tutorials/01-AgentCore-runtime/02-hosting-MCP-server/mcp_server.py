import logging
import asyncio
from fastmcp import FastMCP
import anyio
from fastmcp.server.middleware import Middleware, MiddlewareContext

# ロギングの設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# デバッグ情報を出力するミドルウェア
class DebugMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        import inspect
        logger.debug(f"Context type: {type(context)}")
        logger.debug(f"Context attributes: {dir(context)}")
        logger.debug(f"Context structure: {inspect.getmembers(context)[:10]}")  # 最初の10項目だけ表示
        return await call_next(context)

# Content-Typeヘッダーを追加するカスタムミドルウェア
class ContentTypeMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        # デバッグ情報を出力
        logger.debug(f"ContentTypeMiddleware: Context type: {type(context)}")
        logger.debug(f"ContentTypeMiddleware: Context attributes: {dir(context)}")
        
        # fastmcp_contextが存在する場合、そこからヘッダー情報にアクセス
        if context.fastmcp_context:
            # ヘッダー情報へのアクセス方法はFastMCPのバージョンによって異なる可能性がある
            if hasattr(context.fastmcp_context, 'headers'):
                headers = context.fastmcp_context.headers
                if "content-type" not in headers:
                    logger.info("Content-Typeヘッダーを追加します")
                    headers["content-type"] = "application/json"
            # 別の可能性のあるヘッダーアクセス方法
            elif hasattr(context.fastmcp_context, 'request') and hasattr(context.fastmcp_context.request, 'headers'):
                headers = context.fastmcp_context.request.headers
                if "content-type" not in headers:
                    logger.info("Content-Typeヘッダーを追加します")
                    headers["content-type"] = "application/json"
        
        return await call_next(context)

# カスタムCORSミドルウェア
class CustomCORSMiddleware(Middleware):
    def __init__(self, allow_origins=None, allow_methods=None, allow_headers=None, allow_credentials=False):
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "OPTIONS"]
        self.allow_headers = allow_headers or ["Content-Type", "Authorization"]
        self.allow_credentials = allow_credentials
        
    async def on_message(self, context: MiddlewareContext, call_next):
        logger.debug(f"CustomCORSMiddleware: Processing {context.method}")
        
        # fastmcp_contextが存在する場合、CORSヘッダーを設定
        if context.fastmcp_context:
            if hasattr(context.fastmcp_context, 'headers'):
                # レスポンスヘッダーを設定（実際のヘッダー設定方法はFastMCPのバージョンによって異なる可能性がある）
                if hasattr(context.fastmcp_context, 'response_headers'):
                    headers = context.fastmcp_context.response_headers
                    headers["Access-Control-Allow-Origin"] = ", ".join(self.allow_origins)
                    headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
                    headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
                    if self.allow_credentials:
                        headers["Access-Control-Allow-Credentials"] = "true"
        
        # 処理を続行
        result = await call_next(context)
        return result

# MCPサーバーの設定を変更
mcp = FastMCP(
    name="MCPServer"
)

# デバッグミドルウェアを追加
mcp.add_middleware(DebugMiddleware())

# Content-Typeミドルウェアを追加
mcp.add_middleware(ContentTypeMiddleware())

# カスタムCORSミドルウェアを追加
mcp.add_middleware(CustomCORSMiddleware(
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "content-type", "Authorization", "x-session-id", "Accept", "Mcp-Session-Id"],
    allow_credentials=True
))

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

class ErrorHandlingMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        try:
            return await call_next(context)
        except anyio.ClosedResourceError as e:
            logger.warning(f"クライアント接続が閉じられました: {e}")
            return {"status": "error", "message": "クライアント接続が閉じられました"}
        except anyio.BrokenResourceError as e:
            logger.warning(f"クライアント接続が破損しました: {e}")
            return {"status": "error", "message": "クライアント接続が破損しました"}
        except Exception as e:
            logger.error(f"予期しないエラーが発生しました: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"status": "error", "message": f"エラー: {str(e)}"}

# ミドルウェアを追加
mcp.add_middleware(ErrorHandlingMiddleware())

if __name__ == "__main__":
    logger.info("MCPサーバーを起動しています...")
    try:
        # FastMCPの設定を修正
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            stateless_http=True,  # ステートレスモードのまま
            uvicorn_config={
                "timeout_keep_alive": 600  # Keep-Alive接続のタイムアウト
            }
        )
    except asyncio.CancelledError:
        logger.info("サーバーが正常にシャットダウンされました")
    except anyio.ClosedResourceError as e:
        logger.warning(f"クライアント接続が閉じられました: {e}")
    except Exception as e:
        logger.error(f"サーバー実行中にエラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
