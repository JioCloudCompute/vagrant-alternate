#!/usr/bin/env bash

brctl addbr $1 2>&1 >/dev/null
if [ $? -ne 0 ]
then
ifconfig $1 down
brctl delbr $1
brctl addbr $1
fi

ifconfig $1 $2 netmask $3 up
if [ $? -ne 0 ]
then
echo "[Error] Failed assign IP to $1"
exit 2
fi

if [ -e /var/run/qemu-dnsmasq-$1.pid ]
then
pid=`cat /var/run/qemu-dnsmasq-$1.pid`
kill -9 ${pid}
rm /var/run/qemu-dnsmasq-$1.pid
fi

dnsmasq --strict-order --except-interface=lo --interface=$1 --listen-address=$2 \
    --bind-interfaces \
    --dhcp-range=${2}00,${2}99 \
    --conf-file= --no-hosts --addn-hosts=/tmp/puppet.hosts \
    --pid-file=/var/run/qemu-dnsmasq-$1.pid \
    --dhcp-leasefile=/var/run/qemu-dnsmasq-$1.leases \
    --dhcp-no-override --dhcp-fqdn --domain=domain.name \
    --dhcp-hostsfile=/tmp/puppet.hostfile
if [ $? -ne 0 ]
then
echo "[Error] Failed run dnsmasq to $1"
exit 2
fi

cat > qemu-ifup-$1 <<EOF
#!/bin/bash
set -x

switch=$1

if [ -n "\$1" ];then
        tunctl -u `whoami` -t \$1
        ip link set \$1 up
        sleep 0.5s
        brctl addif \$switch \$1
        exit 0
else
        echo "Error: no interface specified"
        exit 1
fi

EOF

chmod a+x ./qemu-ifup-$1
