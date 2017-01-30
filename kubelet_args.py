#!/usr/bin/env python

# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.


from collections import OrderedDict
import os
import re
import shlex
import subprocess
import sys


CONF = '/etc/kubernetes/kubelet'
OPTION = 'KUBELET_ARGS'

ARG = re.compile('(?P<key>.+?)=(?P<value>.*)')


def usage():
    print(os.linesep.join([
        'Usage: {0} --option=[value]',
        '  {0} --cpu-multiplier=1 : add/edit one option',
        '  {0} --cpu-multiplier=2 --memory-multiplier=3 : add/edit two options',
        '  {0} --memory-multiplier= : remove option']).format(__file__))


def main():
    # get args to be added/modified/removed
    args = sys.argv[1:]
    if not args:
        usage()
        sys.exit(-1)

    in_args = OrderedDict()
    for arg in args:
        match = ARG.match(arg)
        if match:
            arg_dict = match.groupdict()
            in_args[arg_dict['key']] = arg_dict['value']

    # read kubelet config
    with open(CONF) as read:
        config = read.read().splitlines()

    pattern = re.compile('{0}\s*=\s*(?P<args>.+)'.format(OPTION))

    lines = []
    for line in config:
        # find line to be processed
        match = pattern.match(line)
        if match:
            args = shlex.split(match.groupdict()['args'])[0]
            new_args = OrderedDict()
            # get existent options
            for arg in shlex.split(args):
                match = ARG.match(arg)
                if match:
                    arg_dict = match.groupdict()
                    new_args[arg_dict['key']] = arg_dict['value']
            # update options
            for key, value in in_args.items():
                if value:
                    # add/modify option
                    new_args[key] = value
                elif key in new_args:
                    # remove option if no value specified
                    del new_args[key]
            line = '{0}={1}'.format(
                OPTION,
                # double escape of command line string
                subprocess.list2cmdline([
                    subprocess.list2cmdline(
                        ['{0}={1}'.format(k, v) for k, v in new_args.items()]
                    )
                ])
            )
        lines.append(line)

    # write kubelet config
    with open(CONF, 'w') as write:
        write.writelines(['{0}{1}'.format(l, os.linesep) for l in lines])

    # restart kubelet
    try:
        subprocess.check_output(['systemctl', 'restart', 'kubelet.service'],
                                stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(e.output)
        sys.exit(e.returncode)


if __name__ == '__main__':
    main()
