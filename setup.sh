#!/bin/bash
# EMA setup script

# Only needed for standalone deployment
# I use Ansible, instead

# Preresuisites python2.7 and setuptools

echo
echo "------------------------"
echo "Installing EMADB Package"
echo "------------------------"

python setup.py install

# ----------------------------
# Copy scripts
# can be overriden every time
# just like the python modules
# ----------------------------

echo
echo "---------------"
echo "Copying scripts"
echo "---------------"

# daemon in foreground utility
cp -vf scripts/emad.sh  /usr/local/bin/emad
chmod 0755 /usr/local/bin/emad

# init.d service script
cp -vf emad.init.sh /etc/init.d/emad
chmod 0755 /etc/init.d/emad

# Add auxiliar event scripts and command line utility
for script in ema low-volt-sms+shutdown roof-script  volt-script 
do
  echo "Installing auxiliar event script $script ..."
  cp -vf scripts/$script /usr/local/bin/$script
  chmod 0755 /usr/local/bin/$script
done


# --------------------------------------------------
# Copy config files only once
# (be polite with with your existing configurations)
# --------------------------------------------------

echo
echo "-------------------------"
echo "Copying emad config files"
echo "-------------------------"

# python config file

if [ ! -d "/etc/ema" ]; then
    echo "creating /etc/ema as the default config directory"
    mkdir /etc/emad 2>/dev/null 1>/dev/null
fi

for file in config
do
    if [ ! -f "/etc/ema/$file" ]; then
	cp -vf config/$file /etc/ema/
	chmod 0644 /etc/ema/$file
    else
	echo "skipping /etc/ema/$file"
    fi
done

# service defaults file

if [ ! -f "/etc/default/emad" ]; then
    cp -vf default /etc/default/emad
else
    echo "skipping /etc/default/emad"
fi

echo
echo "=================================================================="
echo "EMAD successfully installed"
echo "* To start EMAD daemon in the foreground\t: sudo emad"
echo
echo "* To start EMAD Daemon background\t: sudo service emad start"
echo "* To start EMAD Daemon at boot\t: sudo update-rc.d emad defaults"
echo "=================================================================="

