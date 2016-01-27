#!/usr/bin/env python

import subprocess
import sys, os

KEYFILE = "./vm.pem"
SSH_STRING = "ssh -q -o StrictHostKeyChecking=no "
SSH_HOST = "vagrant@localhost"
RSYNC_PATH = "sudo mkdir -p %s && sudo rsync"

def check_connection_state(port):
    cmd = SSH_STRING + "-i %s -p %d " % (KEYFILE,port) + SSH_HOST + """ sudo %s """ % "ls"
    ret = os.system(cmd)
    if ret != 0:
        return False
    return True

def execute(port,cmd,logfile):
    print ("Executing command on remote: %s" % cmd)
    f = open(logfile, "a")
    cmd = SSH_STRING + "-i %s -p %d " % (KEYFILE,port) + SSH_HOST + """ sudo %s """ % cmd
    ssh = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in ssh.stdout:
        try:
            line = line.decode("utf-8").replace(u"\u2022", "*")
            sys.stdout.write("[%s]: " % logfile + line)
            sys.stdout.flush()
            f.write(line)
            f.flush()
        except UnicodeEncodeError as ude:
            print ("Warning: UnicodeEncodeError: %s" % ude)
            pass
    f.close()

def sync_folder(redir_port, spath, rpath, logfile):
    print ("[%s] Tranfering to remote: %s -> %s" % (logfile, spath, rpath))
    cmd = """ rsync --rsync-path='%s' -e '%s -i %s -p %d ' -avz -r %s %s:%s 2>&1 >>%s """ % (RSYNC_PATH, SSH_STRING, KEYFILE, redir_port, spath, SSH_HOST, rpath,logfile)
    cmd = cmd % rpath
    return os.system(cmd)
 
