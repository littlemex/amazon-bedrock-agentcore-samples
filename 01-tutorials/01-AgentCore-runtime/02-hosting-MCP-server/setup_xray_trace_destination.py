import boto3
import json
import time
import os
import sys
from boto3.session import Session

def setup_xray_trace_destination():
    """
    X-Ray Trace Segment DestinationをCloudWatch Logsに設定します。
    これにより、OpenTelemetryからのトレースデータがCloudWatch Logsに送信されるようになります。
    """
    print("X-Ray Trace Segment Destinationの設定を開始します...")
    
    # セッションを作成
    boto_session = Session()
    region = boto_session.region_name
    
    # X-Rayクライアントを作成
    xray_client = boto_session.client('xray', region_name=region)
    
    # STSクライアントを作成してアカウントIDを取得
    sts_client = boto_session.client('sts')
    account_id = sts_client.get_caller_identity()["Account"]
    
    # 現在の設定を確認
    try:
        current_config = xray_client.get_trace_segment_destination_configuration()
        print(f"現在の設定: {json.dumps(current_config, default=str)}")
    except Exception as e:
        print(f"現在の設定の取得中にエラーが発生しました: {e}")
        print("設定が存在しない可能性があります。新規作成を試みます。")
    
    # CloudWatch Logsの設定
    log_group_name = "aws/spans"
    
    # CloudWatch Logsの設定を作成
    try:
        response = xray_client.update_trace_segment_destination(
            Destination={
                'CloudWatch': {
                    'LogGroup': log_group_name
                }
            }
        )
        print(f"X-Ray Trace Segment Destinationの設定が完了しました: {json.dumps(response, default=str)}")
        
        # 設定が反映されるまで少し待機
        print("設定が反映されるまで待機しています...")
        time.sleep(5)
        
        # 設定を確認
        updated_config = xray_client.get_trace_segment_destination_configuration()
        print(f"更新後の設定: {json.dumps(updated_config, default=str)}")
        
        return True
    except Exception as e:
        print(f"X-Ray Trace Segment Destinationの設定中にエラーが発生しました: {e}")
        return False

if __name__ == "__main__":
    setup_xray_trace_destination()
