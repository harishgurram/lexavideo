# -*- coding: utf-8 -*- 

################################################################################
# LexaLink Copyright information - do not remove this copyright notice
# Copyright (C) 2012 
#
# Lexalink - a free social network and dating website platform for the Google App Engine. 
#
# Original author: Alexander Marquardt
# Documentation and additional information: http://www.LexaLink.com
# Git source code repository: https://github.com/alexander-marquardt/lexalink 
#
# Please consider contributing your enhancements and modifications to the LexaLink community, 
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################


from os import environ

import traceback, sys, os, StringIO, re
import logging, json

STARS_BREAK = '******************************************\n'
def log_call_stack_and_traceback(logging_function, *args, **kwds):
    """Signal handler to log an exception or error condition for which we want further details 
    in the log files. 
    logging_function should be one of the logging.* (ie. logging.error) functions"""
    
    # get the exception -- however, we also use this function for general error logging
    # and therefore exc_info might return (None, None, None). 
    excinfo = sys.exc_info()
    cls, err = excinfo[:2]
    
    extra_info = ''
    
    if 'stack_limit' in kwds:
        stack_limit = kwds['stack_limit']
    else: 
        stack_limit = 5
    
    if err:
        exception_name = cls.__name__
        reason_for_logging = 'Exception: %s: %s\n' % (exception_name, err)
        traceback_info =     STARS_BREAK + 'Traceback: ' + ''.join(traceback.format_exception(*excinfo)) + '\n'
               
    else: 
        reason_for_logging = 'Status: No exception has occured\n'
        traceback_info = ''
       
    # we don't need to include the current "log_call_stack_and_traceback" function in the stack trace. 
    start_frame = sys._getframe(1)
    
    call_stack_info_file = StringIO.StringIO()
    traceback.print_stack(start_frame, limit=stack_limit, file = call_stack_info_file)
    call_stack_info = STARS_BREAK + 'Call Stack: ' + call_stack_info_file.getvalue() + '\n'
    call_stack_info_file.close()

        
    # Check if request information is passed in
    if 'request' in kwds:
        try:
            repr_request = STARS_BREAK + "Request: " + repr(kwds['request']) + '\n'
        except:
            repr_request = STARS_BREAK + 'log_call_stack_and_traceback error: Request repr() not available.\n'
    else:
        repr_request = ''
        
    if 'extra_info' in kwds:
        extra_info += STARS_BREAK + "Message: %s" % kwds['extra_info'] + '\n'

        
    
    msg = '\n' + reason_for_logging + extra_info + traceback_info +call_stack_info + repr_request
    
    logging_function(msg)
        
        
