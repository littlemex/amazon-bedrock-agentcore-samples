import asyncio
import boto3
import json
import sys
import re
from boto3.session import Session
import aiohttp

async def main():
    boto_session = Session()
    region = boto_session.region_name
    
    print(f"Using AWS region: {region}")
    
    try:
        ssm_client = boto3.client('ssm', region_name=region)
        agent_arn_response = ssm_client.get_parameter(Name='/mcp_server/runtime/agent_arn')
        agent_arn = agent_arn_response['Parameter']['Value']
        print(f"Retrieved Agent ARN: {agent_arn}")

        secrets_client = boto3.client('secretsmanager', region_name=region)
        response = secrets_client.get_secret_value(SecretId='mcp_server/cognito/credentials')
        secret_value = response['SecretString']
        parsed_secret = json.loads(secret_value)
        bearer_token = parsed_secret['bearer_token']
        print("✓ Retrieved bearer token from Secrets Manager")
        
    except Exception as e:
        print(f"Error retrieving credentials: {e}")
        sys.exit(1)
    
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    print(f"\nConnecting to: {mcp_url}")
    print("Headers configured ✓")

    # シンプルなHTTPリクエストを試みる
    try:
        async with aiohttp.ClientSession() as session:
            # 基本的なJSONRPC初期化リクエスト
            payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": 1
            }
            
            print("\n🔄 Sending simple HTTP request...")
            async with session.post(mcp_url, headers=headers, json=payload, timeout=60) as response:
                print(f"Status: {response.status}")
                print(f"Headers: {response.headers}")
                
                # レスポンスボディを取得
                try:
                    text = await response.text()
                    print(f"Response text: {text}")
                    
                    # "id":UUID パターンを検出して修正
                    pattern = r'"id":([^",\s\}]+)'
                    replacement = r'"id":"\1"'
                    fixed_text = re.sub(pattern, replacement, text)
                    
                    if fixed_text != text:
                        print(f"UUID形式を修正しました: {fixed_text}")
                    
                    # JSONとして解析を試みる
                    try:
                        json_response = json.loads(fixed_text)
                        print(f"Parsed JSON: {json.dumps(json_response, indent=2)}")
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse response as JSON: {e}")
                        # エラー位置の周辺を表示
                        error_pos = e.pos
                        start = max(0, error_pos - 20)
                        end = min(len(fixed_text), error_pos + 20)
                        print(f"Error context: ...{fixed_text[start:error_pos]}[HERE]{fixed_text[error_pos:end]}...")
                except Exception as e:
                    print(f"Error reading response: {e}")
    
    except Exception as e:
        print(f"❌ Error in HTTP request: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
