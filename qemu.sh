#!/usr/bin/env bash

# Base disk image
BASE_IMG="/home/ubuntu/.vagrant.d/boxes/trusty64/0/libvirt/box.img"

# check if qemu is running
if [ -e /tmp/qmp-sock-$1 ]
then
	echo "$1 already running....!"
        exit 1
fi

>./logs/$1.log

# Create qemu disk image.
if [ ${10} == "yes" ]; then
	qemu-img create -f qcow2 -b ${BASE_IMG} ./images/$1.img $9G >>./logs/$1.log 2>&1
fi

# Execute the qemu process.
sudo qemu-system-x86_64 -enable-kvm -name $1 \
	-cpu kvm64  --enable-kvm\
	-m $2 \
	-smp $3 \
	-drive file=./images/$1.img,if=virtio \
	-netdev user,id=prtap-$1,hostname=$1,hostfwd="tcp::$4-:22" -device e1000,netdev=prtap-$1 \
	-netdev type=tap,id=tap-$1,ifname=tap-$1 -device e1000,netdev=tap-$1,mac=$5 \
	-netdev type=tap,id=ptap-$1,ifname=ptap-$1,script=./qemu-ifup -device e1000,netdev=ptap-$1,mac=$6 \
	-vnc :$7  -monitor unix:/tmp/$1.monitor.sock,server,nowait \
    -serial tcp::$8,server,nowait >>./logs/$1.log 2>& 1&
