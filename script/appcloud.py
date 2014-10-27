#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function
import argparse, os, sys, socket, hashlib
import clcommon

DEBUG = False
msg = {}
msg['usage'] = 'python {0} -h'.format(sys.argv[0])
msg['debug'] = '[DEBUG]'
msg['info'] = '[INFO]'
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

    def check_ip(self, ip):
        if ip:
            try:
                socket.inet_aton(ip)
            except:
                print('{0} Wrong IP: "{1}". Please enter valid IP address!'.format(msg.get('debug'), ip))
                ip = None
        return ip

    def restart_service(self):
        cmd = 'service kube-apiserver restart'
        print('{0} Restarting service...'.format(msg.get('info')))
        os.system(cmd)

    def read_config(self):
        lines = clcommon.clconfpars.load(self.config_fn, case_sensitive=True)
        return lines

    def write_config(self, data):
        clcommon.clconfpars.change_settings(data, self.config_fn)
        print('{0} Writing changes to config file...'.format(msg.get('info')))

    def change(self):
        c = self.read_config()
        if DEBUG:
            print(c['MINION_ADDRESSES'])
        old_hash_iplist = hashlib.sha1(c['MINION_ADDRESSES'])
        conf_iplist = c['MINION_ADDRESSES'].replace('"', '').split(',')

        add_ip = self.check_ip(self.add_ip)
        del_ip = self.check_ip(self.del_ip)
        if self.change_ip:
            (old_ip, new_ip) = self.check_ip(self.change_ip[0]), self.check_ip(self.change_ip[1])
        else:
            (old_ip, new_ip) = None, None

        if add_ip: #add
            if add_ip not in conf_iplist:
                conf_iplist.append(add_ip)
            else:
                print('{0} "{1}" already in config'.format(msg.get('debug'), add_ip))
        if del_ip: #del
            if del_ip in conf_iplist:
                conf_iplist.remove(del_ip)
            else:
                print('{0} "{1}" not found in config'.format(msg.get('debug'), del_ip))
        if old_ip and new_ip: #change
            if old_ip in conf_iplist:
                if new_ip not in conf_iplist:
                    conf_iplist.remove(old_ip)
                    conf_iplist.append(new_ip)
                else:
                    print('{0} New IP "{1}" already in config'.format(msg.get('debug'), new_ip))
            else:
                print('{0} Old IP "{1}" not in config'.format(msg.get('debug'), old_ip))
        c['MINION_ADDRESSES'] = '"{0}"'.format(','.join(sorted(conf_iplist)))
        if DEBUG:
            print(c['MINION_ADDRESSES'])
        new_hash_iplist = hashlib.sha1(c['MINION_ADDRESSES'])
        if old_hash_iplist.hexdigest() != new_hash_iplist.hexdigest():
            self.write_config(c)
            self.restart_service()

if len(sys.argv) == 1:
    print(msg.get('usage'))
else:
    m = MinionAdmin(**args.__dict__)
    m.change()
