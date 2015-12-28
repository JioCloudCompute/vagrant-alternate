#!/usr/bin/env bash

# Base disk image
BASE_IMG="/home/ubuntu/.vagrant.d/boxes/trusty64/0/libvirt/box.img"

# check if qemu is running
if [ -e /tmp/qmp-sock-$1 ]
then
	echo "$1 already running....!"
        exit 1
fi
# Create qemu disk image.
if [ $8 == "yes" ]; then
	qemu-img create -f qcow2 -b ${BASE_IMG} ./images/$1.img >>$1.log 2>&1
fi

# Execute the qemu process.
sudo qemu-system-x86_64 -enable-kvm -name $1 \
	-cpu kvm64  --enable-kvm\
	-m $2 \
	-smp $3 \
	-drive file=./images/$1.img,if=virtio \
	-netdev user,id=prtap$6,hostname=$1,hostfwd="tcp::$4-:22" \
	-device e1000,netdev=prtap$6 \
	-netdev type=tap,id=tap$6,ifname=tap$6 -device e1000,netdev=tap$6,mac=$5 \
	-vnc :$6 \
        -serial tcp::$7,server,nowait >>$1.log 2>& 1&
