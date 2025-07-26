#!/usr/bin/env python3
"""
ARM64ビルド環境セットアップスクリプト

このスクリプトは以下を行います：
1. 現在のプラットフォームを確認
2. プラットフォームがarm64でない場合、QEMUエミュレーションを設定
3. DOCKER_DEFAULT_PLATFORMを設定
4. テスト用のDockerfileを作成してビルド
5. ビルドが成功したかどうかを確認

使用方法:
    python setup_arm64_build.py
"""

import os
import sys
import subprocess
import platform
import tempfile
import shutil

def run_command(command, check=True, capture_output=True):
    """コマンドを実行し、結果を返す"""
    print(f"実行: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            text=True,
            capture_output=capture_output
        )
        if capture_output:
            print(f"出力: {result.stdout}")
            if result.stderr:
                print(f"エラー: {result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"コマンド実行エラー: {e}")
        print(f"出力: {e.stdout}")
        print(f"エラー: {e.stderr}")
        if check:
            sys.exit(1)
        return e

def check_platform():
    """現在のプラットフォームを確認"""
    print("現在のプラットフォームを確認中...")
    
    # プラットフォームの確認
    machine = platform.machine()
    print(f"マシンアーキテクチャ: {machine}")
    
    # Dockerのプラットフォームを確認
    docker_info = run_command("docker info --format '{{.Architecture}}'")
    docker_arch = docker_info.stdout.strip()
    print(f"Dockerアーキテクチャ: {docker_arch}")
    
    return machine, docker_arch

def setup_qemu():
    """QEMUエミュレーションを設定"""
    print("\nQEMUエミュレーションを設定中...")
    
    # QEMUが既にインストールされているか確認
    qemu_check = run_command("which qemu-aarch64-static", check=False)
    if qemu_check.returncode == 0:
        print("QEMUは既にインストールされています")
    else:
        print("QEMUがインストールされていません。インストールが必要な場合があります。")
    
    # QEMUエミュレーションを設定
    print("QEMUエミュレーションを設定中...")
    run_command("docker run --rm --privileged multiarch/qemu-user-static --reset -p yes")
    print("QEMUエミュレーションが設定されました")

def setup_docker_platform():
    """DOCKER_DEFAULT_PLATFORMを設定"""
    print("\nDOCKER_DEFAULT_PLATFORMを設定中...")
    
    # 環境変数を設定
    os.environ['DOCKER_DEFAULT_PLATFORM'] = 'linux/arm64'
    print("環境変数が設定されました: DOCKER_DEFAULT_PLATFORM=linux/arm64")
    
    # Docker buildxが利用可能か確認
    buildx_check = run_command("docker buildx version", check=False)
    if buildx_check.returncode != 0:
        print("Docker buildxが利用できません。インストールが必要です。")
        sys.exit(1)
    
    # Docker buildxのビルダーインスタンスを確認
    buildx_ls = run_command("docker buildx ls")
    
    # ARM64プラットフォームがサポートされているか確認
    if "linux/arm64" not in buildx_ls.stdout:
        print("ARM64プラットフォームがサポートされていません。QEMUエミュレーションが正しく設定されているか確認してください。")
        sys.exit(1)
    
    print("Docker buildxがARM64プラットフォームをサポートしています")

def test_arm64_build():
    """テスト用のDockerfileを作成してビルド"""
    print("\nテスト用のDockerfileを作成してビルド中...")
    
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    print(f"一時ディレクトリを作成しました: {temp_dir}")
    
    try:
        # テスト用のDockerfileを作成
        dockerfile_path = os.path.join(temp_dir, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write("""FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.10-slim
WORKDIR /app
RUN echo "ARM64ビルドテスト" > test.txt
CMD ["cat", "test.txt"]
""")
        print(f"テスト用のDockerfileを作成しました: {dockerfile_path}")
        
        # Dockerイメージをビルド
        print("Dockerイメージをビルド中...")
        build_result = run_command(f"cd {temp_dir} && docker buildx build --platform=linux/arm64 -t arm64-test .")
        
        # ビルドが成功したかどうかを確認
        if build_result.returncode == 0:
            print("ARM64ビルドが成功しました！")
            
            # テストイメージを実行
            print("\nテストイメージを実行中...")
            run_command("docker run --rm arm64-test")
            
            return True
        else:
            print("ARM64ビルドが失敗しました")
            return False
    finally:
        # 一時ディレクトリを削除
        shutil.rmtree(temp_dir)
        print(f"一時ディレクトリを削除しました: {temp_dir}")

def generate_sample_code():
    """サンプルコードを生成"""
    print("\nBedrock AgentCore用のサンプルコードを生成中...")
    
    sample_code = """
# Bedrock AgentCore用のサンプルコード

# 環境変数を設定
import os
os.environ['DOCKER_DEFAULT_PLATFORM'] = 'linux/arm64'

# AgentCore Runtimeを初期化
from bedrock_agentcore_starter_toolkit import Runtime
agentcore_runtime = Runtime()

# AgentCore Runtimeを設定
response = agentcore_runtime.configure(
    entrypoint="your_entrypoint.py",  # エントリポイントファイルを指定
    execution_role="your_execution_role_arn",  # 実行ロールのARNを指定
    auto_create_ecr=True,
    requirements_file="requirements.txt",  # 要件ファイルを指定
    region="your_region",  # リージョンを指定
    agent_name="your_agent_name"  # エージェント名を指定
)

# AgentCore Runtimeを起動
launch_result = agentcore_runtime.launch()
print(launch_result)
"""
    
    # サンプルコードをファイルに保存
    sample_code_path = os.path.join(os.path.dirname(__file__), "bedrock_agentcore_arm64_sample.py")
    with open(sample_code_path, "w") as f:
        f.write(sample_code)
    
    print(f"サンプルコードを保存しました: {sample_code_path}")
    print("\nサンプルコードの使用方法:")
    print("1. エントリポイントファイル、実行ロールのARN、リージョン、エージェント名を指定します")
    print("2. スクリプトを実行します")

def main():
    """メイン関数"""
    print("ARM64ビルド環境セットアップスクリプト\n")
    
    # 現在のプラットフォームを確認
    machine, docker_arch = check_platform()
    
    # プラットフォームがarm64でない場合、QEMUエミュレーションを設定
    if machine != "aarch64" and machine != "arm64":
        setup_qemu()
    else:
        print("\nプラットフォームはすでにARM64です。QEMUエミュレーションは不要です。")
    
    # DOCKER_DEFAULT_PLATFORMを設定
    setup_docker_platform()
    
    # テスト用のDockerfileを作成してビルド
    success = test_arm64_build()
    
    if success:
        # サンプルコードを生成
        generate_sample_code()
        
        print("\n設定が完了しました！")
        print("これで、Bedrock AgentCoreでARM64ビルドを実行できます。")
    else:
        print("\n設定に問題があります。エラーを確認してください。")

if __name__ == "__main__":
    main()
