%{!?python_sitelib: %define python_sitelib %(%{__python} -c
"from distutils.sysconfig import get_python_lib; print get_python_lib()")}


Name:       kuberdock-manage
Version:    0.1.0
Release:    1%{?dist}
Summary:    Kuberdock command line utilities
Group:      System Environment/Libraries
License:    CloudLinux Commercial License
URL:        http://www.cloudlinux.com
Source0:    %{name}-%{version}.tar.bz2
BuildRoot:  %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:  noarch

BuildRequires: python

Requires: python
Requires: python-requests
Requires: python-click
Requires: PyYAML


%description
Kuberdock command line utilities


%prep
%setup -q


%build


%install
rm -rf %{buildroot}
install -d %{buildroot}%{_sysconfdir}/%{name}
install -d %{buildroot}%{_bindir}
install -m 0755 -D kdctl %{buildroot}%{_bindir}
install -m 0755 -D kcli2 %{buildroot}%{_bindir}
install -D -d -m 755 %{buildroot}%{python_sitelib}/kdctllib
cp -r kdctllib/* %{buildroot}%{python_sitelib}/kdctllib


%clean
rm -rf %{buildroot}


%files
%defattr(-,root,root,-)
%{_sysconfdir}/*
%{_bindir}/*
%{python_sitelib}/kdctllib/


%changelog
* Tue May 17 2016 Sergey Fokin <sfokin@cloudlinux.com> - 1.0.0-1
- Initial project
