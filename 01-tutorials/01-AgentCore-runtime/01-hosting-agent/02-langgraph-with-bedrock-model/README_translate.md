# ipynb翻訳スクリプト

このスクリプトは、Jupyter Notebook（.ipynb）ファイルを英語から日本語に翻訳するためのツールです。Amazon Bedrock の Claude モデルを使用して翻訳を行います。

## 特徴

- マークダウンセルの全文を日本語に翻訳
- コードセル内のコメントのみを日本語に翻訳（コード自体は変更しない）
- 翻訳時に半角英数字の前後に半角スペースを挿入
- 技術用語（変数名、関数名など）は翻訳せずそのまま保持

## 前提条件

- Python 3.6以上
- boto3
- AWS認証情報の設定（Amazon Bedrockへのアクセス権限が必要）
- Amazon Bedrockの利用権限（Claude-3-Sonnetモデルへのアクセス）

## インストール

必要なライブラリをインストールします：

```bash
pip install boto3
```

## 使い方

基本的な使い方：

```bash
python translate_ipynb.py <入力ファイルパス>
```

出力ファイル名を指定する場合：

```bash
python translate_ipynb.py <入力ファイルパス> --output_file <出力ファイルパス>
```

AWSリージョンを指定する場合：

```bash
python translate_ipynb.py <入力ファイルパス> --region <リージョン名>
```

### 例

```bash
# 基本的な使い方（出力は input_file.ja.ipynb になります）
python translate_ipynb.py runtime_with_langgraph_and_bedrock_models.ipynb

# 出力ファイル名を指定
python translate_ipynb.py runtime_with_langgraph_and_bedrock_models.ipynb --output_file runtime_with_langgraph_and_bedrock_models_jp.ipynb

# リージョンを指定（Amazon Bedrockが利用可能なリージョンを指定）
python translate_ipynb.py runtime_with_langgraph_and_bedrock_models.ipynb --region us-west-2
```

## 注意事項

- 大きなノートブックの翻訳には時間がかかる場合があります
- Amazon Bedrockの使用には料金が発生する可能性があります
- AWS認証情報が正しく設定されていることを確認してください
- 翻訳の品質はモデルに依存します
