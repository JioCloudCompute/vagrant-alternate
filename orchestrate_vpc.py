#!/usr/bin/env python

import sys, os, signal
import subprocess
import re
import ssh
import multiprocessing as mp
import process_provision

# DNS lock
dns_lock = mp.Lock()

assert os.environ.get("consul_discovery_token") is not None, "Please set consul_discovery_token"
assert os.environ.get("env") is not None, "Please set `env`"


cloud_vm_name = "haproxy1"
bootstrap_vm_name = "vpc-cfg1"
external_vm_name = "httpproxy1"
base_ip = "192.168.100."

machine_list = [ 
    {
        "name" : "haproxy1",
        "ram": 2048,
        "vcpus": 2
    },
    {
        "name" : "vpc-ctrl1",
        "ram": 4096,
        "vcpus": 2
    },
    {
        "name" : "vpc-ctrl2",
        "ram": 4096,
        "vcpus": 2
    },
    {
        "name" : "vpc-cfg1",
        "ram": 4096,
        "vcpus": 2
    },
    {
        "name" : "keystone1",
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
        "name" : "vpc-cp1",
        "ram": 4096,
        "vcpus": 4
    },
    {
        "name" : "vpc-monitor1",
        "ram": 4096,
        "vcpus": 4
    },
    ]

def get_index(name):
    return [i for i, v in enumerate(machine_list) if v["name"] == name][0]

def get_guestip(name):
    i = get_index(name)
    redir_port = 9900 + i
    mc = machine_list[i]
    logfile = "/tmp/puppet-ipaddress-%d" % redir_port
    ssh.execute(redir_port, "ifconfig eth1", logfile)
    f = open(logfile, "r")
    for line in f:
        if "inet addr:" in line:
            m = re.search(r"inet addr:(.*?) B", line)
            if m:
                print "ip:",m.group(1)
                f.close()
                return m.group(1)
    return None

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

def add_dhcphostfile_record(name,ip,mac):
    dns_lock.acquire()
    f = open("/tmp/puppet.hostfile", "r")
    lines = list()
    for line in f:
        if len(line.strip()) == 0:
            continue
        if name not in line:
            tokens = line.split(",")
            lines.append(line)
    f.close()
    f = open("/tmp/puppet.hostfile", "w")
    for v in lines:
        f.write("%s\n" % v)
    f.write("%s,%s,%s\n" % (mac,ip,name) )
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

# Copies the puppet files and execute the puppet
def PROVISION_VM(name):
    logfile = "./logs/%s.log" % name
    i = get_index(name)
    redir_port = 9900 + i
    mc = machine_list[i]

    # Set hostname
    ssh.execute(redir_port, "hostname %s" % name, logfile)

    # ifconfig eth1
    ssh.execute(redir_port, "dhclient eth1", logfile)

    env_vars = dict()
    env_vars.update({'hostname': name})
    env_vars.update({'env': os.environ.get("env")})
    env_vars.update({"consul_discovery_token": os.environ.get("consul_discovery_token")})

    # Process the provision.cmd file
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
    ssh.execute(redir_port, "chmod a+x /tmp/%s.provision.sh" % name, logfile)
    ssh.execute (redir_port, "bash -l /tmp/%s.provision.sh" % name, logfile)

# Spawn qemu process as per machine_list
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

def UP_ALL(ignore_arg):
    # Program the /tmp/puppet.hosts
    for mc in machine_list:
        i = get_index(mc["name"])
        ip = base_ip + str(i + 11)
        if mc["name"] == cloud_vm_name:
            fix_cloud_dns(ip)
        if mc["name"] == bootstrap_vm_name:
            add_dns_record("%s.service.consuldiscovery.linux2go.dk" % os.environ.get("consul_discovery_token"), ip)
        add_dns_record(mc["name"], ip)
        mac_address = "00:11:22:33:44:" + str(55 + i)
        add_dhcphostfile_record(mc["name"], ip, mac_address)

def PROVISION_ALL(ignore_arg):
    tl = list()
        
    for mc in machine_list:
        if mc['name'] == external_vm_name:
            continue
        t = mp.Process(target=PROVISION_VM,args=(mc["name"],))
        tl.append(t)
        t.start()

    for t in tl:
        t.join()

cmds = {
    "create": CREATE_VM,
    "provision": PROVISION_VM,
    "upall": UP_ALL,
    "call": CREATE_ALL,
    "pall": PROVISION_ALL,
}

if __name__ == "__main__":
    cmds[sys.argv[1]](sys.argv[2])
