# 2025/05/05 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import os
import sys
import json

script_dir= os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.append( script_dir )
import OllamaAPI2
import SlackMessageChecker

#------------------------------------------------------------------------------

# config.json
#
# {
#   "token": "SLACK-API-TOKEN",
#   "recent_days": 1,
#   "specified_days": 30,
#   "target_channels": [ "general", "random" ],
#   "system_prompt": "要約して",
#   "Header_prompt": "数行にまとめて",
#   "provider": "ollama",
#   "ollama_host": "http://localhost:11434",
#   "model_name": "gemma3:12b",
#   "cahce_file": "cache.json",
#   "output_channel": "summary",
#   "output_markdown": "output.md",
#   "output_mention": ""
# }

#------------------------------------------------------------------------------

class SlackSummary:
    def __init__(self, config_file):
        config= self.load_config(config_file)
        token= config.get('token', os.environ.get('SLACK_API_TOKEN'))
        if token is None:
            print("SLACK_API_TOKEN not found in environment variables.")
            return
        self.slack_checker = SlackMessageChecker.SlackMessageChecker(token=token, cache=config.get('cache_file', 'cache.json'))
        self.recent_days= config.get('recent_days', 1)
        self.specified_days= config.get('specified_days', 7)
        self.target_channels= config.get('target_channels', [])
        self.system_prompt= config.get('system_prompt', '')
        self.header_prompt= config.get('header_prompt', '')
        self.output_channel= config.get('output_channel', None)
        self.output_markdown= config.get('output_markdown', None)
        self.output_mention= config.get('output_mention', '')
        options= OllamaAPI2.OllamaOptions(model_name=config['model_name'], base_url=config['ollama_host'], provider=config.get('provider', 'ollama'))
        self.ollama_api = OllamaAPI2.OllamaAPI(options)

    def load_config(self, config_file):
        # 設定ファイルを読み込む
        if not os.path.exists(config_file):
            print(f"Config file {config_file} does not exist.")
            return None
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config

    def get_recent_messages(self):
        # チャンネル内のメッセージ履歴を取得
        messages = self.slack_checker.get_recent_messages(self.recent_days, self.specified_days, self.target_channels)
        if messages is None or len(messages) == 0:
            print("No messages found.")
            return []
        return messages

    def summarize_messages(self, messages):
        # メッセージを要約する
        summary_list= []
        for index,item in enumerate(messages):
            channel_info= item.get('channel', None)
            date_info= item.get('date', None)
            reply_list= item.get('messages', [])
            thread_info = self.slack_checker.get_message_info(channel_info, date_info, reply_list)
            print('  %d/%d %s' % (index+1, len(messages), thread_info.reply_date), flush=True)
            summary,status_code = self.ollama_api.generate(self.system_prompt + '\n' + thread_info.thread_text)
            if status_code != 200:
                print(f"Error generating summary: {status_code}")
                return  None
            header,status_code = self.ollama_api.generate(self.header_prompt + '\n' + thread_info.header_text)
            if status_code != 200:
                print(f"Error generating summary: {status_code}")
                return  None
            thread_info.summary= summary
            thread_info.header= header
            summary_list.append(thread_info)
        return  summary_list

    def output_text(self, output_file, summary_list):
        # テキスト形式で出力
        with open(output_file, 'w', encoding='utf-8') as fo:
            for thread_info in summary_list:
                fo.write('======== #%s 投稿者 %s, 投稿日 %s ========\n' % (thread_info.channel_name, thread_info.post_user_name, thread_info.post_date))
                fo.write('URL: %s\n' % thread_info.thread_url)
                fo.write('\n')
                if thread_info.reply_count > 0:
                    fo.write('リプライ数 %d, 参加者: %s\n' % (thread_info.reply_count, thread_info.reply_users_text))
                    fo.write('最終リプライ %s, 日時 %s\n' % (thread_info.reply_user_name, thread_info.reply_date))
                    fo.write('\n')
                else:
                    fo.write('リプライなし\n')
                fo.write('\n')
                fo.write(thread_info.summary)
                fo.write('\n\n')

    def output_md(self, output_file, summary_list):
        # Markdown形式で出力
        with open(output_file, 'w', encoding='utf-8') as fo:
            if len(summary_list) != 0:
                date_info= summary_list[0].date_info
                fo.write('# SlackSummary %s\n' % date_info[0])
                fo.write('* 調査日時:  %s\n' % date_info[0])
                fo.write('* 新規判定:  %s  以降の投稿やリプライがある場合\n' % date_info[2])
                fo.write('* 検索範囲:  %s ～ %s\n' % (date_info[1][0:10],date_info[0][0:10]))
                fo.write('* 更新スレッド数:  %d\n' % len(summary_list))
            else:
                fo.write('# SlackSummary\n')
                fo.write('* 更新スレッドなし\n')
            for thread_info in summary_list:
                if thread_info.reply_count > 0:
                    fo.write('## #%s  最終更新 %s %s\n' % (thread_info.channel_name, thread_info.reply_user_name, thread_info.reply_date))
                else:
                    fo.write('## #%s  投稿者 %s %s\n' % (thread_info.channel_name, thread_info.post_user_name, thread_info.post_date))
                fo.write('\n')
                fo.write('%s\n' % thread_info.header)
                fo.write('\n')
                fo.write('%s\n' % thread_info.thread_url)

                if thread_info.reply_count > 0:
                    fo.write('\n')
                    fo.write('### 要約\n')
                    fo.write(thread_info.summary)
                    fo.write('\n\n')
                else:
                    fo.write('* リプライなし\n')
                    fo.write('\n')

                fo.write(    '|                    |          |\n')
                fo.write(    '|:------------------ |:-------- |\n')
                fo.write(    '| チャンネル         | #%s (%s) |\n' % (thread_info.channel_name, thread_info.channel_id) )
                fo.write(    '| 投稿者             | %s       |\n' % thread_info.post_user_name)
                fo.write(    '| 投稿日時           | %s       |\n' % thread_info.post_date)
                if thread_info.reply_count > 0:
                    fo.write('| リプライ数         | %d       |\n' % thread_info.reply_count)
                    fo.write('| 参加者             | %s       |\n' % thread_info.reply_users_text)
                    fo.write('| 最終リプライ投稿者 | %s       |\n' % thread_info.reply_user_name)
                    fo.write('| 最終リプライ日時   | %s       |\n' % thread_info.reply_date)

                fo.write('\n\n')
            fo.write( '\n' )

    def get_slack_text(self, thread_info ):
        text= ''
        if thread_info.reply_count > 0:
            text+=  ('🔴 *#%s  最終更新 %s %s*\n' % (thread_info.channel_name, thread_info.reply_user_name, thread_info.reply_date))
        else:
            text+=  ('🔵 *#%s  投稿者 %s %s*\n' % (thread_info.channel_name, thread_info.post_user_name, thread_info.post_date))
        text+=  ('\n')
        for line in thread_info.header.split('\n'):
            text+=  ('>%s\n' % line)
        text+=  ('\n')
        text+=  ('%s\n' % thread_info.thread_url)
        if thread_info.reply_count > 0:
            text+=  ('\n')
            text+=  ('*要約*\n\n')
            text+=  (thread_info.summary)
            text+=  ('\n')
        else:
            text+=  ('* リプライなし\n')

        text+=  ('\n')
        text+=  ('*情報*\n\n')
        text+=  ('* チャンネル: #%s (%s)\n' % (thread_info.channel_name, thread_info.channel_id) )
        text+=  ('* 投稿者: %s\n' % thread_info.post_user_name)
        text+=  ('* 投稿日時: %s\n' % thread_info.post_date)
        if thread_info.reply_count > 0:
            text+=  ('* リプライ数: %d\n' % thread_info.reply_count)
            text+=  ('* 参加者: %s\n' % thread_info.reply_users_text)
            text+=  ('* 最終リプライ投稿者: %s\n' % thread_info.reply_user_name)
            text+=  ('* 最終リプライ日時: %s\n' % thread_info.reply_date)

        text+=  ('\n　\n')
        return text

    def send_slack_thread(self, slack_channel, summary_list):
        # Slackにスレッドを送信
        text= self.output_mention + '\n'
        if len(summary_list) != 0:
            channels= self.slack_checker.get_channels(summary_list)
            date_info= summary_list[0].date_info
            text= ('*SlackSummary %s*\n' % date_info[0])
            #text+= ('%s 以降の更新\n' % date_info[2])
            #text+= ('検索期間:  %s ～ %s\n' % (date_info[1][0:10],date_info[0][0:10]))
            text+= ('%s\n' % channels)
            text+= ('スレッド合計:  %d\n' % len(summary_list))
        else:
            text= ('*SlackSummary*\n')
            text+= ('更新スレッドはありません\n')
            return  None
        blocks= [
            {
                'type': 'section',
                'expand': True,
                'text': {
                    'type': 'mrkdwn',
                    'text': text
                }
            },
        ]
        response= self.slack_checker.post_message(slack_channel, text=text, blocks=blocks)
        return response

    def output_slack_v1(self, slack_channel, summary_list):
        response= self.send_slack_thread(slack_channel, summary_list)
        if response is None:
            return

        for thread_info in summary_list:
            header_text= ''
            if thread_info.reply_count > 0:
                title_text=  ('🔴 更新 %s %s\n' % (thread_info.reply_user_name, thread_info.reply_date))
                header_text= '*%s %s*\n' % (thread_info.post_user_name, thread_info.post_date)
            else:
                title_text=  ('🔵 新規 %s %s\n' % (thread_info.post_user_name, thread_info.post_date))
            header_text+= thread_info.header
            blocks= [
                {
                    'type': 'header',
                    'text': {
                        'type': 'plain_text',
                        'text': title_text,
                        'emoji': True
                    }
                },
                {
                    'type': 'divider'
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': '<%s|元スレッドのリンク(%d)>   #%s' % (thread_info.thread_url, thread_info.reply_count, thread_info.channel_name)
                    }
                },
                {
                    'type': 'section',
                    'expand': True,
                    'text': {
                        'type': 'mrkdwn',
                        'text': header_text
                    }
                },
            ]
 
            if thread_info.reply_count > 0:
                blocks.extend([
                    {
                        'type': 'divider'
                    }
                ])

            response= self.slack_checker.post_message(slack_channel, text=title_text+header_text, blocks=blocks, parent_response=response)

            if thread_info.reply_count > 0:
                response= self.slack_checker.post_message(slack_channel, text=None, blocks=None, markdown_text=thread_info.summary, parent_response=response)


    def output_slack_v2(self, slack_channel, summary_list):
        response= self.send_slack_thread(slack_channel, summary_list)
        if response is None:
            return

        for thread_info in summary_list:
            text= ''
            if thread_info.reply_count > 0:
                text+=  ('# 🔴 更新 %s %s\n' % (thread_info.reply_user_name, thread_info.reply_date))
            else:
                text+=  ('# 🔵 新規 %s %s\n' % (thread_info.post_user_name, thread_info.post_date))
            text+= '\n----\n'

            text+= '[元スレッドのリンク(%d)](%s)   #%s\n' % (thread_info.reply_count, thread_info.thread_url, thread_info.channel_name)

            if thread_info.reply_count > 0:
                text+= '**%s %s**\n' % (thread_info.post_user_name, thread_info.post_date)
            text+= thread_info.header

            if thread_info.reply_count > 0:
                text+= '\n----\n'
                text+= thread_info.summary

            response= self.slack_checker.post_message(slack_channel, text=None, blocks=None, markdown_text=text, parent_response=response)

    def output_all(self, summary_list):
        # 全ての出力を行う
        if self.output_markdown is not None:
            self.output_md(self.output_markdown, summary_list)
        if self.output_channel is not None:
            self.output_slack_v1(self.output_channel, summary_list)

#------------------------------------------------------------------------------

def usage():
    print("Usage: python SlackSummary.py --config <config_file>")
    sys.exit( 1 )


def main(argv):
    config_file= 'config.json'
    save_messages= False
    load_messages= False
    acount= len(argv)
    ai= 1
    while ai< acount:
        arg= argv[ai]
        if arg == '-c' or arg == '--config':
            if ai+1 < acount:
                ai+= 1
                config_file= argv[ai]
        elif arg == '--save':
            save_messages= True
        elif arg == '--load':
            load_messages= True
        else:
            usage()
        ai+= 1

    summary = SlackSummary(config_file)
    if load_messages:
        object_list= SlackMessageChecker.SlackAPI.load_json('summary.json')
        summary_list= []
        for object in object_list:
            thread_info= SlackMessageChecker.ThreadInfo()
            thread_info.__dict__.update(object)
            summary_list.append(thread_info)
    else:
        messages = summary.get_recent_messages()
        if messages is None:
            return 0
        summary_list= summary.summarize_messages(messages)
        if save_messages:
            object_list= []
            for thread_info in summary_list:
                object_list.append(thread_info.__dict__)
            SlackMessageChecker.SlackAPI.save_json('summary.json',object_list)

    summary.output_all(summary_list)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))


