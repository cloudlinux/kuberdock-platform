# "commit" variable expected to be passed by cmdline via rpmbuild --define='...'
%global shortcommit	%(c=%{commit}; echo ${c:0:7})

Version: 0.1
Name: kuberdock
Summary: KuberDock
Release: 2.git%{shortcommit}%{?dist}.cloudlinux
Group: Applications/System
BuildArch: noarch
License: CloudLinux Commercial License
Url: http://www.kernelcare.com
Source0: %{name}-%{shortcommit}.tar.gz

Requires: nginx
Requires: influxdb
Requires: redis
Requires: postgresql-server
Requires: kubernetes
Requires: flannel >= 0.3.0
Requires: dnsmasq >= 2.66
Requires: python-uwsgi
Requires: python-cerberus >= 0.7.2
Requires: python-flask >= 0.10.1
Requires: python-flask-assets >= 0.10
Requires: python-flask-influxdb >= 0.1
Requires: python-flask-login >= 0.2.11
Requires: python-flask-mail >= 0.9.1
Requires: python-flask-sqlalchemy >= 2.0
Requires: python-jinja2 >= 2.7.2
Requires: python-markupsafe >= 0.23
Requires: python-sqlalchemy >= 0.9.7-3
Requires: python-unidecode >= 0.04.16
Requires: python-werkzeug >= 0.9.6-1
Requires: python-werkzeug-doc >= 0.9.6
Requires: python-amqp >= 1.4.5
Requires: python-anyjson >= 0.3.3
Requires: python-argparse >= 1.2.1
Requires: python-billiard >= 3.3.0.18
Requires: python-blinker >= 1.3
Requires: python-celery >= 3.1.15
Requires: python-ecdsa >= 0.11
Requires: python-gevent >= 1.0
Requires: python-greenlet >= 0.4.2
Requires: python-influxdb >= 0.1.13
Requires: python-itsdangerous >= 0.24
Requires: python-ipaddress >= 1.0.7
Requires: python-kombu >= 3.0.23
Requires: python-nose >= 1.3.0
Requires: python-paramiko >= 1.12.4
Requires: python-psutil >= 0.7
Requires: python-psycopg2 >= 2.5.1
Requires: python-redis >= 2.10.3
Requires: python-requests >= 2.4.3
Requires: python-simple-rbac >= 0.1.1
Requires: python-sse >= 1.2
Requires: python-webassets >= 0.10.1
Requires: python-wsgiref >= 0.1.2

# AutoReq: 0
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%description
Kuberdock

%prep
%setup -c

%build

%install
rm -rf %{buildroot}
%{__install} -d %{buildroot}%{_defaultdocdir}/%{name}-%{version}/
mkdir -p %{buildroot}/var/opt/kuberdock
mkdir -p %{buildroot}%{_sysconfdir}/uwsgi/vassals
mkdir -p %{buildroot}%{_sysconfdir}/nginx/conf.d/
mkdir -p %{buildroot}%{_sysconfdir}/nginx/ssl/
cp -r * %{buildroot}/var/opt/kuberdock
%{__install} -D -m 0644 conf/kuberdock.ini %{buildroot}%{_sysconfdir}/uwsgi/vassals/kuberdock.ini
%{__install} -D -m 0644 conf/kuberdock-ssl.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf


%clean
rm -rf %{buildroot}

%posttrans

%define sslcert %{_sysconfdir}/nginx/ssl/kubecert.crt
%define sslkey %{_sysconfdir}/nginx/ssl/kubecert.key

%post
umask 077

if [ ! -f %{sslkey} ] ; then
%{_bindir}/openssl genrsa -rand /proc/apm:/proc/cpuinfo:/proc/dma:/proc/filesystems:/proc/interrupts:/proc/ioports:/proc/pci:/proc/rtc:/proc/uptime 1024 > %{sslkey} 2> /dev/null
fi

FQDN=`hostname`
if [ "x${FQDN}" = "x" ]; then
   FQDN=localhost.localdomain
fi

if [ ! -f %{sslcert} ] ; then
cat << EOF | %{_bindir}/openssl req -new -key %{sslkey} \
         -x509 -days 365 -set_serial $RANDOM \
         -out %{sslcert} 2>/dev/null
--
SomeState
SomeCity
SomeOrganization
SomeOrganizationalUnit
${FQDN}
root@${FQDN}
EOF
fi

%files
%defattr(-,root,root)
%attr (-,nginx,nginx) /var/opt/kuberdock
%dir %{_sysconfdir}/nginx/ssl
%config %{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf
%config %{_sysconfdir}/uwsgi/vassals/kuberdock.ini
