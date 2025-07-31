import asyncio
import boto3
import json
import sys
import re
import traceback
import aiohttp
from boto3.session import Session

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
    
    if not agent_arn or not bearer_token:
        print("Error: AGENT_ARN or BEARER_TOKEN not retrieved properly")
        sys.exit(1)
    
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    print(f"\nConnecting to: {mcp_url}")
    print("Headers configured ✓")

    # 直接HTTPリクエストを使用してMCPサーバーと通信
    try:
        async with aiohttp.ClientSession() as session:
            # 初期化リクエスト
            print("\n🔄 Initializing MCP session...")
            init_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": "init-1"
            }
            
            async with session.post(mcp_url, headers=headers, json=init_payload, timeout=60) as response:
                print(f"Initialize Status: {response.status}")
                text = await response.text()
                
                # レスポンスを修正してJSONとして解析
                try:
                    # "id":UUID パターンを検出して修正
                    pattern = r'"id":([^",\s\}]+)'
                    replacement = r'"id":"\1"'
                    fixed_text = re.sub(pattern, replacement, text)
                    
                    if fixed_text != text:
                        print(f"UUID形式を修正しました: {fixed_text}")
                    
                    json_response = json.loads(fixed_text)
                    print("✓ MCP session initialized")
                except json.JSONDecodeError as e:
                    print(f"Failed to parse response as JSON: {e}")
                    sys.exit(1)
            
            # ツール一覧を取得
            print("\n🔄 Listing available tools...")
            list_tools_payload = {
                "jsonrpc": "2.0",
                "method": "mcp/list_tools",
                "params": {},
                "id": "list-tools-1"
            }
            
            async with session.post(mcp_url, headers=headers, json=list_tools_payload, timeout=60) as response:
                print(f"List Tools Status: {response.status}")
                text = await response.text()
                
                # レスポンスを修正してJSONとして解析
                try:
                    # "id":UUID パターンを検出して修正
                    pattern = r'"id":([^",\s\}]+)'
                    replacement = r'"id":"\1"'
                    fixed_text = re.sub(pattern, replacement, text)
                    
                    if fixed_text != text:
                        print(f"UUID形式を修正しました: {fixed_text}")
                    
                    tools_response = json.loads(fixed_text)
                    
                    if "result" in tools_response and "tools" in tools_response["result"]:
                        tools = tools_response["result"]["tools"]
                        
                        print("\n📋 Available MCP Tools:")
                        print("=" * 50)
                        for tool in tools:
                            print(f"🔧 {tool['name']}")
                            print(f"   Description: {tool.get('description', 'No description')}")
                            if "inputSchema" in tool and "properties" in tool["inputSchema"]:
                                properties = tool["inputSchema"]["properties"]
                                print(f"   Parameters: {list(properties.keys())}")
                            print()
                        
                        print(f"✅ Successfully connected to MCP server!")
                        print(f"Found {len(tools)} tools available.")
                    else:
                        print("❌ No tools found in response")
                        print(f"Response: {tools_response}")
                except json.JSONDecodeError as e:
                    print(f"Failed to parse response as JSON: {e}")
                    sys.exit(1)
                
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
