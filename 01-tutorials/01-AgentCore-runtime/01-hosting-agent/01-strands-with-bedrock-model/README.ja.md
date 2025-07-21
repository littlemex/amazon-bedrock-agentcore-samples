# Amazon Bedrock AgentCore ランタイムでのAmazon Bedrockモデルを使用したStrands Agentsのホスティング

## 概要

このチュートリアルでは、Amazon Bedrock AgentCore ランタイムを使用して既存のエージェントをホストする方法を学びます。

ここではAmazon Bedrockモデルを使用したStrands Agentsの例に焦点を当てます。Amazon Bedrockモデルを使用したLangGraphについては[こちら](../02-langgraph-with-bedrock-model)を、OpenAIモデルを使用したStrands Agentsについては[こちら](../03-strands-with-openai-model)をご覧ください。


### チュートリアルの詳細

| 情報               | 詳細                                                                           |
|:------------------|:------------------------------------------------------------------------------|
| チュートリアルタイプ   | 会話型                                                                         |
| エージェントタイプ     | 単一                                                                          |
| エージェントフレームワーク | Strands Agents                                                               |
| LLMモデル          | Anthropic Claude Sonnet 4                                                     |
| チュートリアルコンポーネント | AgentCore ランタイムでのエージェントのホスティング。Strands AgentとAmazon Bedrockモデルの使用 |
| チュートリアル分野     | 分野横断的                                                                      |
| 例の複雑さ          | 簡単                                                                           |
| 使用するSDK         | Amazon BedrockAgentCore Python SDKとboto3                                      |

### チュートリアルのアーキテクチャ

このチュートリアルでは、既存のエージェントをAgentCoreランタイムにデプロイする方法について説明します。

デモンストレーションの目的で、Amazon Bedrockモデルを使用したStrands Agentを使用します。

この例では、`get_weather`と`get_time`という2つのツールを持つ非常にシンプルなエージェントを使用します。

<div style="text-align:left">
    <img src="images/architecture_runtime.png" width="100%"/>
</div>

### チュートリアルの主な特徴

* Amazon Bedrock AgentCore ランタイムでのエージェントのホスティング
* Amazon Bedrockモデルの使用
* Strands Agentsの使用
