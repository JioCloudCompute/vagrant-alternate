#!/usr/bin/env python

import re, os, sys

def process(filename, env_vars):
    fsync_list = dict()
    lines = list()
    f = open(filename, 'r')
    for line in f:
        if len(line.strip()) == 0:
            continue
        if re.search(r'^SCP:', line.strip()):
            # is a folder/file sync command
            tokens = line.strip().split(":")
            fsync_list.update({tokens[2]:tokens[1]})
        else:
            # bash shell statements
            tokens = re.findall(r'#ENV\[.*?\]', line.strip())
            for tok in tokens:
                ev = re.search(r'#ENV\[(.*?)\]', tok).group(1)
                if os.environ.get(ev) is None:
                    print ("Error: %s is not defined in host environment" % ev)
                    sys.exit(1)
                line = line.replace(tok, os.environ.get(ev))

            # Puppet environment vars
            tokens = re.findall(r'#PUPPET_ENV\[.*?\]', line.strip())
            for tok in tokens:
                ev = re.search(r'#PUPPET_ENV\[(.*?)\]', tok).group(1)
                if ev not in env_vars:
                    print ("Error: %s is not defined in puppet environment" % ev)
                    sys.exit(1)
                line = line.replace(tok, env_vars[ev])

            lines.append(line)
    return (fsync_list, lines)

