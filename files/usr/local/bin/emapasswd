#!/usr/bin/env python

# PASSWORD GENETAROR UTILITY FOR HTTP REST API

# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

#--------------------
# System wide imports
# -------------------

import sys
import argparse
import os
import os.path
import getpass

#--------------
# other imports
# -------------

try:
    from ema.web import encrypt
except ImportError:
    import hashlib
    def encrypt(password):
        return hashlib.sha256(password).hexdigest()


# ----------------
# Module constants
# ----------------

VERSION_STRING = "1.0.0"


# -----------------------
# Module global variables
# -----------------------

# -----------------------
# Module global functions
# -----------------------

# Create file
# emapasswd -c    /etc/ema.d/passwd foo  # Prompts for a password
# emapasswd -c -i /etc/ema.d/passwd foo  < cat /etc/mypasswd
# emapasswd -c -b /etc/ema.d/passwd foo bar

# Update file
# emapasswd    /etc/ema.d/passwd foo  # Prompts for a password
# emapasswd  -i /etc/ema.d/passwd foo  < cat /etc/mypasswd
# emapasswd  -b /etc/ema.d/passwd foo bar

# Dont create file
# emapasswd -n    /etc/ema.d/passwd foo  # Prompts for a password
# emapasswd -c -i /etc/ema.d/passwd foo  < cat /etc/mypasswd
# emapasswd -n -b /etc/ema.d/passwd foo bar


def createParser():
    # create the top-level parser
    parser = argparse.ArgumentParser(prog=sys.argv[0])
    
    parser.add_argument('--version',     action='version', version='{0}'.format(VERSION_STRING))
    parser.add_argument('-p' , '--plain',       action='store_true', help='store plain password (not encrypted) in password file (NOT RECOMMENDED)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c' , '--create-file', action='store_true', help='Create the passwdfile. if passwdfile already exists, it is rewritten and truncated. This option cannot be combined with the -n option.')
    group.add_argument('-d' , '--delete-user', action='store_true', help='Delete a user from the passwdfile. It cannot be combined with the -c option.')
    parser.add_argument('passwdfile', type=str, help='password file path')
    parser.add_argument('username',   type=str, help='user name')
    parser.add_argument('password',   type=str, nargs='?', help='user password', default='')
   
    return parser



class PasswordTable(dict):

    def __str__(self):
        '''Serialize dictionary in a <username>:<password> format'''
        return '\r\n'.join([ "{0}:{1}".format(key,  val) for key, val in self.items() ])

    def save(self, filename):
        '''
        Save Password table into a file
        '''
        with open(filename, 'w') as f:
            f.writelines(str(self))
    
    @staticmethod
    def load(filename):
        '''
        Loads Password table from file
        '''
        table = PasswordTable()
        with open(filename, 'r') as f:
            for line in f:
                item = line.split(':')
                table[item[0]] = item[1]
        return table

    def askPassword(self, username):
        '''
        Interactive method to request a password
        '''
        new_passwd1 = getpass.getpass(prompt="Password: ")
        new_passwd2 = getpass.getpass(prompt="Verify password: ")
        if new_passwd1 != new_passwd2:
            print("Sorry, passwords don't match. Bye.")
            sys.exit(1)
        return new_passwd1


    def possiblyEncrypt(self, password, plainFlag):
        if not plainFlag:
            return encrypt(password)
        else:
            return password


def main():
    '''
    Utility entry point
    '''
    try:
        options = createParser().parse_args()
        
        if options.create_file:
            
            table = PasswordTable()
            if options.password == '':
                options.password = table.askPassword(options.username)
            table[options.username] = table.possiblyEncrypt(options.password, options.plain)
            table.save(options.passwdfile)
       
        elif options.delete_user:
        
            table = PasswordTable.load(options.passwdfile)
            try:
                del table[options.username]
            except IndexError:
                print("user {0} did not exist previously".format(options.username))
            table.save(options.passwdfile)
        
        else:
            table = PasswordTable.load(options.passwdfile)
            if options.password == '':
                options.password = table.askPassword(options.username)
            table[options.username] = table.possiblyEncrypt(options.password, options.plain)
            table.save(options.passwdfile)

    except KeyboardInterrupt:
        print('')
    except Exception as e:
        print("Error => {0}".format(e))

main()
