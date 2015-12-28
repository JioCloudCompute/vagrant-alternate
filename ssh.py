#!/usr/bin/env python

import subprocess
import sys, os

KEYFILE = "./puppet.key"
SSH_STRING = "ssh -q -o StrictHostKeyChecking=no "
SSH_HOST = "vagrant@localhost"
RSYNC_PATH = "sudo mkdir -p %s && sudo rsync"

def execute(port,cmd,logfile):
    print ("Executing command on remote: %s" % cmd)
    f = open(logfile, "a")
    cmd = SSH_STRING + "-i %s -p %d " % (KEYFILE,port) + SSH_HOST + """ sudo %s """ % cmd
    ssh = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in ssh.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        f.write(line)
        f.flush()
    f.close()

def sync_folder(redir_port, spath, rpath, logfile):
    print ("Tranfering to remote: %s -> %s" % (spath, rpath))
    cmd = """ rsync --rsync-path='%s' -e '%s -i %s -p %d ' -avz -r %s %s:%s 2>&1 >>%s """ % (RSYNC_PATH, SSH_STRING, KEYFILE, redir_port, spath, SSH_HOST, rpath,logfile)
    cmd = cmd % rpath
    return os.system(cmd)
 
