"""
AgentCoreClient - Amazon Bedrock AgentCoreのクライアントクラス

このモジュールは、ローカルとデプロイされたエージェントを同じインターフェースで呼び出すための
クライアントクラスを提供します。
"""

import json
import importlib.util
import sys
import os
from typing import Dict, Any, Optional, Union


class AgentCoreClient:
    """
    Amazon Bedrock AgentCoreのクライアントクラス
    
    ローカルとデプロイされたエージェントを同じインターフェースで呼び出すためのクライアントクラスです。
    """
    
    def __init__(self, agent_arn: Optional[str] = None, local_entrypoint: Optional[str] = None, 
                 region: Optional[str] = None):
        """
        AgentCoreClientの初期化
        
        Parameters:
        - agent_arn: デプロイされたエージェントのARN（デプロイモード用）
        - local_entrypoint: ローカルエージェントのエントリポイント（ローカルモード用）
        - region: AWSリージョン
        """
        self.agent_arn = agent_arn
        self.local_entrypoint = local_entrypoint
        self.region = region
        self.is_local = local_entrypoint is not None
        self.local_agent = None
        self.client = None
        
        if not self.is_local and not self.agent_arn:
            raise ValueError("Either agent_arn or local_entrypoint must be provided")
        
        if self.is_local:
            # ローカルモードの設定
            self._setup_local()
        else:
            # デプロイモードの設定
            self._setup_deployed()
    
    def _setup_local(self):
        """ローカルモードの設定"""
        try:
            # ローカルエージェントのロード
            module_name = os.path.basename(self.local_entrypoint).replace('.py', '')
            spec = importlib.util.spec_from_file_location(module_name, self.local_entrypoint)
            if spec is None:
                raise ImportError(f"Could not load module from {self.local_entrypoint}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # エントリポイント関数を探す
            if hasattr(module, 'strands_agent_bedrock'):
                self.local_agent = module.strands_agent_bedrock
            elif hasattr(module, 'app') and hasattr(module.app, 'entrypoint'):
                # BedrockAgentCoreAppのエントリポイントを探す
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if callable(attr) and hasattr(attr, '__wrapped__'):
                        self.local_agent = attr
                        break
            
            if self.local_agent is None:
                raise AttributeError(f"Could not find entrypoint function in {self.local_entrypoint}")
            
        except Exception as e:
            raise RuntimeError(f"Error setting up local agent: {e}")
        
    def _setup_deployed(self):
        """デプロイモードの設定"""
        try:
            # boto3クライアントの初期化
            import boto3
            self.client = boto3.client('bedrock-agentcore', region_name=self.region)
        except Exception as e:
            raise RuntimeError(f"Error setting up deployed agent: {e}")
        
    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        エージェントを呼び出す（統一インターフェース）
        
        Parameters:
        - payload: エージェントに送信するペイロード
        
        Returns:
        - response: エージェントからのレスポンス（統一フォーマット）
        """
        if self.is_local:
            return self._invoke_local(payload)
        else:
            return self._invoke_deployed(payload)
    
    def _invoke_local(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """ローカルエージェントを呼び出す"""
        try:
            # ローカルエージェントの呼び出し
            result = self.local_agent(payload)
            
            # 結果を統一フォーマットに変換
            if isinstance(result, dict):
                return {"content": result}
            else:
                return {"content": result}
        except Exception as e:
            return {"error": f"Error invoking local agent: {e}"}
        
    def _invoke_deployed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """デプロイされたエージェントを呼び出す"""
        try:
            import json
            
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.agent_arn,
                qualifier="DEFAULT",
                payload=json.dumps(payload)
            )
            
            # レスポンスを統一フォーマットに変換
            if "text/event-stream" in response.get("contentType", ""):
                # ストリーミングレスポンスの処理
                content = []
                for line in response["response"].iter_lines(chunk_size=1):
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            line = line[6:]
                            content.append(line)
                return {"content": "\n".join(content)}
            else:
                # 通常のレスポンスの処理
                events = []
                for event in response.get("response", []):
                    events.append(event)
                
                # バイト列をデコード
                decoded_text = events[0].decode('utf-8')
                
                # JSONとして解析を試みる
                try:
                    response_json = json.loads(decoded_text)
                    return {"content": response_json}
                except json.JSONDecodeError:
                    # JSONでない場合は、そのまま返す
                    return {"content": decoded_text.strip('"')}
                
        except Exception as e:
            return {"error": f"Error invoking deployed agent: {e}"}
    
    def get_status(self) -> Dict[str, Any]:
        """エージェントのステータスを取得"""
        if self.is_local:
            return {"status": "LOCAL_MODE"}
        else:
            try:
                import boto3
                client = boto3.client('bedrock-agentcore-control', region_name=self.region)
                agent_id = self.agent_arn.split('/')[-1]
                response = client.get_agent_runtime(agentRuntimeId=agent_id)
                return response
            except Exception as e:
                return {"error": f"Error getting agent status: {e}"}
