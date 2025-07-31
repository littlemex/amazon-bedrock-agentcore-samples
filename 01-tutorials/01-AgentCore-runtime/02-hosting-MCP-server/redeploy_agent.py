import boto3
import json
import time
import os
import sys
import shutil
import datetime
from boto3.session import Session

# Import required modules
sys.path.insert(0, os.path.abspath('..'))
from utils import create_agentcore_role, setup_cognito_user_pool, reset_agentcore_yaml
from bedrock_agentcore_starter_toolkit import Runtime
from setup_log_groups import setup_log_groups
from setup_trace_destination import setup_trace_destination

# AWS プロファイルの設定（必要に応じて変更してください）
os.environ['AWS_PROFILE'] = 'cline2'

def main():
    # Initialize session
    boto_session = Session()
    region = boto_session.region_name
    print(f"Using AWS region: {region}")
    
    # Step 0: Delete .bedrock_agentcore.yaml file
    print("\nStep 0: Deleting .bedrock_agentcore.yaml file...")
    yaml_path = os.path.join(os.getcwd(), '.bedrock_agentcore.yaml')
    if os.path.exists(yaml_path):
        # バックアップを作成
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = f"{yaml_path}.bak-{timestamp}"
        try:
            shutil.copy2(yaml_path, backup_path)
            print(f"バックアップを作成しました: {backup_path}")
            
            # ファイルを削除
            os.remove(yaml_path)
            print(f"✓ {yaml_path} を削除しました")
        except Exception as e:
            print(f"⚠ ファイル操作中にエラーが発生しました: {e}")
            print("  手動でファイルを削除してください")
    else:
        print(f"✓ {yaml_path} は存在しません。新規作成します。")
    
    # Step 1: Delete existing agent
    try:
        print("Step 1: Deleting existing agent...")
        ssm_client = boto3.client('ssm', region_name=region)
        agent_arn_response = ssm_client.get_parameter(Name='/mcp_server/runtime/agent_arn')
        agent_arn = agent_arn_response['Parameter']['Value']
        agent_id = agent_arn.split('/')[-1]
        print(f"Retrieved Agent ARN: {agent_arn}")
        print(f"Agent ID: {agent_id}")
        
        agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=region)
        runtime_delete_response = agentcore_control_client.delete_agent_runtime(
            agentRuntimeId=agent_id,
        )
        print("✓ AgentCore Runtime deletion initiated")
        
        # Wait for deletion to complete
        print("Waiting for deletion to complete...")
        time.sleep(30)  # Initial wait
        
        # Check status periodically
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                # Try to get the agent status - if it fails with ResourceNotFoundException, the agent is deleted
                status_response = agentcore_control_client.get_agent_runtime(
                    agentRuntimeId=agent_id
                )
                print(f"Status: {status_response['status']} - waiting...")
                time.sleep(30)
            except agentcore_control_client.exceptions.ResourceNotFoundException:
                print("✓ Agent deleted successfully")
                break
            except Exception as e:
                print(f"Error checking status: {e}")
                time.sleep(30)
                
            if attempt == max_attempts - 1:
                print("Warning: Deletion may not be complete, but proceeding anyway")
    except Exception as e:
        print(f"Error during deletion: {e}")
        print("Proceeding with deployment anyway...")
    
    # Step 2: Set up Cognito
    print("\nStep 2: Setting up Amazon Cognito user pool...")
    cognito_config = setup_cognito_user_pool()
    print("Cognito setup completed ✓")
    print(f"User Pool ID: {cognito_config.get('pool_id', 'N/A')}")
    print(f"Client ID: {cognito_config.get('client_id', 'N/A')}")
    
    # Step 3: Create IAM role
    print("\nStep 3: Creating IAM role...")
    tool_name = "mcp_server"
    agentcore_iam_role = create_agentcore_role(agent_name=tool_name)
    print(f"IAM role created ✓")
    print(f"Role ARN: {agentcore_iam_role['Role']['Arn']}")
    
    # Step 4: Configure AgentCore Runtime
    print("\nStep 4: Configuring AgentCore Runtime...")
    required_files = ['mcp_server.py', 'requirements.txt']
    for file in required_files:
        if not os.path.exists(file):
            raise FileNotFoundError(f"Required file {file} not found")
    print("All required files found ✓")
    
    agentcore_runtime = Runtime()
    
    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [
                cognito_config['client_id']
            ],
            "discoveryUrl": cognito_config['discovery_url'],
        }
    }
    
    response = agentcore_runtime.configure(
        entrypoint="mcp_server.py",
        execution_role=agentcore_iam_role['Role']['Arn'],
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        region=region,
        authorizer_configuration=auth_config,
        protocol="MCP",
        agent_name=tool_name
    )
    print("Configuration completed ✓")
    
    # Step 4.5: Replace the auto-generated Dockerfile with our custom one
    print("\nStep 4.5: Replacing Dockerfile with custom version...")
    try:
        # Check if Dockerfile.custom exists
        if not os.path.exists("Dockerfile.custom"):
            print("⚠ Dockerfile.custom not found. Creating it...")
            with open("Dockerfile.custom", "w") as f:
                f.write("""FROM public.ecr.aws/docker/library/python:3.10-slim
WORKDIR /app

COPY requirements.txt requirements.txt
# Install from requirements file
RUN pip install -r requirements.txt

# Set AWS region environment variable
ENV AWS_REGION=us-east-1
ENV AWS_DEFAULT_REGION=us-east-1

# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080
EXPOSE 8000

# Copy entire project (respecting .dockerignore)
COPY . .

# Use direct file path instead of module path
CMD ["opentelemetry-instrument", "python", "mcp_server.py"]
""")
                print("✓ Dockerfile.custom created")
        
        # Backup the original Dockerfile if it exists
        if os.path.exists("Dockerfile"):
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            backup_path = f"Dockerfile.bak-{timestamp}"
            shutil.copy2("Dockerfile", backup_path)
            print(f"✓ Original Dockerfile backed up to {backup_path}")
        
        # Copy our custom Dockerfile to the standard location
        shutil.copy2("Dockerfile.custom", "Dockerfile")
        print("✓ Custom Dockerfile copied to standard location")
    except Exception as e:
        print(f"⚠ Error replacing Dockerfile: {e}")
        print("  Proceeding with the original Dockerfile")
    
    # Step 5: Launch MCP server
    print("\nStep 5: Launching MCP server to AgentCore Runtime...")
    print("This may take several minutes...")
    # Step 5.5: Setup CloudWatch Logs groups before launching
    print("\nStep 5.5: Setting up CloudWatch Logs groups...")
    logs_result = setup_log_groups()
    if logs_result:
        print("✓ CloudWatch Logs groups setup completed")
    else:
        print("⚠ CloudWatch Logs groups setup failed, but continuing...")
    
    # OpenTelemetry 環境変数の設定
    env_vars = {
        "OTEL_PYTHON_DISTRO": "aws_distro",
        "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
        "OTEL_RESOURCE_ATTRIBUTES": f"service.name=mcp_server,aws.region={region}",
        "OTEL_TRACES_EXPORTER": "otlp",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_LOGS_EXPORTER": "otlp",
        "OTEL_EXPORTER_OTLP_LOGS_HEADERS": f"x-aws-log-group=agents/mcp-server-logs,x-aws-log-stream=default,x-aws-metric-namespace=agents",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS": f"x-aws-log-group=aws/otel/traces",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
        "AWS_REGION": region,
        "AWS_DEFAULT_REGION": region,
        "AGENT_OBSERVABILITY_ENABLED": "true",
        # 追加の環境変数
        "MCP_CONNECTION_TIMEOUT": "120",  # 接続タイムアウトを増やす
        "MCP_KEEP_ALIVE": "true",         # 接続を維持する
        "MCP_STATELESS_HTTP": "false"     # ステートフルモードを使用
    }
    
    try:
        # 新規作成モードで起動（環境変数を追加）
        launch_result = agentcore_runtime.launch(
            auto_update_on_conflict=False,
            env_vars=env_vars
        )
        print("Launch completed ✓")
        print(f"Agent ARN: {launch_result.agent_arn}")
        print(f"Agent ID: {launch_result.agent_id}")
    except Exception as e:
        print(f"⚠ エージェントの起動中にエラーが発生しました: {e}")
        print("  別の方法で再試行します...")
        
        # 別の方法で再試行
        try:
            # auto_update_on_conflict=True で再試行（環境変数を追加）
            launch_result = agentcore_runtime.launch(
                auto_update_on_conflict=True,
                env_vars=env_vars
            )
            print("Launch completed with auto_update_on_conflict=True ✓")
            print(f"Agent ARN: {launch_result.agent_arn}")
            print(f"Agent ID: {launch_result.agent_id}")
        except Exception as e2:
            print(f"⚠ 2回目の試行でもエラーが発生しました: {e2}")
            print("  hosting_mcp_server.ja.ipynb ノートブックから手動でデプロイしてください")
            sys.exit(1)
    
    # Step 6: Check status
    print("\nStep 6: Checking AgentCore Runtime status...")
    status_response = agentcore_runtime.status()
    status = status_response.endpoint['status']
    print(f"Initial status: {status}")
    
    end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
    while status not in end_status:
        print(f"Status: {status} - waiting...")
        time.sleep(10)
        status_response = agentcore_runtime.status()
        status = status_response.endpoint['status']
    
    if status == 'READY':
        print("✓ AgentCore Runtime is READY!")
    else:
        print(f"⚠ AgentCore Runtime status: {status}")
        
    print(f"Final status: {status}")
    
    # Step 6.5: Verify CloudWatch Logs groups
    print("\nStep 6.5: Verifying CloudWatch Logs groups...")
    # エージェントIDを.bedrock_agentcore.yamlに保存するために少し待つ
    print("エージェントIDが.bedrock_agentcore.yamlに保存されるのを待っています...")
    time.sleep(10)
    # 既に設定済みなので、ここでは確認のみ
    try:
        logs_client = boto3.client('logs', region_name=region)
        log_groups = logs_client.describe_log_groups(
            logGroupNamePrefix='agents/mcp-server-logs'
        )
        if log_groups.get('logGroups'):
            print("✓ CloudWatch Logs groups verified")
        else:
            print("⚠ CloudWatch Logs groups not found, setting up again...")
            logs_result = setup_log_groups()
            if logs_result:
                print("✓ CloudWatch Logs groups setup completed")
            else:
                print("⚠ CloudWatch Logs groups setup failed, but continuing...")
    except Exception as e:
        print(f"⚠ Error verifying CloudWatch Logs groups: {e}")
        print("  Attempting to set up CloudWatch Logs groups again...")
        logs_result = setup_log_groups()
        if logs_result:
            print("✓ CloudWatch Logs groups setup completed")
        else:
            print("⚠ CloudWatch Logs groups setup failed, but continuing...")
    
    # Step 6.6: Setup X-Ray trace segment destination
    print("\nStep 6.6: Setting up X-Ray trace segment destination...")
    trace_result = setup_trace_destination()
    if trace_result:
        print("✓ X-Ray trace segment destination setup completed")
    else:
        print("⚠ X-Ray trace segment destination setup failed, but continuing...")
    
    # Step 7: Save configuration
    print("\nStep 7: Saving configuration...")
    ssm_client = boto3.client('ssm', region_name=region)
    secrets_client = boto3.client('secretsmanager', region_name=region)
    
    try:
        cognito_credentials_response = secrets_client.create_secret(
            Name='mcp_server/cognito/credentials',
            Description='Cognito credentials for MCP server',
            SecretString=json.dumps(cognito_config)
        )
        print("✓ Cognito credentials stored in Secrets Manager")
    except secrets_client.exceptions.ResourceExistsException:
        secrets_client.update_secret(
            SecretId='mcp_server/cognito/credentials',
            SecretString=json.dumps(cognito_config)
        )
        print("✓ Cognito credentials updated in Secrets Manager")
    
    agent_arn_response = ssm_client.put_parameter(
        Name='/mcp_server/runtime/agent_arn',
        Value=launch_result.agent_arn,
        Type='String',
        Description='Agent ARN for MCP server',
        Overwrite=True
    )
    print("✓ Agent ARN stored in Parameter Store")
    
    print("\nConfiguration stored successfully!")
    print(f"Agent ARN: {launch_result.agent_arn}")
    
    print("\n🎉 Redeployment completed successfully!")
    print("You can now test the MCP server using the my_mcp_client_remote_fixed.py script.")
    print("\n重要な変更点:")
    print("1. サーバー設定: ステートフルモード、接続タイムアウト増加、keep_alive=True")
    print("2. エラーハンドリング: ClosedResourceErrorの適切な処理")
    print("3. CloudWatch Logs: ロググループの事前設定")
    print("4. クライアント側: ヘッダー設定の最適化、リトライ機能の追加")

if __name__ == "__main__":
    main()
