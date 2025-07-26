#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import os
import argparse
import boto3
import time
from typing import Dict, List, Any, Tuple

def extract_comments(code: str) -> Tuple[List[Tuple[str, str]], str]:
    """
    コードからコメントを抽出し、コメントとその位置情報のリストを返す
    
    Args:
        code: Pythonコード
        
    Returns:
        コメントとその位置情報のリスト、コメントを除去したコード
    """
    # 複数行コメントを抽出 (""" """)
    multiline_comments = []
    pattern = r'(""".*?""")'
    matches = re.finditer(pattern, code, re.DOTALL)
    
    # コメントとその位置を記録
    positions = []
    for match in matches:
        start, end = match.span()
        comment = match.group(1)
        positions.append((comment, f"MULTILINE_COMMENT_{len(positions)}"))
        
    # 複数行コメントをプレースホルダーに置き換え
    for comment, placeholder in positions:
        code = code.replace(comment, placeholder)
    
    # 単一行コメントを抽出 (# で始まる行)
    lines = code.split('\n')
    for i, line in enumerate(lines):
        # コメント部分を抽出
        comment_match = re.search(r'(#.*)$', line)
        if comment_match:
            comment = comment_match.group(1)
            placeholder = f"INLINE_COMMENT_{len(positions)}"
            positions.append((comment, placeholder))
            lines[i] = line.replace(comment, placeholder)
    
    # コメントを除去したコードを再構築
    code_without_comments = '\n'.join(lines)
    
    return positions, code_without_comments

def restore_comments(code: str, translated_comments: List[Tuple[str, str]]) -> str:
    """
    翻訳されたコメントをコードに戻す
    
    Args:
        code: コメントがプレースホルダーに置き換えられたコード
        translated_comments: 翻訳されたコメントとプレースホルダーのリスト
        
    Returns:
        コメントが復元されたコード
    """
    result = code
    for comment, placeholder in translated_comments:
        result = result.replace(placeholder, comment)
    return result

def translate_with_bedrock(text: str, prompt_instruction: str = "", region: str = "us-east-1") -> str:
    """
    Amazon Bedrockを使用してテキストを翻訳する
    
    Args:
        text: 翻訳するテキスト
        prompt_instruction: 翻訳時の追加指示
        region: AWSリージョン
        
    Returns:
        翻訳されたテキスト
    """
    bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name=region)
    
    # 翻訳プロンプトの作成
    prompt = f"""
あなたは翻訳の専門家です。以下のテキストを英語から日本語に翻訳してください。
{prompt_instruction}

翻訳するテキスト:
{text}

日本語訳:
"""
    
    # Claude モデルを使用
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    # リクエストボディの作成
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    })
    
    try:
        # モデル呼び出し
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=body
        )
        
        # レスポンスの解析
        response_body = json.loads(response.get('body').read())
        translated_text = response_body['content'][0]['text']
        
        # 余分な「日本語訳:」などの文字列を削除
        translated_text = re.sub(r'^(日本語訳:|翻訳:|Translation:)\s*', '', translated_text)
        
        return translated_text.strip()
    except Exception as e:
        print(f"翻訳エラー: {e}")
        # エラーの場合は元のテキストを返す
        return text

def translate_ipynb(input_file: str, output_file: str, region: str = "us-east-1") -> None:
    """
    ipynbファイルを翻訳する
    
    Args:
        input_file: 入力ipynbファイルのパス
        output_file: 出力ipynbファイルのパス
        region: AWSリージョン
    """
    # 翻訳指示
    translation_instruction = "半角英数字の前後には半角スペースを挿入する。コードやコマンド、変数名、関数名などの技術的な用語は翻訳せず、そのまま残してください。"
    
    try:
        # ipynbファイルを読み込む
        with open(input_file, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        # 各セルを処理
        for cell in notebook['cells']:
            cell_type = cell['cell_type']
            
            if cell_type == 'markdown':
                # マークダウンセルの場合は全文を翻訳
                source = ''.join(cell['source'])
                
                # 空のセルはスキップ
                if not source.strip():
                    continue
                
                print(f"マークダウンセルを翻訳中...")
                translated_source = translate_with_bedrock(source, translation_instruction, region)
                
                # 翻訳結果を行のリストに変換して戻す
                cell['source'] = [translated_source]
                
            elif cell_type == 'code':
                # コードセルの場合はコメントのみを翻訳
                source = ''.join(cell['source'])
                
                # 空のセルはスキップ
                if not source.strip():
                    continue
                
                # コメントを抽出
                comments, code_without_comments = extract_comments(source)
                
                if comments:
                    print(f"コードセル内のコメントを翻訳中...")
                    translated_comments = []
                    
                    for comment, placeholder in comments:
                        # コメント内容を翻訳
                        translated_comment = translate_with_bedrock(comment, translation_instruction, region)
                        translated_comments.append((translated_comment, placeholder))
                    
                    # 翻訳したコメントをコードに戻す
                    translated_source = restore_comments(code_without_comments, translated_comments)
                    
                    # 翻訳結果を行のリストに変換して戻す
                    cell['source'] = [translated_source]
        
        # 翻訳結果を保存
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, ensure_ascii=False, indent=1)
            
        print(f"翻訳完了: {output_file}")
        
    except Exception as e:
        print(f"エラー: {e}")

def main():
    parser = argparse.ArgumentParser(description='ipynbファイルを日本語に翻訳するスクリプト')
    parser.add_argument('input_file', help='入力ipynbファイルのパス')
    parser.add_argument('--output_file', help='出力ipynbファイルのパス（指定しない場合は入力ファイル名.ja.ipynbになります）')
    parser.add_argument('--region', default='us-east-1', help='AWSリージョン（デフォルト: us-east-1）')
    
    args = parser.parse_args()
    
    input_file = args.input_file
    region = args.region
    
    # 出力ファイル名が指定されていない場合は自動生成
    if args.output_file:
        output_file = args.output_file
    else:
        # 拡張子の前に.jaを追加
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}.ja{ext}"
    
    translate_ipynb(input_file, output_file, region)

if __name__ == "__main__":
    main()
