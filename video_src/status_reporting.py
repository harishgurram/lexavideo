
# -*- coding: utf-8 -*- 


from os import environ

import traceback, sys, os, StringIO, re
import logging, json

STARS_BREAK = '******************************************\n'
def log_call_stack_and_traceback(logging_function, *args, **kwds):
    '''Signal handler to log an exception or error condition for which we want further details 
    in the log files. 
    logging_function should be one of the logging.* (ie. logging.error) functions'''
    
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
        reason_for_logging = '%s: %s\n' % (exception_name, err)
        traceback_info =     STARS_BREAK + 'Traceback: ' + ''.join(traceback.format_exception(*excinfo)) + '\n'
               
    else: 
        reason_for_logging = 'No exception has occured\n'
        traceback_info = ''
       
    # we don't need to include the current 'log_call_stack_and_traceback' function in the stack trace. 
    start_frame = sys._getframe(1)
    
    call_stack_info_file = StringIO.StringIO()
    traceback.print_stack(start_frame, limit=stack_limit, file = call_stack_info_file)
    call_stack_info = STARS_BREAK + 'Call Stack: ' + call_stack_info_file.getvalue() + '\n'
    call_stack_info_file.close()

        
    # Check if request information is passed in
    if 'request' in kwds and kwds['request'] != None:
        try:
            request = kwds['request']
            repr_request = STARS_BREAK + \
                'Request that triggered traceback and call stack display:\n' +\
                '\tPath: ' + request.path + '\n' + \
                '\tURL: ' + request.url + '\n' + \
                '\tRemote address: ' + request.remote_addr + '\n' + \
                '\tQuery string: ' + request.query_string + '\n' + \
                '\tHeaders: ' + repr(request.headers) + '\n' + \
                '\tBody: ' + request.body + '\n'
        except:
            repr_request = STARS_BREAK + 'log_call_stack_and_traceback error: "request" not available.\n'
    else:
        repr_request = ''
        
    if 'extra_info' in kwds:
        extra_info += STARS_BREAK + '%s' % kwds['extra_info'] + '\n'

    end_of_error = STARS_BREAK + 'End of error feedback\n'
    msg = '\n' + reason_for_logging + extra_info + traceback_info +call_stack_info + repr_request + end_of_error + STARS_BREAK
    
    logging_function(msg)
        
        

