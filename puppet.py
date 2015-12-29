#!/usr/bin/env python

import sys, os, signal
import subprocess
import re
import ssh
import multiprocessing as mp
import process_provision


# DNS lock
dns_lock = mp.Lock()

machine_list = [ 
    {
        "name" : "bootstrap1",
        "ram": 1024,
        "vcpus": 1
    },
    {
        "name" : "haproxy1",
        "ram": 2048,
        "vcpus": 2
    },
    {
        "name" : "oc1",
        "ram": 4096,
        "vcpus": 2
    },
    {
        "name" : "ocdb1",
        "ram": 4096,
        "vcpus": 2
    },
    {
        "name" : "ct1",
        "ram": 4096,
        "vcpus": 2
    },
    {
        "name" : "stmonleader1",
        "ram": 4096,
        "vcpus": 2
    },
    {
        "name" : "stmon1",
        "ram": 4096,
        "vcpus": 2,
        "disk": 80,
    },
    {
        "name" : "stmon2",
        "ram": 4096,
        "vcpus": 2,
        "disk": 80,
    },
    {
        "name" : "st1",
        "ram": 4096,
        "vcpus": 2,
        "disk": 80,
    },
    {
        "name" : "cp1",
        "ram": 4096,
        "vcpus": 4
    },
    {
        "name" : "cp2",
        "ram": 4096,
        "vcpus": 4
    },
    {
        "name" : "gcp1",
        "ram": 4096,
        "vcpus": 2
    }]

def get_index(name):
    return [i for i, v in enumerate(machine_list) if v["name"] == name][0]

def get_guestip(mac):
    while True:
        f = open("/var/run/qemu-dnsmasq-br0.leases", "r")
        for line in f:
            if re.search(r'%s'%mac, line):
                tokens = line.split(" ")
                return tokens[2]
        f.close()

def add_dns_record(name,ip):
    dns_lock.acquire()
    f = open("/tmp/puppet.hosts", "r")
    lines = dict()
    for line in f:
        if len(line.strip()) == 0:
            continue
        if name not in line:
            tokens = line.split(" ")
            lines.update({tokens[1]:tokens[0]})
    f.close()
    f = open("/tmp/puppet.hosts", "w")
    for k,v in lines.iteritems():
        f.write("%s %s\n" % (v,k) )
    f.write("%s %s\n" % (ip,name) )
    f.close()
    # Get the pid of dnsmasq
    pid = os.popen('pidof dnsmasq').read()
    # Send signal to dnsmasq to clear its cache
    os.system("sudo kill -SIGHUP %s" % pid)
    dns_lock.release()

def fix_cloud_dns(ip):
    cloud_list = [ "identity.jiocloud.com", "volume.jiocloud.com", "network.jiocloud.com",
   "compute.jiocloud.com", "image.jiocloud.com", "object.jiocloud.com" ]

    for cl in cloud_list:
        add_dns_record(cl, ip)

def PROVISION_VM(name):
    logfile = "./logs/%s.log" % name
    i = get_index(name)
    redir_port = 9900 + i

    mac_address = "00:11:22:33:44:" + str(55 + i)
    ssh.execute(redir_port, "dhclient eth1",logfile)
    print ("Fixing dns server")
    add_dns_record(name, get_guestip(mac_address))
    if name == "bootstrap1":
        print ("Fixing dns server for consul service")
        add_dns_record("%s.service.consuldiscovery.linux2go.dk" % os.environ.get("consul_discovery_token"), get_guestip(mac_address))

    if name == "haproxy1":
        fix_cloud_dns(get_guestip(mac_address))

    # For separate data and control plane
    if name == 'cp1' or name == 'cp2' or name == 'gcp1':
        ssh.execute(redir_port, "dhclient eth2", logfile)

    env_vars = dict()
    env_vars.update({'hostname': "%s.domain.name" % name})
    fsync_list,lines = process_provision.process("./provision.cmd", env_vars)
    for k,v in fsync_list.iteritems():
        ssh.sync_folder(redir_port, v, k, logfile)
        
    # Write the lines to remote tmp file
    f = open("/tmp/%s.provision.sh" % name, "w")
    for line in lines:
        f.write(line)
    f.close()
    # Transfer the file to remote
    ssh.sync_folder(redir_port, "/tmp/%s.provision.sh" % name, "/tmp/", logfile)
    # Set execute permission and run
    ssh.execute(redir_port, "sudo 'hostname %s'" % name, logfile)
    ssh.execute(redir_port, "chmod a+x /tmp/%s.provision.sh" % name, logfile)
    ssh.execute (redir_port, "/tmp/%s.provision.sh" % name, logfile)

def CREATE_VM(name):
    i = get_index(name)
    disk_size = 40
    mc = machine_list[i]
    print "======================================"
    print "[Starting machine] ==> " + mc["name"]
    mac_address = "00:11:22:33:44:" + str(55 + i)
    mac_address1 = "00:11:22:33:55:" + str(55 + i)
    print "[Mac address]      ==> " + mac_address
    redir_port = 9900 + i
    serial_port = 9700 + i
    print "[Redir Port]       ==> %d" % redir_port
    print "[Vcpus]            ==> %d" % mc["vcpus"]
    print "[RAM]              ==> %d" % mc["ram"]
    if "disk" in mc:
    	print "[DISK]             ==> %dG" % mc["disk"]
        disk_size = mc["disk"]
    else:
	print "[DISK]             ==> 40G"
    print "======================================"

    if len(sys.argv) > 3 and sys.argv[3] == "new":
        create_disk = "yes"
    else:
        create_disk = "no"
    cmd = """ %s/qemu.sh "%s" "%s" "%s" "%d" "%s" "%s" "%d" "%d" %d "%s" """ % \
		(os.path.dirname(os.path.realpath(__file__)), mc["name"],mc["ram"],mc["vcpus"],
            redir_port,mac_address,mac_address1,
            i,serial_port,disk_size,create_disk)
    print cmd
    os.system(cmd)

def CREATE_ALL(ignore_arg):
    tl = list()
    for mc in machine_list:
        t = mp.Process(target=CREATE_VM,args=(mc["name"],))
        t.start()

    for t in tl:
        t.join()

def PROVISION_ALL(ignore_arg):
    tl = list()
    for mc in machine_list:
        if mc["name"] == "bootstrap1":
	   continue
        t = mp.Process(target=PROVISION_VM,args=(mc["name"],))
        tl.append(t)
        t.start()

    for t in tl:
        t.join()

def DNS(ignore_arg):
    f = open('/tmp/puppet-hosts', 'w')
    for i,mc in enumerate(machine_list):
        mac_address = "00:11:22:33:44:" + str(55 + i)
        ip_addr = "192.168.100." + str(3 + i)
        hstr = "%s,%s,%s,infinite\n" %(mac_address,ip_addr,mc["name"])
        f.write(hstr)
    f.close()

cmds = {
    "create": CREATE_VM,
    "provision": PROVISION_VM,
    "dns": DNS,
    "call": CREATE_ALL,
    "pall": PROVISION_ALL,
}

cmds[sys.argv[1]](sys.argv[2])
