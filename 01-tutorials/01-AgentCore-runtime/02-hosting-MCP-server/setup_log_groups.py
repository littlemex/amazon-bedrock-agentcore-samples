import boto3
import logging
import os
import yaml
from boto3.session import Session

def get_agent_id():
    """
    .bedrock_agentcore.yamlファイルからエージェントIDを取得します。
    """
    yaml_path = os.path.join(os.getcwd(), '.bedrock_agentcore.yaml')
    if not os.path.exists(yaml_path):
        print(f"警告: {yaml_path} が見つかりません。デフォルトのエージェントIDを使用します。")
        return None
    
    try:
        with open(yaml_path, 'r') as file:
            config = yaml.safe_load(file)
        
        default_agent = config.get('default_agent')
        if default_agent and default_agent in config.get('agents', {}):
            agent_config = config['agents'][default_agent]
            if 'bedrock_agentcore' in agent_config and 'agent_id' in agent_config['bedrock_agentcore']:
                return agent_config['bedrock_agentcore']['agent_id']
        
        print("警告: エージェントIDが見つかりません。デフォルトのエージェントIDを使用します。")
        return None
    except Exception as e:
        print(f"エラー: YAMLファイルの読み込み中にエラーが発生しました: {e}")
        return None

def setup_log_groups():
    """
    MCPサーバーが使用するCloudWatch Logsのロググループとログストリームを作成します。
    """
    print("CloudWatch Logsのロググループとログストリームを設定しています...")
    
    # リージョンを明示的に設定
    region = os.environ.get('AWS_REGION', 'us-east-1')
    print(f"使用するリージョン: {region}")
    
    # エージェントIDを取得
    agent_id = get_agent_id()
    if agent_id:
        print(f"エージェントID: {agent_id}")
    else:
        print("エージェントIDが取得できませんでした。基本パスのみ使用します。")
    
    # CloudWatchログクライアントを作成
    logs_client = boto3.client('logs', region_name=region)
    
    # 作成するロググループとログストリームのマッピング
    log_groups_and_streams = {
        "agents/mcp-server-logs": ["default"]
    }
    
    # エージェントIDが取得できた場合は、そのエージェントIDを含むロググループも作成
    if agent_id:
        agent_log_group = f"/aws/bedrock-agentcore/runtimes/{agent_id}-DEFAULT"
        log_groups_and_streams[agent_log_group] = ["default"]
    else:
        log_groups_and_streams["/aws/bedrock-agentcore/runtimes"] = ["default"]  # 基本パスのみ指定
    
    success = True
    
    for log_group, log_streams in log_groups_and_streams.items():
        try:
            # ロググループが存在するか確認
            response = logs_client.describe_log_groups(logGroupNamePrefix=log_group)
            if response.get('logGroups'):
                print(f"✓ ロググループ '{log_group}' またはそのプレフィックスを持つグループは既に存在します")
                
                # 既存のロググループの保持期間を設定
                for group in response.get('logGroups', []):
                    group_name = group.get('logGroupName')
                    try:
                        logs_client.put_retention_policy(
                            logGroupName=group_name,
                            retentionInDays=30
                        )
                        print(f"✓ ロググループ '{group_name}' の保持期間を30日に設定しました")
                        
                        # 各ログストリームを作成
                        for stream_name in log_streams:
                            try:
                                # ログストリームが存在するか確認
                                stream_response = logs_client.describe_log_streams(
                                    logGroupName=group_name,
                                    logStreamNamePrefix=stream_name
                                )
                                
                                if any(stream.get('logStreamName') == stream_name for stream in stream_response.get('logStreams', [])):
                                    print(f"✓ ログストリーム '{stream_name}' は既に存在します")
                                else:
                                    # ログストリームを作成
                                    logs_client.create_log_stream(
                                        logGroupName=group_name,
                                        logStreamName=stream_name
                                    )
                                    print(f"✓ ログストリーム '{stream_name}' を作成しました")
                            except Exception as e:
                                print(f"⚠ ログストリーム '{stream_name}' の作成中にエラーが発生しました: {e}")
                                success = False
                    except Exception as e:
                        print(f"⚠ ロググループ '{group_name}' の保持期間設定中にエラーが発生しました: {e}")
                        success = False
            else:
                # ロググループが存在しない場合は作成
                logs_client.create_log_group(logGroupName=log_group)
                print(f"✓ ロググループ '{log_group}' を作成しました")
                
                # ログの保持期間を30日に設定
                logs_client.put_retention_policy(
                    logGroupName=log_group,
                    retentionInDays=30
                )
                print(f"✓ ロググループ '{log_group}' の保持期間を30日に設定しました")
                
                # 各ログストリームを作成
                for stream_name in log_streams:
                    try:
                        logs_client.create_log_stream(
                            logGroupName=log_group,
                            logStreamName=stream_name
                        )
                        print(f"✓ ログストリーム '{stream_name}' を作成しました")
                    except Exception as e:
                        print(f"⚠ ログストリーム '{stream_name}' の作成中にエラーが発生しました: {e}")
                        success = False
            
        except Exception as e:
            print(f"⚠ ロググループ '{log_group}' の設定中にエラーが発生しました: {e}")
            success = False
    
    return success

if __name__ == "__main__":
    setup_log_groups()
