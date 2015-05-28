Version: 0.1
Name: kuberdock
Summary: KuberDock
Release: 51%{?dist}.cloudlinux
Group: Applications/System
BuildArch: noarch
License: CloudLinux Commercial License
URL: http://www.cloudlinux.com
Source0: %{name}-%{version}.tar.bz2

Requires: nginx
Requires: influxdb
Requires: redis
Requires: postgresql-server
Requires: fabric
Requires: etcd == 2.0.9-1.el7.centos
Requires: kubernetes >= 0.15.0-4.el7.centos.1
Requires: flannel >= 0.3.0
Requires: dnsmasq >= 2.66
# For semanage, but in new CentOS it's installed by default:
Requires: policycoreutils-python >= 2.2
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
Requires: python-psycopg2 >= 2.5.4
Requires: python-redis >= 2.10.3
Requires: python-requests >= 2.4.3
Requires: python-simple-rbac >= 0.1.1
Requires: python-sse >= 1.2
Requires: python-webassets >= 0.10.1
Requires: python-wsgiref >= 0.1.2
Requires: python-psycogreen >= 1.0

# AutoReq: 0
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%description
Kuberdock

%prep
%setup -n %{name}-%{version}

%build

%install
rm -rf %{buildroot}
%{__install} -d %{buildroot}%{_defaultdocdir}/%{name}-%{version}/
mkdir -p %{buildroot}/var/opt/kuberdock
mkdir -p %{buildroot}%{_sysconfdir}/uwsgi/vassals
mkdir -p %{buildroot}%{_sysconfdir}/nginx/conf.d/
mkdir -p %{buildroot}%{_sysconfdir}/nginx/ssl/
mkdir -p %{buildroot}/var/log/kuberdock
cp -r * %{buildroot}/var/opt/kuberdock
%{__install} -D -m 0644 conf/kuberdock.ini %{buildroot}%{_sysconfdir}/uwsgi/vassals/kuberdock.ini
%{__install} -D -m 0644 conf/kuberdock-ssl.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf
%{__install} -D -m 0644 conf/kuberdock.conf %{buildroot}%{_sysconfdir}/sysconfig/kuberdock/kuberdock.conf


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

# Even if SELinux disabled, we set labels for future
semanage fcontext -a -t httpd_sys_content_t /var/opt/kuberdock/kubedock/frontend/static\(/.\*\)\?
restorecon -Rv /var/opt/kuberdock/kubedock/frontend/static

%files
%defattr(-,root,root)
%attr (-,nginx,nginx) /var/opt/kuberdock
%attr (-,nginx,nginx) /var/log/kuberdock
%dir %{_sysconfdir}/nginx/ssl
%config %{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf
%config %{_sysconfdir}/uwsgi/vassals/kuberdock.ini
%attr (-,nginx,nginx) %config(noreplace) %{_sysconfdir}/sysconfig/kuberdock/kuberdock.conf

%changelog
* Thu May 28 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>  0.1-51
- AC-257: fixed return button on result page
- AC-405: Add validation to name field in env step
- AC-295: Add style to error text at login page
- AC-249: Prepared style IPPool to new scructure
- renamed back 'args' to 'command'
- added dockerfile instructions parsing by comma
- added ENTRYPOINT instruction
- added decision logic if entrypoint is string or a list
- Fix empty tables in container tabs
- front-end persistent storage functionality refactored

* Tue May 26 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>  0.1-50
- AC-258: Add style to entrypoint field
- AC-147: Fix public ip allocation
- namespaces now are created while a pod is being created and deleted after a pod had been deleted

* Tue May 26 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-49
- Changed image attribute 'command' to 'args'

* Tue May 26 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-48
- Moved '_parse_cmd_string' method to Pod class

* Tue May 26 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>  0.1-47
- Fix breadcrumb information in containers tabs page; AC-398: Rename users statuses; AC-254: Add style to user activity page
- Fix container variables page
- removed temporary persistendDrives data from pod model on submit
- AC-394: Fix adding the same container to the pod
- AC-249: Add design to IPPol page 1 part; Fix return podeName in container monitoring tab
- Fix design in  variables tab in container page, Add podname to all tabs, hide empty tables from container page
- AC-394 part 2: Set kube type and restart policy based on the first selection
- Fix action on ippool page; AC-401
- Remove bug (not found parentID) with create container steps
- AC-414: Show pod name in all container tabs
- AC-402 Page for user to edit his profile
- AC-394 fix: Set propertly kube type and restart policy based on the first selection
- AC-404 Fix portal ips for kuberdock pods
- Fix design bugs AC-403, Ac-409, AC-4010, AC-411
- AWS deploy fixes
- Moved pods API to namespaces and v1beta3

* Thu May 21 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>  0.1-46
- AC-205: Create numbers of containers in one pod
- AC-260: Add action on delete node
- Fix dinamic data on monitoring, configuration generals tabs
- AC-393: Random password for admin
- Show message if admin password missing during createdb.py execution
- Fix node redeploy
- modified persistent drives mount logic

* Thu May 21 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>  0.1-45
- Fixed host ports. Fixed pod delete
- AC-355: Show modal dialog on user save
- Fix services with refactored pods api
- AC-380: Add new design to users page & change links in top menu
- Fixed container details display; fixed pod graps dependencies; fixed updated start-stop button on changing pod state;
- Fix jquery tabs in user profile
- Fixed distorted containers view; added kube types to select dropdown
- Fixed services deleting on stopped pod
- AC-385: Decrease kubes cpu value

* Wed May 20 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>  0.1-44
- Add spoiler to node install log, class Reason, AC-362,369: Rename some fields, AC-324: Fix design bug in breadcrumb (Safari)
- AC-355: Edit user
- AC-371 Cpu limits
- Fix ntpd problem on Amazon (not tested). Improve firewalld rules. Fix bug with freehost
- Added processing 'set_public_ip' attribute on the end of pod creation
- Fix User blocked page, some design bugs, remove spoiler from node log instalation, AC-343
- Basic functionality for ceph-based persistent drives
- Removed pods_app/pods_views.js and pd.sh
- added v1beta3 to KubeQuery

* Sun May 17 2015 Igor Savenko <bliss@cloudlinux.com>  0.1-43
- Switched pods application to AMD (require.js)

* Fri May 15 2015 Igor Savenko <bliss@cloudlinux.com>  0.1-42
- Refactored pods backend interface

* Thu May 14 2015 Andrey Lukyanov <alukyanov@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>  0.1-40
- pod deleting fix (can delete if there are no services and pods)
- AC-338: Show container environment variables

* Thu May 14 2015 Andrey Lukyanov <alukyanov@cloudlinux.com> 0.1-39
- unauthorized user namespaces fix

* Thu May 14 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-36
- Deploy fixes for semanage and ssh-keygen.
- Fixed SSE on nodes page.
- AC-328: Fix problem setting restart policy
- fixed non-settings kube price on kube creation
- fixed usage REST API (connected to added ability for a package to have more than one kube)
- AC-317 - Add fivecon, AC-320 - Fix design in nodes detailes page, AC-321 - fix menu arrow, fix redeploy button position
- Switch to v1beta3 for nodes api and services api
- AC-300: Show detailed container data
- AC-304: ports validation disabled; AC-299: pod name, container name in breadcrumbs; AC-291: show image likes; AC-290: image "more" button;
- AC-320 - Hide start button on pod page while pod has status pending
- AC-181 - show all fields on add node page, AC-183 - Add style to logout button
- AC171 - Add style to choose ip field
- AC 334 - change endpoints name, Cloud-7 - fix style logo on login page
- AC-319 fix select item on node pagelist
- AC-300: Show detailed container data
- AC-266: Add placeholders to environment variables step; AC-300: Fix design in container page; AC-292: Add spoiler to logs
- AC-327 Enable firewalld on master. AC-333 nsswitch.conf workaround.
- Improved deploy helpers.
- Fix node capacity on node page.
- Remove node install log with node.
- AC-346 AWS detection and auto-change host-gw to udp if on amazon. Not tested.
- Namespaces + pods API v1beta3 + some fixes

* Wed May 06 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-35
- Add package to kuberdock-internal user
- AC-304 Containers without port and v1beta3 migration helper option
- Prohibit service pods removing
- fixed missing package of a user
- AC-301: Show containers of just created pod
- AC-316: Fix start/stop pod problem due to model extra fields
- Deploy.sh logging and exit on first error. kub_install.sh now exits on first error.
- Fix Gevent + uwsgi.
- bugfix: removed creating dict from dict 'dict(response.form)'
- fixed user creation
- remove 'amount' from package's schema and add 'price' to kube's one
- bugfixes connected to new kube model (more than one kube per package)
- AC-326: Redeploy button for node
- Batch node adding, add logging, remove make_scripts.
- Now only same version of kubernetes on master and nodes. Code clean up.
- deploy.sh is determining ip_address and interface on its own
- node inner interface is deduced from master_ip

* Wed Apr 29 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-34
- AC-292 Node saves install log and shows it if in troubles state.
- Design fixes AC: 266, 279, 281, 288, 299
- Design fixes AC: 271, 276, 279, 297, 312, 31
- Remove manifests from kubelet config as we no longer use them
- AC-262: Run service pods as KuberDock Internal user
- Reworked WHMCS API

* Mon Apr 27 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-33
- Added preliminary persistent storage implementation

* Mon Apr 27 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.1-32
- Show true container state on container page
- Add node troubles reason
- Last small gevent related fixes
- Fix for no node condition
- Fix typo in deploy.sh with externalIPs feature.
- Change to generateName in services
- Design fixes AC: 270, 275, 279, 280, 284, 285, 286, 287
- Added persistent drive script

* Fri Apr 24 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-31
- gevent fixes
- deploy.sh improvemets

* Mon Apr 22 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-30
- multiports
- bugfixes

* Mon Apr 20 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.1-29
- Add full style to container page tabs
- AC-218, AC-211 add style to variables page & fix style in others pages in container template
- Add style to last step in add pod template

* Fri Apr 17 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.1-28
- SELinux fixes
- AC-217 (SSH-key generation)
- kube-public-ip fix, show count of kubes of pod,
  added price and kubes into validation scheme (added new type strnum)
   

* Thu Apr 16 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com> 0.1-27
- Merge "AC-202: Default page for admin and user roles"
- set_public_ip fix, next redirect on login fix, 401 status code fix
- Add new design to add pod template, fix some bugs in settings,
  create new templates in container page
- Introduce new desgn login page

* Wed Apr 15 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-26
- First release

