# 2025 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import os
import sys
import time
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

#-------------------------------------------------------------------------------

def save_json( file_name, message_obj ):
    if os.path.exists( file_name ):
        file_name_bak= file_name+'.bak'
        if os.path.exists( file_name_bak ):
            os.remove( file_name_bak )
        os.rename( file_name, file_name_bak )
    with open( file_name, 'w', encoding='utf-8' ) as fo:
        fo.write( json.dumps( message_obj, indent=4, ensure_ascii=False ) )

def load_json( file_name ):
    if os.path.exists( file_name ):
        with open( file_name, 'r', encoding='utf-8' ) as fi:
            return  json.loads( fi.read() )
    return  None

#-------------------------------------------------------------------------------

class SlackAPI:
    def __init__( self, token, cache=None ):
        self.client = WebClient( token=token )
        self.user_map= {}
        self.channel_map= {}
        self.cache_file= 'cache.json'
        if cache:
            self.cache_file= cache
        self.load_cache()

    def load_cache( self ):
        self.cache_updated= False
        cache= load_json( self.cache_file )
        if cache:
            print( 'load', self.cache_file, flush=True )
            self.user_map= cache.get( 'user', {} )
            self.channel_map= cache.get( 'channel', {} )

    def save_cache( self ):
        if self.cache_updated:
            save_json( self.cache_file, {'user':self.user_map, 'channel':self.channel_map} )
            self.cache_updated= False
            print( 'save', self.cache_file, flush=True )

    def get_all_channels( self ):
        all_channels= []
        cursor= None
        while True:
            result= self.client.conversations_list( cursor=cursor, limit=800, types="public_channel" )
            time.sleep( 1.0 )
            channels= result.get( "channels", [] )
            all_channels.extend( channels )
            cursor= result.get( 'response_metadata', {} ).get( 'next_cursor', None )
            if cursor is None or cursor == '' or channels == []:
                break
        return  all_channels

    def get_channel_id( self, channel_name ):
        if channel_name in self.channel_map:
            return  self.channel_map[channel_name]
        try:
            channels= self.get_all_channels()
            for channel in channels:
                channel_id= channel['id']
                name= channel['name']
                self.channel_map[name]= channel_id
            self.cache_updated= True
        except SlackApiError as e:
            print( 'Error fetching channels: %s' % str(e.response['error']) )
            return  None
        return  self.channel_map.get( channel_name, None )

    def get_user_info( self, user_id ):
        if user_id in self.user_map:
            return  self.user_map[user_id]
        try:
            response= self.client.users_info( user=user_id )
            time.sleep( 0.5 )
            user= response.get( 'user', {} )
            user_name= user.get( 'name', 'Unknown' )
            real_name= user.get( 'real_name', '' )
            display_name= user.get( 'profile', {} ).get( 'display_name', '' )
            if real_name == '':
                real_name= user_name
            if display_name == '':
                display_name= user_name
            user_info= { 'user':user_name, 'display':display_name, 'real':real_name }
            self.user_map[user_id]= user_info
            self.cache_updated= True
            return  user_info
        except SlackApiError as e:
            print( 'Error fetching user: %s' % str(e.response['error']) )
            return  {'name':'Unknown', 'display':'Unknown', 'real':'Unknown'}

    def post_message( self, channel_name, text, blocks=None, markdown_text= None, thread_ts=None ):
        try:
            channel_id= self.get_channel_id( channel_name )
            response= self.client.chat_postMessage( channel=channel_id, text=text, blocks=blocks, markdown_text=markdown_text, thread_ts=thread_ts )
            time.sleep( 1.0 )
            return  response
        except SlackApiError as e:
            print( 'Error sending message: %s' % str(e.response['error']) )
            return  None

#-------------------------------------------------------------------------------

def usage():
    print( 'Usage: python SlackAPI.py' )
    print( 'SLACK_API_TOKEN must be set in the environment.' )
    print( 'options:' )
    print( '  --channel <channel>' )
    sys.exit( 0 )


def main( argv ):
    channel= None
    acount= len( argv )
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg == '--channel':
            if ai+1 < acount:
                ai+= 1
                channel= argv[ai]
        elif arg == '-h' or arg == '--help':
            usage()
        else:
            print( 'Error: Unknown argument %s' % arg )
            usage()
            return  1
        ai+= 1

    SLACK_TOKEN= os.environ.get( 'SLACK_API_TOKEN', None )
    if not SLACK_TOKEN:
        print( 'Error: Please set the SLACK_API_TOKEN environment variable.' )
        return  1

    if channel:
        api= SlackAPI( SLACK_TOKEN )
        api.post_message( channel, 'Test Message' )
    return  0


if __name__ == '__main__':
    sys.exit( main( sys.argv ) )

