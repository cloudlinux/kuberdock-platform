%define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; import sys; sys.stdout.write(get_python_lib())")

Name: kuberdock-cli
Version: 1.0
Release: 6%{?dist}.cloudlinux
Summary: Libraries and executables for kuberdock command-line interface
Group: System Environment/Libraries
License: CloudLinux Commercial License
URL: http://www.cloudlinux.com
#BuildArch: noarch
Source0: %{name}-%{version}.tar.bz2
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildRequires: python

Requires: python
Requires: python-requests
Requires: python-argparse
Requires: python-click


%description
Kuberdock command-line interface

%prep
%setup -q

%build

%install
rm -rf %{buildroot}
%{__install} -d %{buildroot}%{_defaultdocdir}/%{name}-%{version}/
mkdir -p %{buildroot}/usr/share/kuberdock-cli

%{__install} -D -d -m 755 %{buildroot}%{python_sitelib}/kubecli
%{__install} -D -m 755 kcli %{buildroot}%{_bindir}/kcli
%{__install} -D -m 755 kcli-iptables %{buildroot}%{_bindir}/kcli-iptables
%{__install} -D -m 644 kubecli.conf %{buildroot}%{_sysconfdir}/kubecli.conf
cp -r kubecli/* %{buildroot}%{python_sitelib}/kubecli
if [ ! -d %{buildroot}%{_libexecdir} ];then
    mkdir -p %{buildroot}%{_libexecdir}
fi
cc -DHOOKEXEC='"/usr/bin/kcli"' -o %{buildroot}%{_libexecdir}/suidwrap src/suidwrap.c
chmod 4755 %{buildroot}%{_libexecdir}/suidwrap
%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{_bindir}/kcli
%{_bindir}/kcli-iptables
%{_libexecdir}/suidwrap
%{python_sitelib}/kubecli/*

%config(noreplace) %{_sysconfdir}/kubecli.conf

%changelog

* Mon Sep 12 2016 Aleksandr Skorodumov <askorodumov@cloudlinux.com> 1.0-5
- AC-3931 AC-3696 Network isolation rules

* Thu Jul 07 2016 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Aleksandr Skorodumov <askorodumov@cloudlinux.com> 1.0-4
- AC-3990 KCLI. Add upgrade option to deploy script
- AC-3488 Fixed volume name generation
- AC-3648 KCLI. After upgrade kcli don't rewrite global config
- AC-3348 Add integration tests for nonfloating IP feature

* Wed Jun 15 2016 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Maksym Lobur <mlobur@cloudlinux.com>, Aleksandr Skorodumov <askorodumov@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 1.0-3
- AC-3458 fix: user can't create pod with more that 10 kubes
- Install kuberdock-plugin when deploy cli
- AC-3248 Fix kcli - two conflicting patches
- KCLI. Get home dir from config path
- AC-3239 Fix unit test kcli. Change Pod init order. Newly-given data has higher priority than one found on disk.
- AC-3069 Fix failing kubecli helper test

* Wed Apr 20 2016 Igor Savenko <bliss@cloudlinux.com> 1.0-2
- AC-2963: removed passwords from /etc/kubecli.conf;
  restricted file permissions for ~/.kubecli.conf;
  removed excessive data from ~/.kubecli.conf.
- AC-2827: To kcli-deploy.sh added command line argument to specify iface for flannel

* Mon Mar 14 2016 Igor Savenko <bliss@cloudlinux.com> 1.0-1
- raised tag

* Wed Feb 17 2016 Igor Savenko <bliss@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com> 1.0-0.rc.2
- fixed kuberdock-cli test
- AC-2159: Bundle of KCLI-related issues fixed
- AC-2217: Added possibility to list or delete environment variables of pending container in KCLI

* Mon Feb 08 2016 Igor Savenko <bliss@cloudlinux.com> 1.0-0.rc.1
- raised tag

* Tue Feb 02 2016 Igor Savenko <bliss@cloudlinux.com> 0.1-30
- AC-1937: Improve error handling in KCLI
- AC-2014: Starting pod repeatedly brings 'Unknown format' error
- AC-2028: kcli kuberdock search & kcli docker search doesn't work

* Wed Dec 30 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-29
- AC-603: Return status when JSON enabled.
- AC-1741: set YAML origin. Added test for kcli. Added filtering by origin.
- AC-1922: Implemented 'register' functionality

* Fri Nov 20 2015 Aleksandr Tishin <atishin@cloudlinux.com> 0.1-28
- AC-1475: Remove authorization options in KCLI

* Thu Nov 12 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.1-27
- Removed old api param set_public_ip

* Wed Nov 11 2015 Fedor Degtyarev <fdegtyarev@cloudlinux.com> 0.1-26
- AC-1138: In case of incorrect config an error displayed

* Fri Oct 30 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com> 0.1-25
- AC-1345: check --kubes type and value
- AC-1372: add validation to environment variable name. Fixed API errors output in kcli
-

* Wed Oct 21 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.1-24
- KCLI. Remove info messages (breaks cPanel plugin)

* Tue Oct 20 2015 Aleksandr Tishin <atishin@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com> 0.1-23
- Fix kuberdock-cli.spec
- AC-1298: Add template name to kcli
- AC-1271: use token instead of user/password

* Wed Oct 07 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com> 0.1-22
- KCLI container.py bugfix: on comparison of unicode and non-unicode strings defaults to false
- AC-1169: kcli: rename kuberdock kubes to kuberdock kube-types
- AC-1176: added CRUD actions for predefined apps templates in kcli
- AC-1204: python 2.6 compatibility fixes for kcli

* Tue Sep 29 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com> 0.1-21
- AC-988: added cli command to create and run pods from yaml files

* Tue Sep 08 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com> 0.1-20
- AC-551 kcli: unit tests added with minor refactoring of kcli code

* Wed Aug 26 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.1-19
- AC-569: kubecli: remove --read-only option
- AC-562: change default config path (/etc/kubecli.conf -> ~/.kubecli.conf); if default config doesn't exist, copy specified config to default config path
- AC-565: rename kcli kuberdock -i|--image -> -C|--container

* Mon Aug 17 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.1-18
- AC-566 KCLI new port syntax
- AC-765 KCLI. Use token for all requests
- AC-777 KCLI. Added user config

* Sun Aug 09 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-17
- AC-570: completed

* Wed Jul 29 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.1-16
- AC-661 KCLI FIxed plain data output
- AC-570: Added persistent storage functinality for KCLI. Added persistent storage listing

* Thu Jul 23 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-15
- kuberdock-cli KubeCtl bugfix

* Wed Jul 22 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-14
- Change postprocess iptables rules
- added --token parameter to kcli
- commented out volumeMounts data because the PD functionality not implemented

* Tue Jul 21 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-13
- kcli bugfix: env variables now are being appended, not overriden
- AC-491: finished

* Sun Jul 19 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-12
- AC-491: added suidwrapper for kcli-iptables-wrapper

* Fri Jul 03 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.1-11
- AC-626 KCLI Add --env command, adding env variables

* Fri Jul 03 2015 Alex Tishin <atishin@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.1-10
- AC-632: fixed
- AC-564 KCLI Add create command
- AC-545: Add 'describe' action to 'kcli kuberdock'

* Fri Jul 03 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.1-9
- AC-563 KCLI Merge image and kuberdock commands
- AC-601 Fix

* Wed Jul 01 2015 Igor Savenko <bliss@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.1-8
- AC-535: added command kcli kuberdock forget [NAME] to delete one or all pending pods
- AC-546 KCLI Delete image from container not worked
- AC-530: fixed. Added self._FIELDS for start/stop methods
- AC-531: in PrintOut mix-in default attributes checks changed to use __getattr__
- AC-567: KCLI. Traceback --mount-path. Fixed

* Thu Jun 25 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-7
- AC-568: Fixed 'Unknown format' error on 'kcli kubectl describe pods <NAME>' command
- AC-527: Added comments for user and password

* Sun Jun 21 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.1-6
- AC-502 cPanel. Public IP for application. kcli added get free ip method

* Tue Jun 16 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.1-5
- AC-518 cPanel. Added image  get command
- kcli set kube count and no ports by default

* Tue Jun 02 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-4
- fixed volume mounts and settings port as public
- Silenced untrusted cert warning

* Mon Jun 01 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-3
- added port protocol settings if missing

* Mon Jun 01 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-2
- Refactored to reflect current kuberdock functinality

* Wed Apr 15 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-1
- First release
