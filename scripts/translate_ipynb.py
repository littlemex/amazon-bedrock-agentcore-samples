#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import os
import argparse
import boto3
from typing import List, Tuple

def clean_translation_output(text: str) -> str:
    """翻訳出力から余分な文字列を除去"""
    # 翻訳プロンプトの残骸を除去
    patterns_to_remove = [
        r'^(日本語訳:|翻訳:|Translation:|Japanese:|訳:)\s*',
        r'日本語訳:\s*$',
        r'以下.*翻訳.*です[：:]\s*',
        r'翻訳結果[：:]\s*',
    ]
    
    result = text.strip()
    for pattern in patterns_to_remove:
        result = re.sub(pattern, '', result, flags=re.MULTILINE)
    
    return result.strip()

def is_already_japanese(text: str) -> bool:
    """テキストが既に日本語かどうかを判定"""
    # ひらがな、カタカナ、漢字の割合をチェック
    japanese_chars = len(re.findall(r'[ひ-ゖヲ-ヺ一-龯]', text))
    total_chars = len(re.sub(r'\s', '', text))
    
    if total_chars == 0:
        return False
    
    japanese_ratio = japanese_chars / total_chars
    return japanese_ratio > 0.3  # 30%以上が日本語文字なら日本語と判定

def extract_code_strings(code: str) -> Tuple[List[Tuple[str, str]], str]:
    """コードから翻訳対象の文字列のみを抽出"""
    positions = []
    result = code
    
    # より厳密な文字列パターン
    patterns = [
        (r'("""[^"]*?""")', 'DOCSTRING'),  # docstring
        (r"('''[^']*?''')", 'DOCSTRING'),  # docstring
        (r'("[^"\n]{6,}?")', 'STRING'),    # 6文字以上の文字列
        (r"('[^'\n]{6,}?')", 'STRING'),    # 6文字以上の文字列
    ]
    
    for pattern, string_type in patterns:
        matches = list(re.finditer(pattern, result, re.DOTALL))
        for match in reversed(matches):
            full_match = match.group(1)
            
            # 文字列の内容を取得
            if full_match.startswith(('"""', "'''")):
                inner_content = full_match[3:-3]
            else:
                inner_content = full_match[1:-1]
            
            # 翻訳すべき文字列かどうかを判定
            if should_translate_string(inner_content):
                placeholder = f"TRANSLATE_{string_type}_{len(positions)}"
                positions.append((full_match, placeholder))
                result = result[:match.start()] + placeholder + result[match.end():]
    
    return positions, result

def should_translate_string(content: str) -> bool:
    """文字列が翻訳対象かどうかを判定"""
    content = content.strip()
    
    # 除外条件
    if (len(content) < 6 or  # 短すぎる
        is_already_japanese(content) or  # 既に日本語
        re.match(r'^[a-zA-Z0-9_.-]+$', content) or  # 識別子
        content.startswith(('http', 'www', 'ftp', '/', './', '../')) or  # URL/パス
        re.match(r'^[A-Z_][A-Z0-9_]*$', content) or  # 定数
        content.startswith('%') or  # フォーマット文字列
        content.count('{') > 2 or  # 複雑なフォーマット
        not re.search(r'[a-zA-Z]', content)):  # 英字を含まない
        return False
    
    return True

def translate_with_bedrock(text: str, region: str = "us-east-1") -> str:
    """Bedrockで翻訳（シンプルなプロンプト）"""
    if is_already_japanese(text):
        return text
    
    bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name=region)
    
    # 最小限のプロンプト
    prompt = f"""Translate the following English text to natural Japanese. Only output the translation, no explanations.
    コードブロックについてはコメント部分以外は決して変更してはなりません。例外として、自然言語でなんらかのプロンプトや指示を与える箇所のみ日本語に翻訳してください。

English: {text}
Japanese:"""
    
    model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}]
    })
    
    try:
        response = bedrock_runtime.invoke_model(modelId=model_id, body=body)
        response_body = json.loads(response.get('body').read())
        translated = response_body['content'][0]['text']
        
        # 出力をクリーンアップ
        cleaned = clean_translation_output(translated)
        return cleaned if cleaned else text
        
    except Exception as e:
        print(f"翻訳エラー: {e}")
        return text

def translate_ipynb(input_file: str, output_file: str, region: str = "us-east-1") -> None:
    """ipynbファイルを翻訳"""
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        for i, cell in enumerate(notebook['cells']):
            cell_type = cell['cell_type']
            source = ''.join(cell['source']) if cell['source'] else ""
            
            if not source.strip():
                continue
            
            print(f"セル {i+1} ({cell_type}) を処理中...")
            
            if cell_type == 'markdown':
                # マークダウンセルは既に日本語でなければ翻訳
                if not is_already_japanese(source):
                    # コードブロックを保護
                    protected_source = source
                    code_blocks = []
                    
                    def protect_code(match):
                        code_blocks.append(match.group(0))
                        return f"PROTECTED_CODE_{len(code_blocks)-1}"
                    
                    protected_source = re.sub(r'```.*?```', protect_code, protected_source, flags=re.DOTALL)
                    
                    # 翻訳
                    translated = translate_with_bedrock(protected_source, region)
                    
                    # コードブロックを復元
                    for j, code_block in enumerate(code_blocks):
                        translated = translated.replace(f"PROTECTED_CODE_{j}", code_block)
                    
                    cell['source'] = [translated]
                    print(f"  → マークダウンを翻訳しました")
                else:
                    print(f"  → 既に日本語のためスキップ")
                    
            elif cell_type == 'code':
                # コードセルは文字列リテラルのみ翻訳
                translatable_strings, code_without_strings = extract_code_strings(source)
                
                if translatable_strings:
                    print(f"  → {len(translatable_strings)}個の文字列を翻訳中...")
                    translated_strings = []
                    
                    for string_content, placeholder in translatable_strings:
                        # 文字列の種類に応じて処理
                        if string_content.startswith('"""'):
                            inner = string_content[3:-3]
                            translated_inner = translate_with_bedrock(inner, region)
                            translated_strings.append(('"""' + translated_inner + '"""', placeholder))
                        elif string_content.startswith("'''"):
                            inner = string_content[3:-3]
                            translated_inner = translate_with_bedrock(inner, region)
                            translated_strings.append(("'''" + translated_inner + "'''", placeholder))
                        elif string_content.startswith('"'):
                            inner = string_content[1:-1]
                            translated_inner = translate_with_bedrock(inner, region)
                            translated_strings.append(('"' + translated_inner + '"', placeholder))
                        elif string_content.startswith("'"):
                            inner = string_content[1:-1]
                            translated_inner = translate_with_bedrock(inner, region)
                            translated_strings.append(("'" + translated_inner + "'", placeholder))
                    
                    # 翻訳された文字列を復元
                    final_code = code_without_strings
                    for translated_string, placeholder in translated_strings:
                        final_code = final_code.replace(placeholder, translated_string)
                    
                    cell['source'] = [final_code]
                    print(f"  → コード内文字列を翻訳しました")
                else:
                    print(f"  → 翻訳対象の文字列なし")
        
        # 結果を保存
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, ensure_ascii=False, indent=1)
        
        print(f"\n✅ 翻訳完了: {output_file}")
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='ipynbファイル翻訳ツール（最終版）')
    parser.add_argument('input_file', help='入力ipynbファイル')
    parser.add_argument('--output_file', help='出力ipynbファイル')
    parser.add_argument('--region', default='us-east-1', help='AWSリージョン')
    
    args = parser.parse_args()
    
    if args.output_file:
        output_file = args.output_file
    else:
        base, ext = os.path.splitext(args.input_file)
        output_file = f"{base}.ja{ext}"
    
    translate_ipynb(args.input_file, output_file, args.region)

if __name__ == "__main__":
    main()