
import vidsetup
import os, datetime, subprocess
from build_support import gen_yaml

def run_grunt(grunt_arg, subprocess_function):

    os.chdir("client")
    pargs = ['grunt', grunt_arg]
    process = subprocess_function(pargs,  stderr=subprocess.STDOUT)    
    os.chdir("..")
    print "Switched directory back to: %s" % os.getcwd()
    
    
def run_grunt_jobs():
    
    if vidsetup.RUN_GRUNT:
        if vidsetup.DEBUG_BUILD:
            # If we are accessing the non-compressed static files, we are probably developing and therefore want to see updates
            run_grunt('serve', subprocess.Popen)    
        else: 
            # only run the grunt build scripts if we are currently accessing the compressed static files (ie. client/dist instead of client/app). 
            # Otherwise, we are directly accessing/debugging the source static files, and minimizing would serve no purpose.
            run_grunt('build', subprocess.call)

        
def customize_files(version_id):
    
    print "**********************************************************************"
    print "Generating custom files: %s " % version_id
    print "Current path): %s" % os.getcwd()   
    print "%s" % datetime.datetime.now()
    print "**********************************************************************"
    
    gen_yaml.generate_app_yaml(version_id)
    run_grunt_jobs()

        