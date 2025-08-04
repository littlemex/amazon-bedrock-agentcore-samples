import requests
import urllib.parse
import json
import yaml
import os
import logging
import time

# 詳細なログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# HTTPリクエストのログを有効化
logging.getLogger("urllib3").setLevel(logging.DEBUG)
logging.getLogger("requests").setLevel(logging.DEBUG)

try:
    # YAMLファイルからエージェント情報を取得
    with open('.bedrock_agentcore.yaml', 'r') as file:
        config = yaml.safe_load(file)
        logger.info("YAML設定ファイルを読み込みました")

    # エージェント情報を抽出
    agent_name = config['default_agent']
    agent_config = config['agents'][agent_name]
    agent_id = agent_config['bedrock_agentcore']['agent_id']
    agent_arn = agent_config['bedrock_agentcore']['agent_arn']
    region = agent_config['aws']['region']

    logger.info(f"Agent ID: {agent_id}")
    logger.info(f"Agent ARN: {agent_arn}")
    logger.info(f"Region: {region}")

    # 正しいエンドポイントURLを構築（リージョンを使用）
    BEDROCK_AGENT_CORE_ENDPOINT_URL = f"https://bedrock-agentcore.{region}.amazonaws.com"
    logger.info(f"Endpoint URL: {BEDROCK_AGENT_CORE_ENDPOINT_URL}")

    # Cognitoクライアントを初期化
    import boto3
    cognito_client = boto3.client('cognito-idp', region_name=region)
    logger.info("Cognitoクライアントを初期化しました")

    # ユーザープールIDを取得
    user_pools = cognito_client.list_user_pools(MaxResults=60)
    pool_id = None
    for pool in user_pools['UserPools']:
        if pool['Name'] == 'DemoUserPool':
            pool_id = pool['Id']
            break

    if not pool_id:
        logger.error("DemoUserPoolが見つかりません。setup_cognito_user_pool.shを実行してください。")
    else:
        logger.info(f"User Pool ID: {pool_id}")
        
        # クライアントIDを取得
        clients = cognito_client.list_user_pool_clients(
            UserPoolId=pool_id,
            MaxResults=60
        )
        
        client_id = None
        for client in clients['UserPoolClients']:
            if client['ClientName'] == 'DemoClient':
                client_id = client['ClientId']
                break
        
        if not client_id:
            logger.error("DemoClientが見つかりません。")
        else:
            logger.info(f"Client ID: {client_id}")
            
            # アクセストークンを取得
            try:
                auth_response = cognito_client.initiate_auth(
                    ClientId=client_id,
                    AuthFlow='USER_PASSWORD_AUTH',
                    AuthParameters={
                        'USERNAME': 'testuser',
                        'PASSWORD': 'MyPassword123!'
                    }
                )
                
                cognito_bearer_token = auth_response['AuthenticationResult']['AccessToken']
                logger.info(f"認証トークンを取得しました: {cognito_bearer_token[:20]}...")
                
                # エージェントARNをURLエンコード
                escaped_agent_arn = urllib.parse.quote(agent_arn, safe='')
                
                # 完全なURLを構築
                url = f"{BEDROCK_AGENT_CORE_ENDPOINT_URL}/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
                logger.info(f"リクエストURL: {url}")
                
                # ヘッダーを設定
                headers = {
                    "Authorization": f"Bearer {cognito_bearer_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "7a750a8c-11ab-447a-aec9-fe7b38402088222"
                }
                logger.info(f"リクエストヘッダー: {headers}")
                
                # ペイロードを設定 - 形式を修正
                payload = {
                    "prompt": "Hello"
                }
                payload_json = json.dumps(payload)
                logger.info(f"リクエストペイロード: {payload_json}")
                
                # エージェントを呼び出す（タイムアウトを設定）
                logger.info("リクエスト送信開始...")
                start_time = time.time()
                
                invoke_response = requests.post(
                    url,
                    headers=headers,
                    data=payload_json,
                    timeout=30  # 30秒のタイムアウトを設定
                )
                
                end_time = time.time()
                logger.info(f"リクエスト完了。所要時間: {end_time - start_time:.2f}秒")
                
                # レスポンスを表示
                logger.info(f"ステータスコード: {invoke_response.status_code}")
                logger.info(f"レスポンスヘッダー: {dict(invoke_response.headers)}")

                if invoke_response.status_code == 200:
                    logger.info("レスポンスJSON:")
                    logger.info(invoke_response.text)  # 生のレスポンステキストを直接表示
                    try:
                        response_data = invoke_response.json()
                        logger.info("パース済みJSON:")
                        logger.info(json.dumps(response_data, indent=2))
                    except json.JSONDecodeError:
                        logger.error("JSONデコードエラー")

                elif invoke_response.status_code >= 400:
                    logger.error(f"エラーレスポンス ({invoke_response.status_code}):")
                    try:
                        error_data = invoke_response.json()
                        logger.error(json.dumps(error_data, indent=2))
                    except:
                        logger.error(invoke_response.text[:1000])
                else:
                    logger.warning(f"予期しないステータスコード: {invoke_response.status_code}")
                    logger.warning("レスポンステキスト:")
                    logger.warning(invoke_response.text[:1000])
                    
            except requests.exceptions.Timeout:
                logger.error("リクエストがタイムアウトしました。サーバーが応答していません。")
            except requests.exceptions.RequestException as e:
                logger.error(f"リクエストエラー: {str(e)}")
            except Exception as e:
                logger.error(f"エラー: {str(e)}")
                logger.exception("詳細なエラー情報:")

except Exception as e:
    logger.error(f"スクリプト実行エラー: {str(e)}")
    logger.exception("詳細なエラー情報:")
