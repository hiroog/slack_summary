# vim:ts=4 sw=4 et:

import os
import sys
import datetime
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackMessageChecker:
    DATEFORMAT='%Y-%m-%d %H:%M:%S'
    def __init__(self, token):
        self.client = WebClient(token=token)
        self.user_map= {}

    def get_recent_messages(self, recent_days, specified_days, target_channels):
        if target_channels is None or target_channels == []:
            return []

        # 計算: 指定日と更新判定期間
        specified_date = datetime.datetime.now() - datetime.timedelta(days=specified_days)
        recent_date = datetime.datetime.now() - datetime.timedelta(days=recent_days)

        try:
            # チャンネル一覧を取得
            channels = self.client.conversations_list(types="public_channel").get("channels", [])

            # 指定されたチャンネルのみをフィルタリング
            if target_channels:
                channels = [channel for channel in channels if channel["name"] in target_channels]
            
            result = []

            for channel in channels:
                channel_id = channel["id"]
                channel_name = channel["name"]
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
                                #print( '   replies=', len(replies) )
                                result.append({"channel": (channel_name, channel_id), "messages": replies, 'date':latest_reply_date.strftime(self.DATEFORMAT)})
                                appended= True
                    else:
                        if message_date >= recent_date:
                            result.append({"channel": (channel_name, channel_id), "messages": [message], 'date':message_date.strftime(self.DATEFORMAT)})
                            appended= True

                    message_num+= 1
                    if appended:
                        print( '    %d/%d %s replies=%d  user=%d' % (message_num,message_count,message_date,reply_count,reply_users_count) )

            print( '* Total %d threads' % len(result), flush=True )
            return result

        except SlackApiError as e:
            print(f"Error fetching messages: {e.response['error']}")
            return []

    def get_user_name(self, user_id):
        if user_id in self.user_map:
            return  self.user_map[user_id]
        try:
            response= self.client.users_info(user=user_id)
            time.sleep( 0.5 )
            user= response.get('user',{})
            user_name= user.get('name', 'Unknown')
            real_name= user.get('real_name', user_name)
            display_name= user.get('profile',{}).get('display_name', real_name)
            name_text= '%s (%s)' % (display_name,user_name)
            self.user_map[user_id]= name_text
            return  name_text
        except SlackApiError as e:
            print(f"Error fetching messages: {e.response['error']}")
            return 'Unknown'

    def message_to_text(self, message):
        user= self.get_user_name( message.get('user', 'Unknown') )
        text= message.get('text', '')
        ts= datetime.datetime.fromtimestamp(float(message.get('ts', '0'))).strftime(self.DATEFORMAT)
        return  '%s  %s\n%s\n' % (user,ts,text)

    def threads_to_text(self, messages):
        replies_list= []
        for message in messages:
            replies_list.append(self.message_to_text(message))
        return  '\n'.join(replies_list)

    def dump_messages(self, messages):
        for item in messages:
            channel_name,channel_id= item.get('channel', None)
            threads_text= self.threads_to_text(item.get('messages',[]))
            print( '-------- # %s (%s)--------' % (channel_name,channel_id) )
            print( threads_text )


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
