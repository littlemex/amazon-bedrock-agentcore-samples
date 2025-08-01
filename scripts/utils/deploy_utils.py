"""
deploy_utils - Amazon Bedrock AgentCoreのデプロイユーティリティ

このモジュールは、Amazon Bedrock AgentCoreのデプロイ、ステータス確認、削除などの
機能を提供するユーティリティ関数を提供します。
"""

import boto3
import time
import json
from typing import Dict, Any, List, Optional, Union


def deploy_agent(entrypoint: str, execution_role: str, requirements_file: Optional[str] = None, 
                 region: Optional[str] = None, agent_name: Optional[str] = None) -> Any:
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
    try:
        from bedrock_agentcore_starter_toolkit import Runtime
        
        # 環境変数の設定（ARM64サポート）
        import os
        os.environ['DOCKER_DEFAULT_PLATFORM'] = 'linux/arm64'
        
        agentcore_runtime = Runtime()
        
        # 設定
        response = agentcore_runtime.configure(
            entrypoint=entrypoint,
            execution_role=execution_role,
            auto_create_ecr=True,
            requirements_file=requirements_file,
            region=region,
            agent_name=agent_name
        )
        
        # 起動
        launch_result = agentcore_runtime.launch()
        
        return launch_result
    except Exception as e:
        raise RuntimeError(f"Error deploying agent: {e}")


def check_status(agent_id: str, region: Optional[str] = None) -> Dict[str, Any]:
    """
    エージェントのステータスを確認
    
    Parameters:
    - agent_id: エージェントID
    - region: AWSリージョン（オプション）
    
    Returns:
    - response: ステータス情報
    """
    try:
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        response = client.get_agent_runtime(agentRuntimeId=agent_id)
        return response
    except Exception as e:
        raise RuntimeError(f"Error checking agent status: {e}")


def wait_for_status(agent_id: str, target_status: List[str] = ['READY'], 
                   region: Optional[str] = None, timeout: int = 600, interval: int = 10) -> Dict[str, Any]:
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
    try:
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = client.get_agent_runtime(agentRuntimeId=agent_id)
            status = response.get('status')
            print(f"Current status: {status}")
            
            if status in target_status:
                return response
            
            time.sleep(interval)
        
        raise TimeoutError(f"Timeout waiting for status {target_status}")
    except Exception as e:
        if isinstance(e, TimeoutError):
            raise e
        raise RuntimeError(f"Error waiting for agent status: {e}")


def delete_agent(agent_id: str, ecr_uri: Optional[str] = None, 
                role_name: Optional[str] = None, region: Optional[str] = None) -> Dict[str, Any]:
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
    try:
        # AgentCore Runtimeの削除
        agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=region)
        runtime_delete_response = agentcore_control_client.delete_agent_runtime(
            agentRuntimeId=agent_id
        )
        
        result = {"agent_runtime_delete": runtime_delete_response}
        
        # ECRリポジトリの削除（オプション）
        if ecr_uri:
            try:
                ecr_client = boto3.client('ecr', region_name=region)
                repository_name = ecr_uri.split('/')[-1]
                ecr_response = ecr_client.delete_repository(
                    repositoryName=repository_name,
                    force=True
                )
                result["ecr_delete"] = ecr_response
            except Exception as e:
                result["ecr_delete_error"] = str(e)
        
        # IAMロールの削除（オプション）
        if role_name:
            try:
                iam_client = boto3.client('iam')
                
                # ロールポリシーの削除
                policies = iam_client.list_role_policies(
                    RoleName=role_name,
                    MaxItems=100
                )
                
                for policy_name in policies.get('PolicyNames', []):
                    iam_client.delete_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name
                    )
                
                # ロールの削除
                iam_response = iam_client.delete_role(
                    RoleName=role_name
                )
                result["iam_delete"] = iam_response
            except Exception as e:
                result["iam_delete_error"] = str(e)
        
        return result
    except Exception as e:
        raise RuntimeError(f"Error deleting agent: {e}")


def list_agents(region: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    デプロイされたエージェントの一覧を取得
    
    Parameters:
    - region: AWSリージョン（オプション）
    
    Returns:
    - agents: エージェントのリスト
    """
    try:
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        response = client.list_agent_runtimes()
        return response.get('agentRuntimes', [])
    except Exception as e:
        raise RuntimeError(f"Error listing agents: {e}")
