import boto3
import json
import time
import os
import yaml
import shutil
import datetime
from boto3.session import Session


def setup_cognito_user_pool():
    boto_session = Session()
    region = boto_session.region_name
    
    # Initialize Cognito client from session
    cognito_client = boto_session.client('cognito-idp', region_name=region)
    pool_name = 'MCPServerPool'
    
    try:
        # まず既存のユーザープールを検索
        existing_pools = cognito_client.list_user_pools(MaxResults=60)
        pool_id = None
        client_id = None
        
        # 既存のプールを探す
        for pool in existing_pools.get('UserPools', []):
            if pool['Name'] == pool_name:
                pool_id = pool['Id']
                print(f"既存のユーザープール '{pool_name}' を見つけました: {pool_id}")
                break
        
        # ユーザープールが見つからない場合は新規作成
        if not pool_id:
            print(f"ユーザープール '{pool_name}' が見つからないため、新規作成します")
            user_pool_response = cognito_client.create_user_pool(
                PoolName=pool_name,
                Policies={
                    'PasswordPolicy': {
                        'MinimumLength': 8
                    }
                }
            )
            pool_id = user_pool_response['UserPool']['Id']
            
            # 新規プールにアプリクライアントを作成
            app_client_response = cognito_client.create_user_pool_client(
                UserPoolId=pool_id,
                ClientName='MCPServerPoolClient',
                GenerateSecret=False,
                ExplicitAuthFlows=[
                    'ALLOW_USER_PASSWORD_AUTH',
                    'ALLOW_REFRESH_TOKEN_AUTH'
                ]
            )
            client_id = app_client_response['UserPoolClient']['ClientId']
            
            # ユーザーを作成
            try:
                cognito_client.admin_create_user(
                    UserPoolId=pool_id,
                    Username='testuser',
                    TemporaryPassword='Temp123!',
                    MessageAction='SUPPRESS'
                )
                
                # 永続パスワードを設定
                cognito_client.admin_set_user_password(
                    UserPoolId=pool_id,
                    Username='testuser',
                    Password='MyPassword123!',
                    Permanent=True
                )
            except cognito_client.exceptions.UsernameExistsException:
                print("ユーザー 'testuser' は既に存在します")
        else:
            # 既存のプールからクライアントIDを取得
            clients = cognito_client.list_user_pool_clients(
                UserPoolId=pool_id,
                MaxResults=60
            )
            
            for client in clients.get('UserPoolClients', []):
                if client['ClientName'] == 'MCPServerPoolClient':
                    client_id = client['ClientId']
                    print(f"既存のクライアント 'MCPServerPoolClient' を見つけました: {client_id}")
                    break
            
            # クライアントが見つからない場合は新規作成
            if not client_id:
                print("クライアント 'MCPServerPoolClient' が見つからないため、新規作成します")
                app_client_response = cognito_client.create_user_pool_client(
                    UserPoolId=pool_id,
                    ClientName='MCPServerPoolClient',
                    GenerateSecret=False,
                    ExplicitAuthFlows=[
                        'ALLOW_USER_PASSWORD_AUTH',
                        'ALLOW_REFRESH_TOKEN_AUTH'
                    ]
                )
                client_id = app_client_response['UserPoolClient']['ClientId']
                
            # ユーザーを確認
            try:
                cognito_client.admin_get_user(
                    UserPoolId=pool_id,
                    Username='testuser'
                )
                print("ユーザー 'testuser' が存在することを確認しました")
            except cognito_client.exceptions.UserNotFoundException:
                # ユーザーが存在しない場合は作成
                print("ユーザー 'testuser' が見つからないため、新規作成します")
                cognito_client.admin_create_user(
                    UserPoolId=pool_id,
                    Username='testuser',
                    TemporaryPassword='Temp123!',
                    MessageAction='SUPPRESS'
                )
                
                # 永続パスワードを設定
                cognito_client.admin_set_user_password(
                    UserPoolId=pool_id,
                    Username='testuser',
                    Password='MyPassword123!',
                    Permanent=True
                )
        
        # トークンを取得（常に最新のトークンを取得）
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': 'testuser',
                'PASSWORD': 'MyPassword123!'
            }
        )
        bearer_token = auth_response['AuthenticationResult']['AccessToken']
        
        # 必要な値を出力
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration")
        print(f"Client ID: {client_id}")
        print(f"Bearer Token: {bearer_token}")
        
        # 処理に必要な値を返す
        return {
            'pool_id': pool_id,
            'client_id': client_id,
            'bearer_token': bearer_token,
            'discovery_url': f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return None


def create_agentcore_role(agent_name):
    # セッションを作成
    boto_session = Session()
    region = boto_session.region_name
    
    # セッションからクライアントを作成
    iam_client = boto_session.client('iam')
    sts_client = boto_session.client('sts')
    
    # 現在のセッション情報をログ出力（デバッグ用）
    print(f"使用中のプロファイル: {boto_session.profile_name}")
    print(f"使用中のリージョン: {region}")
    
    agentcore_role_name = f'agentcore-{agent_name}-role'
    account_id = sts_client.get_caller_identity()["Account"]
    print(f"アカウントID: {account_id}")
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockPermissions",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": "*"
            },
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:DescribeImages",
                    "ecr:ListImages",
                    "ecr:DescribeRepositories"
                ],
                "Resource": [
                    f"arn:aws:ecr:{region}:{account_id}:repository/*",
                    f"arn:aws:ecr:{region}:{account_id}:repository/bedrock-agentcore-*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogStreams",
                    "logs:CreateLogGroup"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogGroups",
                    "logs:PutRetentionPolicy"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                ]
            },
            {
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:agents/mcp-server-logs:*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:*"
                ]
            },
             {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                }
            },
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                ],
                "Resource": [
                  f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                  f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/{agent_name}-*"
                ]
            },
            {
                "Sid": "SpansLogGroupAccess",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:aws/spans:*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:aws/otel/traces:*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/application-signals/data:*"
                ]
            },
            {
                "Sid": "OTELPermissions",
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                    "xray:GetSamplingStatisticSummaries",
                    "xray:GetTraceSegmentDestination",
                    "xray:UpdateTraceSegmentDestination",
                    "xray:UpdateIndexingRule"
                ],
                "Resource": "*"
            },
            {
                "Sid": "SSMParametersAccess",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameters"
                ],
                "Resource": "*"
            }
        ]
    }
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": f"{account_id}"
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
            }
        ]
    }

    assume_role_policy_document_json = json.dumps(
        assume_role_policy_document
    )
    role_policy_document = json.dumps(role_policy)
    # Create IAM Role for the Lambda function
    try:
        print(f"IAMロール {agentcore_role_name} の作成を試みます")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

        # Pause to make sure role is created
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print(f"ロール {agentcore_role_name} は既に存在します - 削除して再作成します")
        policies = iam_client.list_role_policies(
            RoleName=agentcore_role_name,
            MaxItems=100
        )
        print("policies:", policies)
        for policy_name in policies['PolicyNames']:
            iam_client.delete_role_policy(
                RoleName=agentcore_role_name,
                PolicyName=policy_name
            )
        print(f"{agentcore_role_name} を削除中")
        iam_client.delete_role(
            RoleName=agentcore_role_name
        )
        print(f"{agentcore_role_name} を再作成中")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )
    except Exception as e:
        print(f"IAMロールの作成中にエラーが発生しました: {e}")
        # エラーが発生した場合はダミーのロール情報を返す
        # これにより、ローカルテストを続行できる
        agentcore_iam_role = {
            'Role': {
                'Arn': f'arn:aws:iam::123456789012:role/{agentcore_role_name}',
                'RoleName': agentcore_role_name
            }
        }
        print(f"ダミーのロール情報を使用します: {agentcore_iam_role['Role']['Arn']}")
        # Attach the AWSLambdaBasicExecutionRole policy
    print(f"attaching role policy {agentcore_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_role_name
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role


def reset_agentcore_yaml(path=None, mode="null_session", backup=True, agent_name=None):
    """
    .bedrock_agentcore.yaml ファイルをリセットまたは修正します。
    
    Args:
        path (str): .bedrock_agentcore.yaml ファイルのパス。None の場合はカレントディレクトリを使用。
        mode (str): リセットモード
            - "null_session": セッションIDをnullに設定（デフォルト）
            - "delete": ファイルを完全に削除
            - "clean": 問題のある部分を修正（セッションID、ロール名の問題など）
        backup (bool): バックアップを作成するかどうか
        agent_name (str): 対象のエージェント名。None の場合はデフォルトエージェントを使用。
    
    Returns:
        bool: 成功した場合はTrue、失敗した場合はFalse
    """
    try:
        # パスが指定されていない場合はカレントディレクトリを使用
        if path is None:
            path = os.getcwd()
        
        # ディレクトリの場合はファイルパスを構築
        if os.path.isdir(path):
            yaml_path = os.path.join(path, '.bedrock_agentcore.yaml')
        else:
            yaml_path = path
        
        # ファイルが存在するか確認
        if not os.path.exists(yaml_path):
            print(f"エラー: {yaml_path} が見つかりません。")
            return False
        
        # バックアップを作成
        if backup:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            backup_path = f"{yaml_path}.bak-{timestamp}"
            shutil.copy2(yaml_path, backup_path)
            print(f"バックアップを作成しました: {backup_path}")
        
        # モードに応じた処理
        if mode == "delete":
            # ファイルを完全に削除
            os.remove(yaml_path)
            print(f"{yaml_path} を削除しました。")
            return True
        
        # YAMLファイルを読み込む
        with open(yaml_path, 'r') as file:
            config = yaml.safe_load(file)
        
        if mode == "null_session":
            # エージェント名が指定されていない場合はデフォルトエージェントを使用
            if agent_name is None:
                if 'default_agent' in config:
                    agent_name = config['default_agent']
                else:
                    # エージェントが1つしかない場合はそれを使用
                    if 'agents' in config and len(config['agents']) == 1:
                        agent_name = list(config['agents'].keys())[0]
                    else:
                        print("エラー: エージェント名を指定してください。")
                        return False
            
            # セッションIDをnullに設定
            if 'agents' in config and agent_name in config['agents']:
                if 'bedrock_agentcore' in config['agents'][agent_name]:
                    config['agents'][agent_name]['bedrock_agentcore']['agent_session_id'] = None
                    print(f"エージェント '{agent_name}' のセッションIDをnullに設定しました。")
                else:
                    print(f"警告: エージェント '{agent_name}' にbedrock_agentcoreセクションがありません。")
            else:
                print(f"エラー: エージェント '{agent_name}' が見つかりません。")
                return False
        
        elif mode == "clean":
            # エージェント名が指定されていない場合はすべてのエージェントを処理
            if agent_name is None:
                agents_to_process = list(config.get('agents', {}).keys())
            else:
                agents_to_process = [agent_name]
            
            for agent in agents_to_process:
                if agent in config.get('agents', {}):
                    # セッションIDをnullに設定
                    if 'bedrock_agentcore' in config['agents'][agent]:
                        config['agents'][agent]['bedrock_agentcore']['agent_session_id'] = None
                    
                    # ロール名の問題を修正
                    if 'aws' in config['agents'][agent] and 'execution_role' in config['agents'][agent]['aws']:
                        role_arn = config['agents'][agent]['aws']['execution_role']
                        # ロール名から無効な文字を削除
                        if '/' in role_arn:
                            role_name = role_arn.split('/')[-1]
                            valid_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+=,.@_-"
                            cleaned_role_name = ''.join(c for c in role_name if c in valid_chars)
                            if cleaned_role_name != role_name:
                                new_role_arn = role_arn.replace(role_name, cleaned_role_name)
                                config['agents'][agent]['aws']['execution_role'] = new_role_arn
                                print(f"エージェント '{agent}' のロール名を修正しました: {role_name} -> {cleaned_role_name}")
                    
                    print(f"エージェント '{agent}' の設定をクリーンアップしました。")
        
        # 変更を保存
        with open(yaml_path, 'w') as file:
            yaml.dump(config, file, default_flow_style=False)
        
        print(f"{yaml_path} を更新しました。")
        return True
    
    except Exception as e:
        print(f"エラー: {e}")
        return False


def restore_agentcore_yaml(backup_path, target_path=None):
    """
    バックアップから .bedrock_agentcore.yaml ファイルを復元します。
    
    Args:
        backup_path (str): バックアップファイルのパス
        target_path (str): 復元先のパス。None の場合はカレントディレクトリを使用。
    
    Returns:
        bool: 成功した場合はTrue、失敗した場合はFalse
    """
    try:
        # 復元先のパスが指定されていない場合はカレントディレクトリを使用
        if target_path is None:
            target_path = os.path.join(os.getcwd(), '.bedrock_agentcore.yaml')
        
        # ディレクトリの場合はファイルパスを構築
        if os.path.isdir(target_path):
            target_path = os.path.join(target_path, '.bedrock_agentcore.yaml')
        
        # バックアップファイルが存在するか確認
        if not os.path.exists(backup_path):
            print(f"エラー: バックアップファイル {backup_path} が見つかりません。")
            return False
        
        # 復元先のファイルが存在する場合はバックアップを作成
        if os.path.exists(target_path):
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            current_backup = f"{target_path}.before-restore-{timestamp}"
            shutil.copy2(target_path, current_backup)
            print(f"現在のファイルのバックアップを作成しました: {current_backup}")
        
        # バックアップから復元
        shutil.copy2(backup_path, target_path)
        print(f"{backup_path} から {target_path} に復元しました。")
        return True
    
    except Exception as e:
        print(f"エラー: {e}")
        return False
