#!/usr/bin/env python

import sys, os, signal
import subprocess
import re
import ssh
import multiprocessing as mp
import process_provision
import json
import pexpect

dns_lock = mp.Lock()
assert os.environ.get("consul_discovery_token") is not None, "Please set consul_discovery_token"
assert os.environ.get("env") is not None, "Please set `env`"

BASE_IMG = "/home/ubuntu/puppet_temp/source/disk.img"

with open("site.rc") as json_data_file:
    config_obj = json.load(json_data_file)

def network_str(name,i):
    pnet = [v for j, v in enumerate(config_obj["networks"]) if ("dns" in v and v["dns"] == 1) ][0]
    maddr = pnet["mac-base"].strip() + ":" + str(55 + i)
    port = 9900 + i

    if pnet is None:
        print ("site.rc error! no primary network defined (one with dns:true)")
        os.exit(1)

    _str = " -netdev user,id=NAME,hostname=NAME,hostfwd=tcp::%d-:22 -device e1000,netdev=NAME" % port
    n_str  = _str.replace("NAME", name)
    _str = " -netdev type=tap,id=TAP,ifname=TAP,script=./qemu-ifup-%s -device e1000,netdev=TAP,mac=%s" % (pnet["name"], maddr)
    n_str  += _str.replace("TAP", "%s-tap%d" % (pnet["name"],i))

    for nw in config_obj["networks"]:
        maddr = nw["mac-base"].strip() + ":" + str(55 + i)
        if nw["name"] != pnet["name"]:
            _str =" -netdev type=tap,id=TAP,ifname=TAP,script=./qemu-ifup-%s -device e1000,netdev=TAP,mac=%s" % (nw["name"],maddr) 
            n_str += _str.replace("TAP", "%s-tap%s" % (nw["name"],i))
    return n_str

def qemu_command(name,i):
    mc = config_obj["nodes"][i]
    sport = 9700 + i
    ram = mc["ram"]
    vcpus = mc["vcpus"]
    name = mc["name"]

    # Qemu command
    cmd = """
sudo qemu-system-x86_64 -enable-kvm -name %s -cpu kvm64 --enable-kvm \
 -m %d -smp %d -drive file=./images/%s.img -serial tcp::%d,server,nowait -vnc :%d \
 -monitor unix:/tmp/%s.monitor.sock,server,nowait %s 2>&1 >./logs/%s.log &
""" % (name, ram, vcpus, name, sport, i, name, network_str(name,i),name)

    # Qemu img command
    qemu_img_cmd = "qemu-img create -f qcow2 -b %s ./images/%s.img 40G 2>&1 > ./logs/%s.log" % (BASE_IMG, name, name)
    if os.system(qemu_img_cmd) != 0:
        print ("Failed: %s" % qemu_img_cmd)
        sys.exit(1)
    if os.system(cmd) != 0:
        print ("Failed: %s" % cmd)
        sys.exit(1)

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
    f.write("%s,%s,%s,30d\n" % (mac,ip,name) )
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

def wait_for_vm(i):
    port = 9700 + i
    vm = pexpect.spawn('telnet localhost %d' % port)
    while True:
        vm.sendline("\n")
        try:
            if vm.expect('vagrant-ubuntu-trusty-64 login:', timeout=60) == 0:
                break
        except EOF:
            vm.sendline("\n")
        except TIMEOUT:
            vm.sendline("\n")
    vm.close()

# Copies the puppet files and execute the puppet
def provision_vm(name,i):
    logfile = "./logs/%s.log" % name
    redir_port = 9900 + i

    print ("Waiting for %s to boot" % name)
    wait_for_vm(i)

    # Set hostname
    ssh.execute(redir_port, "hostname %s" % name, logfile)

    # ifconfig eth1 (primary network must be eth1 always in qemu command)
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
def create_vm(name,i):
#    disk_size = 40
#    mc = config_obj["nodes"][i]
#    print "======================================"
#    print "[Starting machine] ==> " + mc["name"]
#    mac_address = "00:11:22:33:44:" + str(55 + i)
#    mac_address1 = "00:11:22:33:55:" + str(55 + i)
#    print "[Mac address]      ==> " + mac_address
#    redir_port = 9900 + i
#    serial_port = 9700 + i
#    print "[Redir Port]       ==> %d" % redir_port
#    print "[Vcpus]            ==> %d" % mc["vcpus"]
#    print "[RAM]              ==> %d" % mc["ram"]
#    if "disk" in mc:
#    	print "[DISK]             ==> %dG" % mc["disk"]
#        disk_size = mc["disk"]
#    else:
#	print "[DISK]             ==> 40G"
#    print "======================================"
#
#    if len(sys.argv) > 3 and sys.argv[3] == "new":
#        create_disk = "yes"
#    else:
#        create_disk = "no"
#    cmd = """ %s/qemu.sh "%s" "%s" "%s" "%d" "%s" "%s" "%d" "%d" %d "%s" """ % \
#		(os.path.dirname(os.path.realpath(__file__)), mc["name"],mc["ram"],mc["vcpus"],
#            redir_port,mac_address,mac_address1,
#            i,serial_port,disk_size,create_disk)
#    print cmd
#    os.system(cmd)
    qemu_command(name,i)

if sys.argv[1] == 'init':
    # Get the primary network (then one which DNS true)
    primary_network = [v for i, v in enumerate(config_obj["networks"]) if ("dns" in v and v["dns"] == 1) ][0]
    base_ip = ".".join(primary_network["ip"].split(".")[:3])

    # Create network
    for nw in config_obj["networks"]:
        if "dns" in nw and nw["dns"]:
            os.system("./network_dns.sh %s %s %s" % (nw["name"],nw["ip"],nw["netmask"]))
        else:
            os.system("./network.sh %s %s %s" % (nw["name"],nw["ip"],nw["netmask"]))

    # Process the nodes for DNS and IP arrangements
    for i,mc in enumerate(config_obj["nodes"]):
        maddr = primary_network["mac-base"] + str(55 + i)
        ip = base_ip + "." + str(11 + i)

        # If the VM is consul bootstrap server
        if "bootstrap_vm" in mc and mc["bootstrap_vm"]:
            add_dns_record("%s.service.consuldiscovery.linux2go.dk" % \
                os.environ.get("consul_discovery_token"), ip)

        # If the VM is jiocloud VM
        if "cloud_vm" in mc and mc["cloud_vm"]:
            fix_cloud_dns(ip)
        
        add_dns_record(mc["name"], ip)
        mac_address = "00:11:22:33:44:" + str(55 + i)
        add_dhcphostfile_record(mc["name"], ip, mac_address)

        # Create the VM
        create_vm(mc["name"], i)

if sys.argv[1] == 'run':
    for i,mc in enumerate(config_obj["nodes"]):
        if "bootstrap_vm" in mc and mc["bootstrap_vm"]:
            print ("Provisioning %s" % mc["name"])
            provision_vm(mc["name"], i)

    for i,mc in enumerate(config_obj["nodes"]):
        tl = list()
        t = mp.Process(target=provision_vm,args=(mc["name"],i))
        tl.append(t)
        t.start()

    for t in tl:
        t.join()
