SCP:puppet-rjil/hiera/:/etc/puppet/hiera
SCP:puppet-rjil/modules/:/etc/puppet/modules
SCP:puppet-rjil/manifests/:/etc/puppet/modules/rjil/manifests
SCP:puppet-rjil/files/:/etc/puppet/modules/rjil/files
SCP:puppet-rjil/templates/:/etc/puppet/modules/rjil/templates
SCP:puppet-rjil/lib/:/etc/puppet/modules/rjil/lib
SCP:puppet-rjil/:/etc/puppet/manifests

cp /etc/puppet/hiera/hiera.yaml /etc/puppet
export consul_discovery_token=#PUPPET_ENV[consul_discovery_token]

[ -e '/etc/facter/facts.d/consul.txt' -o -n '${consul_discovery_token}' ] || (echo 'No consul discovery token set. Bailing out. Use ". newtokens.sh" to get tokens.' ; exit 1)
mkdir -p /etc/facter/facts.d; [ -e '/etc/facter/facts.d/consul.txt' ] && exit 0; echo consul_discovery_token=${consul_discovery_token} > /etc/facter/facts.d/consul.txt
echo consul_gossip_encrypt=`echo ${consul_discovery_token}| cut -b 1-15 | base64` >> /etc/facter/facts.d/consul.txt


# Fix /etc/hosts
echo "127.0.1.1 #PUPPET_ENV[hostname].domain.name #PUPPET_ENV[hostname]" >> /etc/hosts

echo env=#PUPPET_ENV[env] > /etc/facter/facts.d/env.txt

echo $(printf 'Acquire::http::proxy "%s";' #ENV[http_proxy]) > /etc/apt/apt.conf.d/03proxy
echo $(printf 'Acquire::https::proxy "%s";' #ENV[http_proxy]) >> /etc/apt/apt.conf.d/03proxy
echo "123.108.225.6 pool.ntp.org" >> /etc/hosts

echo export http_proxy=#ENV[http_proxy] >> /etc/environment
echo export https_proxy=#ENV[https_proxy] >> /etc/environment
echo export no_proxy='127.0.0.1,169.254.169.254,localhost,consul,jiocloud.com' >> /etc/environment

export http_proxy=#ENV[http_proxy]
export https_proxy=#ENV[https_proxy]
export no_proxy='127.0.0.1,169.254.169.254,localhost,consul,jiocloud.com'

echo "APT::Get::AllowUnauthenticated 1;" > /etc/apt/apt.conf.d/02allow-unsigned

apt-get clean
apt-get update
apt-get install -y git curl

test -e puppet.deb && exit 0
release=$(lsb_release -cs)
http_proxy=#ENV[http_proxy] wget -O puppet.deb http://apt.puppetlabs.com/puppetlabs-release-${release}.deb
dpkg -i puppet.deb
apt-get clean
apt-get update
apt-get install -y puppet-common=3.6.2-1puppetlabs1

apt-get clean
puppet apply -e 'ini_setting { basemodulepath: path => "/etc/puppet/puppet.conf" , section => main, setting => basemodulepath, value => "/etc/puppet/modules.overrides:/etc/puppet/modules" } ini_setting { default_manifest: path => "/etc/puppet/puppet.conf", section => main, setting => default_manifest, value => "/etc/puppet/manifests/site.pp" } ini_setting { disable_per_environment_manifest: path => "/etc/puppet/puppet.conf", section => main, setting => disable_per_environment_manifest, value => "true" }'

puppet apply --detailed-exitcodes --debug -e "include rjil::jiocloud"; if [[ $? = 1 || $? = 4 || $? = 6 ]]; then apt-get update; puppet apply --detailed-exitcodes --debug -e "include rjil::jiocloud"; fi

