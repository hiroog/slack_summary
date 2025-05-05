# 2025/3/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import re
import json
import requests
import base64

#------------------------------------------------------------------------------

class OptionBase:
    def __init__( self ):
        pass

    def set_str( self, ai, argv, name ):
        acount= len(argv)
        if ai+1 < acount:
            ai+= 1
            setattr( self, name, argv[ai] )
        return  ai

    def set_int( self, ai, argv, name ):
        acount= len(argv)
        if ai+1 < acount:
            ai+= 1
            setattr( self, name, int(argv[ai]) )
        return  ai

    def apply_params( self, params ):
        for key in params:
            getattr( self, key )
            setattr( self, key, params[key] )

class OllamaOptions(OptionBase):
    def __init__( self, **args ):
        super().__init__()
        self.image_file= None
        self.ollama_host= 'http://127.0.0.1:11434'
        self.model_name= 'gemma3:12b'
        self.apply_params( args )


def image_to_base64( image_path ):
    with open( image_path, 'rb' ) as fi:
        encoded_byte= base64.b64encode( fi.read() )
        return  encoded_byte.decode('utf-8')
    return  None


class OllamaAPI:
    def __init__( self, options ):
        self.options= options
        self.model_name= 'gemma3:12b'
        self.base_url= 'http://127.0.0.1:11434'
        if 'OLLAMA_HOST' in os.environ:
            self.base_url= os.environ['OLLAMA_HOST']
        self.set_host( options.ollama_host )
        self.set_model( options.model_name )

    def set_host( self, ollama_host ):
        if ollama_host:
            self.base_url= ollama_host

    def set_model( self, model_name ):
        if model_name:
            self.model_name= model_name

    def generate( self, text, image_file= None, remove_think=True ):
        params= {
            'model': self.model_name,
            'prompt': text,
            'stream': False,
        }
        if image_file:
            image_data= image_to_base64( image_file )
            params['images']= [ image_data ]
        api_url= self.base_url + '/api/generate'
        data= json.dumps( params )
        try:
            result= requests.post( api_url, headers={ 'Content-Type': 'application/json' }, data=data, timeout=600 )
        except Exception as e:
            return  '',408
        if result.status_code == 200:
            data= result.json()
            response= data['response']
            if remove_think:
                response= self.remove_think_tag( response )
            return  response,result.status_code
        else:
            print( 'Error: %d' % result.status_code )
        return  '',result.status_code

    def remove_think_tag( self, response ):
        begin_pat= re.compile( r'^(.*)\<think\>' )
        end_pat= re.compile( r'\<\/think\>(.*)$' )
        bmode= 0
        result_list= []
        for line in response.split( '\n' ):
            if bmode == 0:
                pat= begin_pat.search( line )
                if pat:
                    spat= pat.group(1)
                    if spat != '':
                        result_list.append( spat )
                    bmode= 1
                else:
                    result_list.append( line )
            elif bmode == 1:
                pat= end_pat.search( line )
                if pat:
                    spat= pat.group(1)
                    if spat != '':
                        result_list.append( spat )
                    bmode= 2
            else:
                result_list.append( line )
        if bmode == 0:
            return  response
        return  '\n'.join( result_list )


#------------------------------------------------------------------------------

def usage():
    print( 'OllamaAPI v1.20' )
    print( 'usage: OllamaAPI [<options>] [<message..>]' )
    print( 'options:' )
    print( '  --host <ollama_host>' )
    print( '  --model <model_name>' )
    print( '  --image <image_file>' )
    sys.exit( 0 )


def main( argv ):
    acount= len(argv)
    options= OllamaOptions( image_file= None )
    text_list= []
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '--image':
                ai= options.set_str( ai, argv, 'image_file' )
            elif arg == '--model':
                ai= options.set_str( ai, argv, 'model_name' )
            elif arg == '--host':
                ai= options.set_str( ai, argv, 'ollama_host' )
            else:
                usage()
        else:
            text_list.append( arg )
        ai+= 1

    api= OllamaAPI( options )
    if text_list != []:
        print( api.generate( ' '.join( text_list ), options.image_file ) )
    else:
        usage()
    return  0


if __name__=='__main__':
    sys.exit( main( sys.argv ) )


