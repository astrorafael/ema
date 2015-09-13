#!/bin/bash
# EMA setup script

# Only needed for standalone deployment
# I use Ansible, instead

# Prerequisites python2.7 and setuptools

echo
echo "----------------------"
echo "Installing EMA Package"
echo "----------------------"

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

NAME=ema

# daemon in foreground utility
cp -vf scripts/$NAME.sh  /usr/local/bin/$NAME
chmod 0755 /usr/local/bin/$NAME

# init.d service script
cp -vf $NAME.init.sh /etc/init.d/$NAME
chmod 0755 /etc/init.d/$NAME

# Add auxiliar event scripts and command line utility
for script in emacli low-volt-sms+shutdown roof-script  volt-script 
do
  echo "Installing auxiliar event script $script ..."
  cp -vf scripts/$script /usr/local/bin/$script
  chmod 0755 /usr/local/bin/$script
done


# ------------------------
# Make the cache directory
# ------------------------

if [ ! -d "/var/cache/$NAME" ]; then
    echo "creating /var/cache/$NAME directory"
    mkdir /etc/$NAME 2>/dev/null 1>/dev/null
fi
# --------------------------------------------------
# Copy config files only once
# (be polite with with your existing configurations)
# --------------------------------------------------

echo
echo "-------------------------"
echo "Copying $NAME config files"
echo "-------------------------"

# python config file

if [ ! -d "/etc/$NAME" ]; then
    echo "creating /etc/$NAME as the default config directory"
    mkdir /etc/$NAME 2>/dev/null 1>/dev/null
fi

for file in config
do
    if [ ! -f "/etc/$NAME/$file" ]; then
	cp -vf config/$file /etc/$NAME/
	chmod 0644 /etc/$NAME/$file
    else
	echo "skipping /etc/$NAME/$file"
    fi
done

# service defaults file

if [ ! -f "/etc/default/$NAME" ]; then
    cp -vf default /etc/default/$NAME
else
    echo "skipping /etc/default/$NAME"
fi

echo
echo "================================="
echo "EMA daemon successfully installed"
echo "================================="

