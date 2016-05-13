Name:       kuberdock-manage
Version:    1.0
Release:    2%{?dist}
Summary:    Kuberdock admin command line interface
Group:      System Environment/Libraries
License:    CloudLinux Commercial License
URL:        http://www.cloudlinux.com
Source0:    %{name}-%{version}.tar.bz2
BuildRoot:  %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:  noarch

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
install -d %{buildroot}%{_sysconfdir}/%{name}
install -m 0644 -D kuberdock-manage.conf %{buildroot}%{_sysconfdir}/%{name}
install -d %{buildroot}%{_bindir}
install -m 0755 -D kuberdock-manage %{buildroot}%{_bindir}


%files
%defattr(-,root,root,-)
%{_sysconfdir}/*
%{_bindir}/*


%changelog
* Tue May 17 2016 Sergey Fokin <sfokin@cloudlinux.com> - 1.0-2
- Initial project
