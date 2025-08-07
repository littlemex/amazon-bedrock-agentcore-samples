import boto3
import json
import os
from boto3.session import Session

def setup_trace_destination():
    """
    AWS X-Rayのトレースセグメントの送信先をCloudWatch Logsに設定します。
    これにより、OpenTelemetryトレースエクスポーターがCloudWatch Logsにトレースを送信できるようになります。
    """
    print("AWS X-Rayのトレースセグメント送信先を設定しています...")
    
    # リージョンを明示的に設定
    boto_session = Session()
    region = boto_session.region_name
    print(f"使用するリージョン: {region}")
    
    # アカウントIDを取得
    sts_client = boto3.client('sts', region_name=region)
    account_id = sts_client.get_caller_identity()["Account"]
    print(f"アカウントID: {account_id}")
    
    # ステップ1: CloudWatch Logsへのアクセス権限を付与するリソースポリシーを作成
    try:
        print("ステップ1: CloudWatch Logsリソースポリシーを設定しています...")
        logs_client = boto3.client('logs', region_name=region)
        
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "TransactionSearchXRayAccess",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "xray.amazonaws.com"
                    },
                    "Action": [
                        "logs:PutLogEvents",
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams"
                    ],
                    "Resource": [
                        f"arn:aws:logs:{region}:{account_id}:log-group:aws/spans:*",
                        f"arn:aws:logs:{region}:{account_id}:log-group:aws/spans",
                        f"arn:aws:logs:{region}:{account_id}:log-group:/aws/application-signals/data:*",
                        f"arn:aws:logs:{region}:{account_id}:log-group:/aws/application-signals/data"
                    ]
                }
            ]
        }
        
        logs_client.put_resource_policy(
            policyName="TransactionSearchPolicy",
            policyDocument=json.dumps(policy_document)
        )
        print("✓ CloudWatch Logsリソースポリシーを設定しました")
    except Exception as e:
        print(f"⚠ CloudWatch Logsリソースポリシーの設定中にエラーが発生しました: {e}")
    
    # ステップ2: トレースセグメントの送信先をCloudWatch Logsに設定
    try:
        print("ステップ2: トレースセグメントの送信先を設定しています...")
        xray_client = boto3.client('xray', region_name=region)
        
        # 現在の設定を確認
        current_destination = xray_client.get_trace_segment_destination()
        current_dest = current_destination.get('Destination', 'なし')
        current_status = current_destination.get('Status', 'なし')
        print(f"現在の送信先: {current_dest}, ステータス: {current_status}")
        
        # 既にCloudWatchLogsに設定されているか、PENDING状態の場合はスキップ
        if current_dest == "CloudWatchLogs":
            if current_status == "PENDING":
                print("✓ トレースセグメントの送信先は既にCloudWatch Logsに設定中です（PENDING状態）")
            else:
                print("✓ トレースセグメントの送信先は既にCloudWatch Logsに設定されています")
        elif current_status == "PENDING":
            print("⚠ 現在PENDING状態のため、トレースセグメントの送信先を変更できません")
            print("  現在の処理が完了するまでお待ちください")
        else:
            # 送信先をCloudWatch Logsに更新
            xray_client.update_trace_segment_destination(
                Destination="CloudWatchLogs"
            )
            print("✓ トレースセグメントの送信先をCloudWatch Logsに設定しました")
    except Exception as e:
        print(f"⚠ トレースセグメントの送信先の設定中にエラーが発生しました: {e}")
    
    # ステップ3: インデックス化するスパンの割合を設定（デフォルトは1%）
    try:
        print("ステップ3: インデックス化するスパンの割合を設定しています...")
        xray_client.update_indexing_rule(
            Name="Default",
            Rule={"Probabilistic": {"DesiredSamplingPercentage": 1}}
        )
        print("✓ インデックス化するスパンの割合を1%に設定しました")
    except Exception as e:
        print(f"⚠ インデックス化するスパンの割合の設定中にエラーが発生しました: {e}")
    
    # ステップ4: 設定が正しく適用されたことを確認
    try:
        print("ステップ4: 設定を確認しています...")
        destination_response = xray_client.get_trace_segment_destination()
        destination = destination_response.get('Destination')
        status = destination_response.get('Status')
        
        print(f"送信先: {destination}, ステータス: {status}")
        
        if destination == "CloudWatchLogs":
            if status == "ACTIVE":
                print("✓ トレースセグメントの送信先が正しく設定されました")
                return True
            elif status == "PENDING":
                print("✓ トレースセグメントの送信先はCloudWatch Logsに設定中です（PENDING状態）")
                print("  設定が反映されるまで数分かかる場合があります")
                return True  # PENDING状態も成功とみなす
            else:
                print(f"⚠ トレースセグメントの送信先の設定状態が異常です: {status}")
                return False
        else:
            print("⚠ トレースセグメントの送信先の設定が完了していません")
            print(f"  現在の状態: 送信先={destination}, ステータス={status}")
            print("  設定が反映されるまで数分かかる場合があります")
            return False
    except Exception as e:
        print(f"⚠ 設定の確認中にエラーが発生しました: {e}")
        return False

if __name__ == "__main__":
    setup_trace_destination()
