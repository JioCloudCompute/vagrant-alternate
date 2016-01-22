#!/usr/bin/env bash

brctl addbr br0
if [ $? -ne 0 ]
then
echo "[Error] Failed to create br0 bridge"
exit 1
fi

ifconfig br0 192.168.100.1 netmask 255.255.255.0 up
if [ $? -ne 0 ]
then
echo "[Error] Failed assign IP to br0"
exit 2
fi

dnsmasq --strict-order --except-interface=lo --interface=br0 --listen-address=192.168.100.1 --bind-interfaces --dhcp-range=192.168.100.100,192.168.100.200 --conf-file= --no-hosts --addn-hosts=/tmp/puppet.hosts --pid-file=/var/run/qemu-dnsmasq-br0.pid --dhcp-leasefile=/var/run/qemu-dnsmasq-br0.leases --dhcp-no-override --dhcp-fqdn --domain=domain.name --dhcp-hostfile=/tmp/puppet.hostfile
if [ $? -ne 0 ]
then
echo "[Error] Failed run dnsmasq to br0"
exit 2
fi

iptables-restore <<EOF
*nat
:PREROUTING ACCEPT [61:9671]
:POSTROUTING ACCEPT [121:7499]
:OUTPUT ACCEPT [132:8691]
-A POSTROUTING -s 192.168.100.1/255.255.255.0 -j MASQUERADE
COMMIT
*filter
:INPUT ACCEPT [1453:976046]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [1605:194911]
-A INPUT -i br0 -p tcp -m tcp --dport 67 -j ACCEPT
-A INPUT -i br0 -p udp -m udp --dport 67 -j ACCEPT
-A INPUT -i br0 -p tcp -m tcp --dport 53 -j ACCEPT
-A INPUT -i br0 -p udp -m udp --dport 53 -j ACCEPT
-A FORWARD -i br0 -o br0 -j ACCEPT
-A FORWARD -s 192.168.100.1/255.255.255.0 -i br0 -j ACCEPT
-A FORWARD -d 192.168.100.1/255.255.255.0 -o br0 -m state --state RELATED,ESTABLISHED -j ACCEPT
-A FORWARD -o br0 -j REJECT --reject-with icmp-port-unreachable
-A FORWARD -i br0 -j REJECT --reject-with icmp-port-unreachable
COMMIT
EOF

brctl addbr br1
if [ $? -ne 0 ]
then
echo "[Error] Failed to create br1 bridge"
exit 1
fi

ifconfig br1 172.24.133.1 netmask 255.255.255.0 up
if [ $? -ne 0 ]
then
echo "[Error] Failed assign IP to br1"
exit 2
fi

dnsmasq --strict-order --except-interface=lo --interface=br1 --listen-address=172.24.133.1 --bind-interfaces --dhcp-range=172.24.133.100,172.24.133.200 --conf-file= --pid-file=/var/run/qemu-dnsmasq-br1.pid --dhcp-leasefile=/var/run/qemu-dnsmasq-br1.leases --dhcp-no-override
if [ $? -ne 0 ]
then
echo "[Error] Failed run dnsmasq to br1"
exit 2
fi

