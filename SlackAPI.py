# 2025 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import os
import sys
import time
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# channels:history
# channels:read
# chat:write
# reactions:write
# groups:history
# groups:read
# groups:write
# users:read
# users.profile:read
# files:write

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
    CACHE_VERSION=4

    def __init__( self, token, cache=None, public_only=False ):
        self.client = WebClient( token=token )
        self.user_map= {}
        self.channel_map= {}
        self.cache_file= 'slack_cache.json'
        if cache:
            self.cache_file= cache
        self.public_only= public_only
        self.load_cache()

    def load_cache( self ):
        self.cache_updated= 0
        cache= load_json( self.cache_file )
        if cache:
            print( 'load', self.cache_file, flush=True )
            ver= cache.get( 'version', 0 )
            if ver != self.CACHE_VERSION:
                cache= {}
            self.user_map= cache.get( 'user', {} )
            self.channel_map= cache.get( 'channel', {} )

    def save_cache( self ):
        if (self.cache_updated & 0xff) != 0:
            save_json( self.cache_file, {'user':self.user_map, 'channel':self.channel_map, 'version':self.CACHE_VERSION} )
            self.cache_updated= (self.cache_updated << 8) & 0xff00
            print( 'save', self.cache_file, flush=True )

    #--------------------------------------------------------------------------

    def get_all_channels( self ):
        all_channels= []
        cursor= None
        while True:
            types= 'public_channel'
            if not self.public_only:
                types+= ',private_channel'
            result= self.client.conversations_list( cursor=cursor, limit=800, types=types )
            time.sleep( 2.0 )
            channels= result.get( 'channels', [] )
            all_channels.extend( channels )
            cursor= result.get( 'response_metadata', {} ).get( 'next_cursor', None )
            if cursor is None or cursor == '' or channels == []:
                break
        return  all_channels

    def refresh_channels( self ):
        if (self.cache_updated & 0x101) != 0:
            return
        try:
            channels= self.get_all_channels()
            for channel in channels:
                channel_id= channel['id']
                name= channel['name']
                self.channel_map[name]= channel_id
            self.cache_updated|= 1
        except SlackApiError as e:
            print( 'Error fetching channels: %s' % str(e.response['error']) )

    def get_channel_id( self, channel_name ):
        if channel_name.startswith( '#' ):
            channel_name= channel_name[1:]
        if channel_name in self.channel_map:
            return  self.channel_map[channel_name]
        self.refresh_channels()
        return  self.channel_map.get( channel_name, None )

    def get_channel_name_1( self, channel_id ):
        for name in self.channel_map:
            if channel_id == self.channel_map[name]:
                return  name
        return  None

    def get_channel_name( self, channel_id ):
        channel_name= self.get_channel_name_1( channel_id )
        if channel_name:
            return  channel_name
        self.refresh_channels()
        return  self.get_channel_name_1( channel_id )

    #--------------------------------------------------------------------------

    def get_all_users( self ):
        all_user_map= {}
        cursor= None
        while True:
            time.sleep( 3.0 )
            result= self.client.users_list( cursor= cursor )
            time.sleep( 3.0 )
            users= result.get( 'members', [] )
            for user in users:
                user_id= user.get( 'id', 'Unknown' )
                user_name= user.get( 'name', 'Unknown' )
                real_name= user.get( 'real_name', '' )
                display_name= user.get( 'profile', {} ).get( 'display_name', '' )
                user_info= {
                    'user':     user_name,
                    'display':  display_name,
                    'real':     real_name,
                    'id':       user_id,
                    'bot':      user.get('is_bot',False),
                }
                all_user_map[user_id]= user_info
            cursor= result.get( 'response_metadata', {} ).get( 'next_cursor', None )
            if cursor is None or cursor == '' or users == []:
                break
        return  all_user_map

    def refresh_users( self ):
        if (self.cache_updated & 0x202) != 0:
            return
        try:
            self.user_map= self.get_all_users()
            self.cache_updated|= 2
        except SlackApiError as e:
            print( 'Error fetching user lists: %s' % str(e.response['error']) )

    def get_user_info( self, user_id ):
        if user_id in self.user_map:
            return  self.user_map[user_id]
        self.refresh_users()
        if user_id in self.user_map:
            return  self.user_map[user_id]
        return  { 'user':'Unknown', 'display':'Unknown', 'real':'Unknown', 'id':'Unknown', 'bot':False }

    def get_user_id_1( self, user_name ):
        for user_id in self.user_map:
            user_info= self.user_map[user_id]
            if user_name == user_info['user'] or user_name == user_info['display'] or user_name == user_info['real']:
                return  user_id
        return  None

    def get_user_id( self, user_name ):
        if user_name.startswith( '@' ):
            user_name= user_name[1:]
        user_id= self.get_user_id_1( user_name )
        if user_id:
            return  user_id
        self.refresh_users()
        return  self.get_user_id_1( user_name )

    #--------------------------------------------------------------------------

    def post_message( self, channel_name, text, blocks=None, markdown_text= None, thread_ts=None, parent_response=None ):
        if (thread_ts is None) and (parent_response is not None):
            thread_ts= parent_response.get('ts', None)
        try:
            channel_id= self.get_channel_id( channel_name )
            response= self.client.chat_postMessage( channel=channel_id, text=text, blocks=blocks, markdown_text=markdown_text, thread_ts=thread_ts )
            time.sleep( 1.0 )
            return  response
        except SlackApiError as e:
            print( 'Error sending message: %s' % str(e.response['error']) )
            return  None
        self.save_cache()

#-------------------------------------------------------------------------------

def usage():
    print( 'SlackAPI v1.10' )
    print( 'Usage: python SlackAPI.py' )
    print( 'options:' )
    print( '  --channel <channel>' )
    print( '  --user <user_name>' )
    sys.exit( 0 )


def main( argv ):
    channel= None
    user= None
    acount= len( argv )
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg == '--channel':
            if ai+1 < acount:
                ai+= 1
                channel= argv[ai]
        elif arg == '--user':
            if ai+1 < acount:
                ai+= 1
                user= argv[ai]
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

    if channel or user:
        api= SlackAPI( SLACK_TOKEN )

    if channel:
        channel_id= api.get_channel_id( channel )
        channel_name= api.get_channel_name( channel_id )
        print( 'channel_name=', channel_name, channel )
        print( 'channel_id=', channel_id )
        api.post_message( channel, 'Test Message' )

    if user:
        user_id= api.get_user_id( user )
        user_info= api.get_user_info( user_id )
        print( user_info )
        print( 'user_name=', user_info['user'] )
        print( 'display_name=', user_info['display'] )
        print( 'real_name=', user_info['real'] )
        print( 'user_id=', user_info['id'] )
        print( 'is_bot=', user_info['bot'] )

    if channel or user:
        api.save_cache()

    return  0


if __name__ == '__main__':
    sys.exit( main( sys.argv ) )

