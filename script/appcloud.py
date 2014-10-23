#!/usr/bin/env python2
from __future__ import print_function
import os, sys
import argparse
import clcommon


msg = 'python {0} -h'.format(sys.argv[0])
parser = argparse.ArgumentParser()

parser.add_argument('--add-minion', help='Add new minion', type=str)
parser.add_argument('--del-minion', help='Delete minion', type=str)
parser.add_argument('--change-minion-ip', help='Change minion IP', type=str, nargs=2)

args = parser.parse_args()

class MinionAdmin(object):
    def __init__(self, add_minion, del_minion, change_minion_ip):
        self.config_fn = './apiserver' #/etc/kubernetes/apiserver
        self.add_ip = add_minion
        self.del_ip = del_minion
        self.change_ip = change_minion_ip

    def read_config(self):
        lines = clcommon.clconfpars.load(self.config_fn, case_sensitive=True)
        return lines

    def write_config(self, data):
        clcommon.clconfpars.change_settings(data, self.config_fn)

    def change(self):
        c = self.read_config()
        print(c['MINION_ADDRESSES'])
        conf_iplist = c['MINION_ADDRESSES'].replace('\"', '').split(',')
        if self.add_ip: #add
            if self.add_ip not in conf_iplist:
                conf_iplist.append(self.add_ip)
            else:
                print('\"{0}\" already in config'.format(self.add_ip))
        if self.del_ip: #del
            if self.del_ip in conf_iplist:
                conf_iplist.remove(self.del_ip)
            else:
                print('\"{0}\" not found in config'.format(self.del_ip))
        if self.change_ip: #change
            (old_ip, new_ip) = self.change_ip
            if old_ip in conf_iplist:
                if new_ip not in conf_iplist:
                    conf_iplist.remove(str(old_ip))
                    conf_iplist.append(str(new_ip))
                else:
                    print('New IP \"{0}\" already in config'.format(new_ip))
            else:
                print('Old IP \"{0}\" not in config'.format(old_ip))
        c['MINION_ADDRESSES'] = '\"{0}\"'.format(','.join(conf_iplist))
        print(c['MINION_ADDRESSES'])
        self.write_config(c)

if len(sys.argv) == 1:
    print(msg)
else:
    m = MinionAdmin(**args.__dict__)
    m.change()
