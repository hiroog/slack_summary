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
            setattr( self, key, params[key] )

class OllamaOptions(OptionBase):
    def __init__( self, **args ):
        super().__init__()
        self.base_url= os.environ.get('OLLAMA_HOST', 'http://localhost:11434' )
        self.provider= 'ollama'
        self.system_role= 'system' # or developer
        self.timeout= 600
        self.model_name= 'gemma3:12b'
        self.apply_params( args )
        self.remove_think= True

def image_to_base64( image_data ):
    encoded_byte= base64.b64encode( image_data )
    return  encoded_byte.decode('utf-8')

def load_image( image_path ):
    with open( image_path, 'rb' ) as fi:
        return  fi.read()
    return  None

#------------------------------------------------------------------------------

class OllamaAPI:
    def __init__( self, options ):
        self.options= options

    #--------------------------------------------------------------------------

    def chat1_oai( self, text, system= None, image_data= None ):
        params= {
            'model': self.options.model_name,
            'messages': [
                {
                    "role": "user",
                    "content": text,
                }
            ],
        }
        if image_data:
            b64_image= image_to_base64( image_data )
            params['messages'][0]['content']= {
                {
                    "type": "input_text",
                    "text": text,
                },
                {
                    "type": "input_image",
                    "image": f"data:mage/jpeg:base64,{b64_image}",
                }
            }
        if system:
            params['messages'].insert( 0, { "role": self.options.system_role, "content": system } )
        api_url= self.options.base_url + '/v1/chat/completions'
        data= json.dumps( params )
        headers= {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % os.environ.get('OPENAI_API_KEY', 'lm-studio'),
        }
        try:
            result= requests.post( api_url, headers=headers, data=data, timeout=self.options.timeout )
        except Exception as e:
            return  '',408
        if result.status_code == 200:
            data= result.json()
            response= data['choices'][0]['message']['content']
            if self.options.remove_think:
                response= self.remove_think_tag( response )
            return  response,result.status_code
        else:
            print( 'Error: %d' % result.status_code )
        return  '',result.status_code

    #--------------------------------------------------------------------------

    def generate_oai( self, text, system= None, image_data= None ):
        params= {
            'model': self.options.model_name,
            'input': text,
        }
        if image_data:
            b64_image= image_to_base64( image_data )
            params['input']= {
                {
                    "type": "input_text",
                    "text": text,
                },
                {
                    "type": "input_image",
                    "image": f"data:mage/jpeg:base64,{b64_image}",
                }
            }
        api_url= self.options.base_url + '/v1/response'
        data= json.dumps( params )
        headers= {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % os.environ.get('OPENAI_API_KEY', 'lm-studio'),
        }
        try:
            result= requests.post( api_url, headers=headers, data=data, timeout=self.options.timeout )
        except Exception as e:
            return  '',408
        if result.status_code == 200:
            data= result.json()
            response= data['output'][0]['content'][0]['text']
            if self.options.remove_think:
                response= self.remove_think_tag( response )
            return  response,result.status_code
        else:
            print( 'Error: %d' % result.status_code )
        return  '',result.status_code

    #--------------------------------------------------------------------------

    def generate_ollama( self, text, system= None, image_data= None ):
        params= {
            'model': self.options.model_name,
            'prompt': text,
            'stream': False,
        }
        if system:
            params['system']= system
        if image_data:
            params['images']= [ image_to_base64( image_data ) ]
        api_url= self.options.base_url + '/api/generate'
        data= json.dumps( params )
        try:
            result= requests.post( api_url, headers={ 'Content-Type': 'application/json' }, data=data, timeout=self.options.timeout )
        except Exception as e:
            return  '',408
        if result.status_code == 200:
            data= result.json()
            response= data['response']
            if self.options.remove_think:
                response= self.remove_think_tag( response )
            return  response,result.status_code
        else:
            print( 'Error: %d' % result.status_code )
        return  '',result.status_code

    #--------------------------------------------------------------------------

    def generate( self, text, system= None, image_data= None ):
        if self.options.provider == 'ollama':
            return  self.generate_ollama( text, system, image_data )
        elif self.options.provider == 'lmstudio':
            return  self.chat1_oai( text, system, image_data )
        elif self.options.provider == 'openai':
            return  self.generate_oai( text, system, image_data )
        return  '',400

    #--------------------------------------------------------------------------

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
            elif bmode == 2:
                if line != '':
                    result_list.append( line )
                    bmode= 3
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
    print( '  --host <base_url>' )
    print( '  --model <model_name>' )
    print( '  --provider <provider>        # ollama, openai, lmstudio' )
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
                ai= options.set_str( ai, argv, 'base_url' )
            elif arg == '--provider':
                ai= options.set_str( ai, argv, 'provider' )
            else:
                print( 'Error: unknown option %s' % arg )
                usage()
        else:
            text_list.append( arg )
        ai+= 1

    api= OllamaAPI( options )
    if text_list != []:
        image_data= None
        if options.image_file:
            image_data= load_image( options.image_file )
            if image_data is None:
                print( 'Error: image file not found' )
                return  1
        input_text= ' '.join( text_list )
        print( 'prompt:', input_text )
        print( 'output:', api.generate( input_text, image_data )[0] )
    else:
        usage()
    return  0


if __name__=='__main__':
    sys.exit( main( sys.argv ) )


