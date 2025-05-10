# vim:ts=4 sw=4 et:

import os
import sys
import datetime
import time
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

#-------------------------------------------------------------------------------

def save_json(file_name, message_obj):
    # バックアップファイルを作成
    if os.path.exists(file_name):
        file_name_bak= file_name+'.bak'
        if os.path.exists(file_name_bak):
            os.remove(file_name_bak)
        os.rename(file_name,file_name_bak)
    # JSONファイルを保存
    with open(file_name, 'w', encoding='utf-8') as fo:
        fo.write(json.dumps(message_obj, indent=4, ensure_ascii=False))

def load_json(file_name):
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as fi:
            return  json.loads(fi.read())
    return  None

#-------------------------------------------------------------------------------

class ThreadInfo:
    # スレッド情報を格納するクラス
    def __init__(self):
        pass

#-------------------------------------------------------------------------------

class SlackMessageChecker:
    DATEFORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(self, token, cache=None):
        self.client = WebClient(token=token)
        self.user_map= {}
        self.channel_map= {}
        self.cache_updated= False
        self.cache_file= 'cache.json'
        if cache:
            self.cache_file= cache
        self.load_cache()

    def load_cache(self):
        cache= load_json(self.cache_file)
        if cache:
            print('load', self.cache_file, flush=True)
            self.user_map= cache.get('user', {})
            self.channel_map= cache.get('channel', {})

    def save_cache(self):
        if self.cache_updated:
            save_json(self.cache_file, {'user':self.user_map, 'channel':self.channel_map})
            self.cache_updated= False
            print('save', self.cache_file, flush=True)

    def get_all_channels(self):
        # チャンネル一覧を取得
        all_channels = []
        cursor = None
        while True:
            result = self.client.conversations_list(cursor=cursor, limit=800, types="public_channel")
            time.sleep( 1.0 )
            channels= result.get("channels", [])
            all_channels.extend( channels )
            cursor= result.get('response_metadata', {}).get('next_cursor', None)
            if cursor is None or cursor == '' or channels == []:
                break
        return  all_channels

    def get_channel_info(self, channel_name):
        # キャッシュからチャンネル情報を取得
        if channel_name in self.channel_map:
            return  self.channel_map[channel_name]
        # チャンネル情報を取得
        try:
            channels = self.get_all_channels()
            for channel in channels:
                channel_id= channel['id']
                name= channel['name']
                self.channel_map[name]= name,channel_id
            self.cache_updated= True
        except SlackApiError as e:
            print(f"Error fetching messages: {e.response['error']}")
            return  None
        if channel_name in self.channel_map:
            return  self.channel_map[channel_name]
        return  None

    def get_date_string(self, ts):
        if type(ts) is not float:
            ts= float(ts)
        if ts <= 0:
            return  ''
        date = datetime.datetime.fromtimestamp(ts)
        return  date.strftime(self.DATEFORMAT)

    def get_recent_messages(self, recent_days, specified_days, target_channels):
        if target_channels is None or target_channels == []:
            return []

        # 計算: 指定日と更新判定期間
        today_date = datetime.datetime.now()
        specified_date = datetime.datetime.now() - datetime.timedelta(days=specified_days)
        recent_date = datetime.datetime.now() - datetime.timedelta(days=recent_days)
        date_info= (today_date.strftime(self.DATEFORMAT), specified_date.strftime(self.DATEFORMAT), recent_date.strftime(self.DATEFORMAT))

        try:
            result = []

            for channel_name in target_channels:
                _,channel_id= self.get_channel_info(channel_name)
                print( '* channel=[%s] (%s)' % (channel_name, channel_id) )

                # チャンネル内のメッセージ履歴を取得
                has_more = True
                next_cursor = None
                all_messages = []  # 全メッセージを格納するリスト

                while has_more:
                    response = self.client.conversations_history(
                        channel=channel_id, 
                        oldest=specified_date.timestamp(),
                        cursor=next_cursor
                    )
                    messages = response.get("messages", [])
                    all_messages.extend(messages)  # 取得したメッセージをリストに追加
                    has_more = response.get("has_more", False)
                    next_cursor = response.get("response_metadata", {}).get("next_cursor")
                    time.sleep( 1.0 )

                message_count= len(all_messages)
                print( '  messages=', message_count )

                message_num= 0
                for message in all_messages:  # すべてのメッセージを処理
                    message_ts = float(message.get('ts', '0'))
                    message_date = datetime.datetime.fromtimestamp(message_ts)
                    reply_count = message.get('reply_count',0)
                    reply_users_count = message.get('reply_users_count',0)

                    appended= False

                    # 最近のメッセージまたはリプライがあるか判定
                    if reply_count >= 1:
                        if 'latest_reply' in message:
                            latest_reply_ts= float(message.get('latest_reply', '0'))
                            latest_reply_date = datetime.datetime.fromtimestamp(latest_reply_ts)
                            if latest_reply_date > recent_date:
                                # スレッドのリプライを確認
                                replies = self.client.conversations_replies(channel=channel_id, ts=message["ts"]).get("messages", [])
                                time.sleep( 1.0 )
                                result.append({"channel": (channel_name, channel_id), "messages": replies, "date":date_info})
                                appended= True
                    else:
                        if message_date >= recent_date:
                            result.append({"channel": (channel_name, channel_id), "messages": [message], "date":date_info})
                            appended= True

                    message_num+= 1
                    if appended:
                        print( '    %d/%d %s replies=%d  user=%d' % (message_num,message_count,message_date,reply_count,reply_users_count), flush=True )

            print( '* Total %d threads' % len(result), flush=True )
            return result

        except SlackApiError as e:
            print(f"Error fetching messages: {e.response['error']}")
            return []
        finally:
            self.save_cache()

    def get_user_info(self, user_id):
        '''ユーザー情報を取得する関数
        user_id: ユーザーID
        return: ユーザー情報
        '''
        # キャッシュからユーザー情報を取得
        if user_id in self.user_map:
            return  self.user_map[user_id]
        try:
            response= self.client.users_info(user=user_id)
            time.sleep( 0.5 )
            user= response.get('user',{})
            user_name= user.get('name', 'Unknown')
            real_name= user.get('real_name', '')
            display_name= user.get('profile',{}).get('display_name', '')
            if real_name == '':
                real_name= user_name
            if display_name == '':
                display_name= user_name
            user_info= {'user':user_name, 'display':display_name, 'real':real_name}
            self.user_map[user_id]= user_info
            self.cache_updated= True
            return  user_info
        except SlackApiError as e:
            print(f"Error fetching messages: {e.response['error']}")
            return {'name':'Unknown', 'display':'Unknown', 'real':'Unknown'}

    def userinfo_to_string(self, user_info):
        return '%s (%s)' % (user_info['real'],user_info['display'])

    def message_to_text(self, message):
        user_name = self.userinfo_to_string( self.get_user_info( message.get('user', 'Unknown') ) )
        text= message.get('text', '')
        date_str= self.get_date_string(message.get('ts', '0'))
        return  '%s  %s\n%s\n' % (user_name,date_str,text)

    def thread_to_text(self, messages):
        replies_list= []
        for message in messages:
            replies_list.append(self.message_to_text(message))
        return  '\n'.join(replies_list)

    def get_message_info(self, channel_info, date_info, messages):
        '''スレッド情報を取得する関数
        channel_info: チャンネルID
        messages: メッセージリスト
        return: スレッド情報
        '''
        info= ThreadInfo()

        # チャンネル情報を格納
        info.channel_name, info.channel_id= channel_info
        info.date_info= date_info

        # スレッド情報を取得
        info.thread_text= self.thread_to_text(messages)
        info.header_text= self.message_to_text(messages[0])
        first_message= messages[0]

        # スレッドのURLを取得
        thread_ts= first_message.get('thread_ts', None)
        if thread_ts is None:
            thread_ts= first_message.get('ts', None)
        response= self.client.chat_getPermalink(channel=info.channel_id, message_ts=thread_ts)
        info.thread_url= response.get('permalink','')

		# ポストしたユーザーの情報を取得
        info.post_user_info= self.get_user_info(first_message['user'])
        info.post_user_name= self.userinfo_to_string(info.post_user_info)
        info.post_date= self.get_date_string(first_message.get('ts', '0'))

		# リプライしたユーザーの情報を取得
        info.reply_date= self.get_date_string(first_message.get('latest_reply', '0'))
        info.reply_user_info= None
        info.reply_user_name= None
        reply_user_list= []
        for user_id in first_message.get('reply_users', []):
            info.reply_user_info= self.get_user_info(user_id)
            info.reply_user_name= self.userinfo_to_string(info.reply_user_info)
            reply_user_list.append(info.reply_user_name)
        info.reply_users_text= ' '.join(reply_user_list)
        info.reply_users= len(reply_user_list)
        info.reply_count= first_message.get('reply_count', 0)

        self.save_cache()
        return  info

    def get_channels(self, summary_list):
        # チャンネル情報を取得
        channel_map= {}
        for thread_info in summary_list:
            channel_name= thread_info.channel_name
            if channel_name not in channel_map:
                channel_map[channel_name]= 0
            channel_map[channel_name]+= 1
        channel_text= ''
        for channel_name in channel_map:
            channel_thread_count= channel_map[channel_name]
            if channel_text != '':
                channel_text+= ', '
            channel_text+= '#%s(%d)' % (channel_name, channel_thread_count)
        return  channel_text

    def post_message(self, channel_name, text, blocks=None, markdown_text= None, parent_response=None):
        # メッセージを送信
        try:
            thread_ts= None
            if parent_response:
                thread_ts= parent_response.get('ts', None)
            _,channel_id= self.get_channel_info(channel_name)
            response = self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks,
                markdown_text=markdown_text,
                thread_ts=thread_ts
            )
            time.sleep( 1.0 )
            return response
        except SlackApiError as e:
            print(f"Error sending message: {e.response['error']}")
            return None

    def dump_messages(self, messages):
        for item in messages:
            channel_name,channel_id= item.get('channel', None)
            threads_text= self.threads_to_text(item.get('messages',[]))
            print( '-------- # %s (%s)--------' % (channel_name,channel_id) )
            print( threads_text )

#-------------------------------------------------------------------------------

def usage():
    print("Usage: python SlackMessageChecker.py")
    print("SLACK_API_TOKEN must be set in the environment.")
    print("Options:")
    print("  -c, --channel <channel_name>  Specify the channel to check (default: None)")
    print("  -r, --recent <days>           Check messages from the last <days> days (default: 1)")
    print("  -d, --days <days>             Search data up to <days> ago (default: 30)")
    print("  -h, --help                    Show this help message and exit")
    sys.exit(0)


def main(argv):
    acount= len(argv)
    channel_list= []
    recent_days= 1
    specified_days= 30
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg == '-c' or arg == '--channel':
            if ai+1 < acount:
                ai+= 1
                channel_list.append(argv[ai])
        elif arg == '-r' or arg == '--recent':
            if ai+1 < acount:
                ai+= 1
                try:
                    recent_days= int(argv[ai])
                except ValueError:
                    print("Error: Invalid number of recent days specified.")
                    return 1
        elif arg == '-d' or arg == '--days':
            if ai+1 < acount:
                ai+= 1
                try:
                    specified_days= int(argv[ai])
                except ValueError:
                    print("Error: Invalid number of specified days specified.")
                    return 1
        elif arg == '-h' or arg == '--help':
            usage()
        else:
            print("Error: Unknown argument '%s'" % arg)
            usage()
            return 1
        ai+= 1

    # Slack API トークンを環境変数から取得
    SLACK_TOKEN = os.getenv("SLACK_API_TOKEN")
    if not SLACK_TOKEN:
        print("Error: Please set the SLACK_API_TOKEN environment variable.")
        return 1

    checker= SlackMessageChecker(SLACK_TOKEN)
    messages = checker.get_recent_messages(recent_days=recent_days, specified_days=specified_days, target_channels=channel_list)
    checker.dump_messages(messages)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
