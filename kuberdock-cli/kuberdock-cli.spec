%define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; import sys; sys.stdout.write(get_python_lib())")

Name: kuberdock-cli
Version: 0.1
Release: 25%{?dist}.cloudlinux
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
%{_sysconfdir}/kubecli.conf
%{_libexecdir}/suidwrap
%{python_sitelib}/kubecli/*

%changelog
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

