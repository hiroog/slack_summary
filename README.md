# Slack 要約ツール


最近更新があったスレッドを抽出して要約するツールです。


## 使い方

config.sample.json を参考に config.json を作成します。
slack のトークンやチャンネルを指定します。
ollama のホストとモデル名も指定します。


```json
{
  "token": "xoxb-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx",
  "target_channels": [ "general", "random" ],
  "ollama_host": "http://localhost:11434",
  "model_name": "gemma3:12b",
  ～
}
```

SlackSummary.py のコマンドラインに config.json を指定して実行します。

```
python SlackSummary.py --config config.json
```

