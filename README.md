# vagrant-alternate

```html
Segregation of control and data plane
Current vagrant setup is somewhat difficult to create an extra network interface to simulate separate control and data network path. Thus a QEMU/KVM based environment is created to host VMs with three network interfaces:

## Management network
It is used by puppet and hosting script (orchestrate.py) to install/provision VMs according to their role. This is created using QEMU’s usermode networking (-netdev user flag). This is private network only visible to HOST and a VM.  Every VM gets 10.0.2.15 as IP address. QEMU’s usermode networking also provides a DNS server (10.0.2.3). 

## Control network
It is used by openstack components to send/receive control packets. This interface is connected to a TAP interface, which is part of bridge (br0). This br0 has 192.168.100.0/24 CIDR. A DNSMASQ is run to listen for DHCP/DNS request on the bridge (br0). DNSMASQ application accepts an addn-host file to provide static DNS entries to the endpoints (VMs). This file is dynamically updated by the orchestrate.py script to add entries for DNS entries for VMs and also DNS entries <token>.service.consuldiscovery.linux2go.dk. After updating the file script sends SIGHUP signal to DNSMASQ process to re-read this file.
    
## Data network
It is used by VMs to send network traffic. This interface is also connected to another TAP interface, which is part of another bridge (br1). This bridge has 172.24.133.0/24 CIDR. A DNSMASQ process is run to listen for DHCP/DNS request on this bridge.
Besides these network interfaces, HOST port is also forward to Guest SSH port. This allows SSH connection to the VMs, for management. The serial port of the VM is also configured to be in TCP server mode. This allows one to see the serial logs.
Puppet scripts are modified to say eth2 as physical interface for contrail vrouter (see the diffs at the end of this document).

<pre>
To create new VMs:
$./orchestrate.py call t new
This would create all the VMs as listed in the machine_list (python list of dict), with desired configuration (as mentioned in the dict).

After the VMs are created, bootstrap1 VM has to be provision first. 
$./orchestrate.py provision bootstrap1
This would transfer all puppet files to the VM and execute the puppet scripts there. Also this would add DNS entry in addn-host file 
<token>.service.consuldiscovery.linux2go.dk <IP address of bootstrap1>
This resolves the DNS_blocker issue seen sometimes during provisioning of other VMs.

Now provision all other VMs:
./orchestrate.py pall t
This would take around 5-10 mins to finish, but the overall provision process would take another 15-20 mins.
SSH login:
HOST port 9900 is forwarded for bootstrap1, 9901 for haproxy, basically incrementing port number for VMs (in list order).
$ssh -i ./vm.pem vagrant@localhost –p 9900
 

DIFF
Puppet changes
Diff –git a/environment/vagrant-vbox.map.yaml b/environment/vagrant-vbox.map.yaml
index 482adfc..34bc96b 100644
--- a/environment/vagrant-vbox.map.yaml
+++ b/environment/vagrant-vbox.map.yaml
@@ -1,4 +1,6 @@
 image:
+  kvm:
+    trusty: 'ubuntu/trusty64'
   virtualbox:
     trusty: 'ubuntu/trusty64'
   lxc:
diff --git a/hiera/data/common.yaml b/hiera/data/common.yaml
index a7b7529..9b02b1a 100644
--- a/hiera/data/common.yaml
+++ b/hiera/data/common.yaml
@@ -666,6 +666,7 @@ contrail::rabbit_password: "%{hiera('rabbit_admin_pass')}"
 contrail::vrouter::metadata_proxy_secret: "%{hiera('nova_metadata_proxy_secret')}"
 contrail::vrouter::keystone_admin_password: "%{hiera('admin_password')}"
 contrail::interface: "%{hiera('private_interface')}"
+contrail::interface: "%{hiera('private_address')}"

 contrail::manage_repo: false
 contrail::vrouter::manage_repo: false
diff --git a/hiera/data/env/vagrant-vbox.yaml b/hiera/data/env/vagrant-vbox.yaml
index 75abdd1..49147b3 100644
--- a/hiera/data/env/vagrant-vbox.yaml
+++ b/hiera/data/env/vagrant-vbox.yaml
@@ -16,7 +16,7 @@ nova::compute::libvirt::libvirt_virt_type: qemu
 # more appropriate value.
 rjil::jiocloud::consul::service::interval: 120s
	
-contrail::vrouter::vrouter_physical_interface: eth1
+contrail::vrouter::vrouter_physical_interface: eth2

 rjil::system::accounts::active_users: [soren,bodepd,hkumar,jenkins,consul,pandeyop,jaspreet,vivek,ahmad,vaidy,himanshu,rohit,amar,abhishekl,anshup,varunarya,prashant,punituee]
 rjil::system::accounts::sudo_users:

Contrail module changes
diff --git a/manifests/vrouter.pp b/manifests/vrouter.pp
index 76b5c29..551c194 100644
--- a/manifests/vrouter.pp
+++ b/manifests/vrouter.pp
@@ -70,7 +70,7 @@ class contrail::vrouter (
   $package_ensure             = 'installed',
   $manage_repo                = false,
   $vrouter_interface          = 'vhost0',
-  $vrouter_physical_interface = 'eth0',
+  $vrouter_physical_interface = 'eth2',
   $vrouter_num_controllers    = 2,
   $vrouter_gw                 = undef,
   $metadata_proxy_secret      = 'set',
@@ -87,6 +87,7 @@ class contrail::vrouter (
   $log_file_size              = 10737418240,
   $log_local                  = 1,
   $debug                      = false,
+  $ipaddress                  = 0.0.0.0'
 ) {

   validate_bool($vgw_enabled)
@@ -171,7 +172,7 @@ class contrail::vrouter (
   # Due to a bug in vrouter on virtualbox, the following patch is required
   # It can be removed once the issue has been fixed
   ##
-  if ($::virtual == 'virtualbox') {
+  if ($::virtual == 'kvm') {
     $vrouter_patch='modprobe vrouter;'
   }
   else
@@ -290,7 +291,7 @@ class contrail::vrouter (
       'DISCOVERY/server':                           value => $discovery_ip;
       'DISCOVERY/max_control_nodes':                value => $vrouter_num_controllers;
       'HYPERVISOR/type':                            value => $hypervisor_type;
-      'NETWORKS/control_network_ip':                value => $vrouter_ip;
+      'NETWORKS/control_network_ip':                value => $ipaddress;
       'VIRTUAL-HOST-INTERFACE/name':                value => 'vhost0';
       'VIRTUAL-HOST-INTERFACE/ip':                  value => "${vrouter_ip}/${vrouter_cidr}";
       'VIRTUAL-HOST-INTERFACE/gateway':             value => $vrouter_gw_orig;
 
</pre>
```
