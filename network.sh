#!/bin/sh

# Set to the name of your bridge
BRIDGE=br0

# Network information
NETWORK=192.168.100.0
NETMASK=255.255.255.0
GATEWAY=192.168.100.1
DHCPRANGE=192.168.100.100,192.168.100.200

# Optionally parameters to enable PXE support
TFTPROOT=
BOOTP=

do_brctl() {
    brctl "$@"
}

do_ifconfig() {
    ifconfig "$@"
}

do_dd() {
    dd "$@"
}

do_iptables_restore() {
    iptables-restore "$@"
}

do_dnsmasq() {
    dnsmasq "$@"
}

check_bridge() {
    if do_brctl show | grep "^$1" > /dev/null 2> /dev/null; then
	return 1
    else
	return 0
    fi
}

create_bridge() {
    do_brctl addbr "$1"
    do_brctl stp "$1" off
    do_brctl setfd "$1" 0
    do_ifconfig "$1" "$GATEWAY" netmask "$NETMASK" up
}

enable_ip_forward() {
    echo 1 | do_dd of=/proc/sys/net/ipv4/ip_forward > /dev/null
}

add_filter_rules() {
do_iptables_restore <<EOF
# Generated by iptables-save v1.3.6 on Fri Aug 24 15:20:25 2007
*nat
:PREROUTING ACCEPT [61:9671]
:POSTROUTING ACCEPT [121:7499]
:OUTPUT ACCEPT [132:8691]
-A POSTROUTING -s $NETWORK/$NETMASK -j MASQUERADE 
COMMIT
*filter
:INPUT ACCEPT [1453:976046]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [1605:194911]
-A INPUT -i $BRIDGE -p tcp -m tcp --dport 67 -j ACCEPT 
-A INPUT -i $BRIDGE -p udp -m udp --dport 67 -j ACCEPT 
-A INPUT -i $BRIDGE -p tcp -m tcp --dport 53 -j ACCEPT 
-A INPUT -i $BRIDGE -p udp -m udp --dport 53 -j ACCEPT 
-A FORWARD -i $1 -o $1 -j ACCEPT 
-A FORWARD -s $NETWORK/$NETMASK -i $BRIDGE -j ACCEPT 
-A FORWARD -d $NETWORK/$NETMASK -o $BRIDGE -m state --state RELATED,ESTABLISHED -j ACCEPT 
-A FORWARD -o $BRIDGE -j REJECT --reject-with icmp-port-unreachable 
-A FORWARD -i $BRIDGE -j REJECT --reject-with icmp-port-unreachable 
COMMIT
EOF
}

start_dnsmasq() {
    do_dnsmasq \
	--strict-order \
	--except-interface=lo \
	--interface=$BRIDGE \
	--listen-address=$GATEWAY \
	--bind-interfaces \
	--dhcp-range=$DHCPRANGE \
	--conf-file="" \
        --no-hosts \
        --addn-hosts=/tmp/puppet.hosts \
	--pid-file=/var/run/qemu-dnsmasq-$BRIDGE.pid \
	--dhcp-leasefile=/var/run/qemu-dnsmasq-$BRIDGE.leases \
	--dhcp-no-override \
	${TFTPROOT:+"--enable-tftp"} \
	${TFTPROOT:+"--tftp-root=$TFTPROOT"} \
	${BOOTP:+"--dhcp-boot=$BOOTP"}
}

setup_bridge_nat() {
    if check_bridge "$1" ; then
	create_bridge "$1"
	enable_ip_forward
	add_filter_rules "$1"
	start_dnsmasq "$1"
    fi
}

setup_bridge_vlan() {
    if check_bridge "$1" ; then
	create_bridge "$1"
	start_dnsmasq "$1"
    fi
}

setup_bridge_nat "$BRIDGE"
