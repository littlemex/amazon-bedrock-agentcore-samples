#!/usr/bin/env python3
"""
cli - Amazon Bedrock AgentCoreのコマンドラインインターフェース

このモジュールは、Amazon Bedrock AgentCoreのユーティリティをコマンドラインから
使用するためのインターフェースを提供します。
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional

from .agentcore_client import AgentCoreClient
from .deploy_utils import deploy_agent, check_status, wait_for_status, delete_agent, list_agents


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Amazon Bedrock AgentCore CLI')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # invokeコマンド
    invoke_parser = subparsers.add_parser('invoke', help='Invoke an agent')
    invoke_parser.add_argument('--agent-arn', help='ARN of the deployed agent')
    invoke_parser.add_argument('--local-entrypoint', help='Path to local entrypoint')
    invoke_parser.add_argument('--region', help='AWS region')
    invoke_parser.add_argument('--payload', required=True, help='JSON payload')
    
    # deployコマンド
    deploy_parser = subparsers.add_parser('deploy', help='Deploy an agent')
    deploy_parser.add_argument('--entrypoint', required=True, help='Path to entrypoint')
    deploy_parser.add_argument('--execution-role', required=True, help='Execution role ARN')
    deploy_parser.add_argument('--requirements-file', help='Path to requirements file')
    deploy_parser.add_argument('--region', help='AWS region')
    deploy_parser.add_argument('--agent-name', help='Agent name')
    
    # statusコマンド
    status_parser = subparsers.add_parser('status', help='Check agent status')
    status_parser.add_argument('--agent-id', required=True, help='Agent ID')
    status_parser.add_argument('--region', help='AWS region')
    
    # waitコマンド
    wait_parser = subparsers.add_parser('wait', help='Wait for agent status')
    wait_parser.add_argument('--agent-id', required=True, help='Agent ID')
    wait_parser.add_argument('--status', default='READY', help='Target status (default: READY)')
    wait_parser.add_argument('--timeout', type=int, default=600, help='Timeout in seconds (default: 600)')
    wait_parser.add_argument('--interval', type=int, default=10, help='Check interval in seconds (default: 10)')
    wait_parser.add_argument('--region', help='AWS region')
    
    # deleteコマンド
    delete_parser = subparsers.add_parser('delete', help='Delete an agent')
    delete_parser.add_argument('--agent-id', required=True, help='Agent ID')
    delete_parser.add_argument('--ecr-uri', help='ECR URI')
    delete_parser.add_argument('--role-name', help='IAM role name')
    delete_parser.add_argument('--region', help='AWS region')
    
    # listコマンド
    list_parser = subparsers.add_parser('list', help='List deployed agents')
    list_parser.add_argument('--region', help='AWS region')
    
    args = parser.parse_args()
    
    try:
        if args.command == 'invoke':
            _handle_invoke(args)
        elif args.command == 'deploy':
            _handle_deploy(args)
        elif args.command == 'status':
            _handle_status(args)
        elif args.command == 'wait':
            _handle_wait(args)
        elif args.command == 'delete':
            _handle_delete(args)
        elif args.command == 'list':
            _handle_list(args)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _handle_invoke(args):
    """invokeコマンドの処理"""
    if not args.agent_arn and not args.local_entrypoint:
        print("Error: Either --agent-arn or --local-entrypoint must be provided", file=sys.stderr)
        sys.exit(1)
    
    client = AgentCoreClient(
        agent_arn=args.agent_arn,
        local_entrypoint=args.local_entrypoint,
        region=args.region
    )
    
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError:
        print("Error: Invalid JSON payload", file=sys.stderr)
        sys.exit(1)
    
    response = client.invoke(payload)
    print(json.dumps(response, indent=2, ensure_ascii=False))


def _handle_deploy(args):
    """deployコマンドの処理"""
    result = deploy_agent(
        entrypoint=args.entrypoint,
        execution_role=args.execution_role,
        requirements_file=args.requirements_file,
        region=args.region,
        agent_name=args.agent_name
    )
    
    # 結果をJSON形式で出力
    result_dict = {
        "agent_id": result.agent_id,
        "agent_arn": result.agent_arn,
        "ecr_uri": result.ecr_uri,
        "mode": result.mode
    }
    print(json.dumps(result_dict, indent=2))


def _handle_status(args):
    """statusコマンドの処理"""
    response = check_status(
        agent_id=args.agent_id,
        region=args.region
    )
    print(json.dumps(response, indent=2))


def _handle_wait(args):
    """waitコマンドの処理"""
    target_status = args.status.split(',')
    response = wait_for_status(
        agent_id=args.agent_id,
        target_status=target_status,
        region=args.region,
        timeout=args.timeout,
        interval=args.interval
    )
    print(json.dumps(response, indent=2))


def _handle_delete(args):
    """deleteコマンドの処理"""
    response = delete_agent(
        agent_id=args.agent_id,
        ecr_uri=args.ecr_uri,
        role_name=args.role_name,
        region=args.region
    )
    print(json.dumps(response, indent=2))


def _handle_list(args):
    """listコマンドの処理"""
    agents = list_agents(region=args.region)
    print(json.dumps(agents, indent=2))


if __name__ == '__main__':
    main()
