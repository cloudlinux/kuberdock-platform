%define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; import sys; sys.stdout.write(get_python_lib())")

Name: kuberdock-cli
Version: 0.1
Release: 7%{?dist}.cloudlinux
Summary: Libraries and executables for kuberdock command-line interface
Group: System Environment/Libraries
License: CloudLinux Commercial License
URL: http://www.cloudlinux.com
BuildArch: noarch
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
%{__install} -D -m 644 kubecli.conf %{buildroot}%{_sysconfdir}/kubecli.conf
cp -r kubecli/* %{buildroot}%{python_sitelib}/kubecli

%clean
rm -rf %{buildroot}


%files
%defattr(-,root,root,-)
%{_bindir}/kcli
%{_sysconfdir}/kubecli.conf
%{python_sitelib}/kubecli/*

%changelog
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

* Wed Apr 15 2014 Igor Savenko <bliss@cloudlinux.com> 0.1-1
- First release

