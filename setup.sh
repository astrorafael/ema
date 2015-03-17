#!/bin/sh
# EMA setup script

# Only needed for standalone deployment
# I use Ansible, instead

# Preresuisites python2.7 and setuptools

echo
echo "Installing EMA Package..."
echo

python setup.py install


# Add config file if it does not exist
if [ ! -f "/etc/ema/config" ]; then
	echo "Copying emad config file..."
	mkdir /etc/ema 2>/dev/null 1>/dev/null
fi
cp -vf config /etc/ema/config

# Add defaults file if it does not exist
if [ ! -f "/etc/default/emad" ]; then
	echo "Copying defaults for emad service script ..."
	cp -vf default /etc/default/emad
fi

# Add service/daemon script
if [ ! -f "/etc/init.d/emad" ]; then
	echo "Installing startup script..."
	cp -vf emad.init.sh /etc/init.d/emad
	chmod 0755 /etc/init.d/emad
fi
echo "Installing startup script..."
cp -vf emad.init.sh /etc/init.d/emad
chmod 0755 /etc/init.d/emad

# Add ema command line utility
echo "Installing EMA daemon as foreground ..."
cp -rf emad.sh /usr/local/bin/emad
chmod 0755 /usr/local/bin/emad


# Add logrotate handling
echo "Installing logrotate handling ..."
cp -rf emad.logrotate /etc/logrotate.d/emad



# Add auxiliar event scripts and command line utility
for script in ema low-volt-sms+shutdown roof-script  volt-script 
do
  echo "Installing auxiliar event script $script ..."
  cp -rf scripts/$script /usr/local/bin/$script
  chmod 0755 /usr/local/bin/$script
done

# Display EMA usages
echo
echo "EMA successfully installed"
echo "* To start EMA daemon in the foreground\t: sudo emad [-h]"
echo
echo "* To start EMA Daemon background\t: sudo service emad start"
echo "* To start EMA Daemon at boot\t: sudo update-rc.d emad defaults"

