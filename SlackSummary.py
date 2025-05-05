# 2025/05/05 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import os
import sys
import json

script_dir= os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.append( script_dir )
import OllamaAPI
import SlackMessageChecker

#------------------------------------------------------------------------------

# config.json
#
# {
#   "token": "SLACK-API-TOKEN",
#   "recent_days": 1,
#   "specified_days": 30,
#   "target_channels": [ "general" ],
#   "system_prompt": "要約して",
#   "ollama_host": "http://localhost:11434",
#   "model_name": "gemma3:12b",
# }

#------------------------------------------------------------------------------

class SlackSummary:
    def __init__(self, config_file):
        config= self.load_config(config_file)
        token= config.get('token', os.environ.get('SLACK_API_TOKEN'))
        if token is None:
            print("SLACK_API_TOKEN not found in environment variables.")
            return
        self.slack_checker = SlackMessageChecker.SlackMessageChecker(token=token)
        self.recent_days= config.get('recent_days', 1)
        self.specified_days= config.get('specified_days', 7)
        self.target_channels= config.get('target_channels', [])
        self.system_prompt= config.get('system_prompt', '')
        options= OllamaAPI.OllamaOptions(model_name= config['model_name'], ollama_host= config['ollama_host'])
        self.ollama_api = OllamaAPI.OllamaAPI(options)

    def load_config(self, config_file):
        # 設定ファイルを読み込む
        if not os.path.exists(config_file):
            print(f"Config file {config_file} does not exist.")
            return {}
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config

    def get_recent_messages(self):
        # チャンネル内のメッセージ履歴を取得
        messages = self.slack_checker.get_recent_messages(self.recent_days, self.specified_days, self.target_channels)
        if messages is None or len(messages) == 0:
            print("No messages found.")
            return None
        return messages

    def summarize_messages(self, messages):
        # メッセージを要約する
        for item in messages:
            channel_name,channel_id= item.get('channel', None)
            date= item.get('date', '')
            threads_text= self.slack_checker.threads_to_text(item.get('messages', []))
            summary,status_code = self.ollama_api.generate(self.system_prompt + '\n' + threads_text)
            if status_code != 200:
                print(f"Error generating summary: {status_code}")
                return None
            print('-------- # %s (%s) 更新 %s --------' % (channel_name, channel_id, date))
            print(summary)
            print('\n', flush=True)


#------------------------------------------------------------------------------

def usage():
    print("Usage: python SlackSummary.py --config <config_file>")
    sys.exit( 1 )


def main(argv):
    config_file= 'config.json'
    acount= len(argv)
    ai= 1
    while ai< acount:
        arg= argv[ai]
        if arg == '-c' or arg == '--config':
            if ai+1 < acount:
                ai+= 1
                config_file= argv[ai]
        else:
            usage()
        ai+= 1

    summary = SlackSummary(config_file)
    messages = summary.get_recent_messages()
    if messages is None:
        return 1
    summary.summarize_messages(messages)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))


