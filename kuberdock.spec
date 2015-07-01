Version: 0.2
Name: kuberdock
Summary: KuberDock
Release: 9%{?dist}.cloudlinux
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
Requires: etcd >= 2.0.9-1.el7.centos
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
Requires: python-gevent >= 1.0.2
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
Requires: python-botocore
Requires: python-boto
Requires: python-alembic
Requires: python-flask-migrate >= 1.4.0
Requires: python-flask-script
Requires: python-bitmath

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
mkdir -p %{buildroot}/var/log/kuberdock/updates
mkdir -p %{buildroot}/var/lib/kuberdock
mkdir -p %{buildroot}%{_bindir}
cp -r * %{buildroot}/var/opt/kuberdock
ln -sf  /var/opt/kuberdock/kubedock/updates/kuberdock_upgrade.py %{buildroot}%{_bindir}/kuberdock_upgrade.py
chmod 755 %{buildroot}/var/opt/kuberdock/kubedock/updates/kuberdock_upgrade.py
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

# Setting labels
SESTATUS=$(sestatus|awk '/SELinux\sstatus/ {print $3}')
if [ "$SESTATUS" != disabled ];then
    semanage fcontext -a -t httpd_sys_content_t /var/opt/kuberdock/kubedock/frontend/static\(/.\*\)\?
    restorecon -Rv /var/opt/kuberdock/kubedock/frontend/static
fi

%files
%defattr(-,root,root)
%attr (-,nginx,nginx) /var/opt/kuberdock
%attr (-,nginx,nginx) /var/log/kuberdock
%attr (-,nginx,nginx) /var/lib/kuberdock
%dir %{_sysconfdir}/nginx/ssl
%config %{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf
%config %{_sysconfdir}/uwsgi/vassals/kuberdock.ini
%attr (-,nginx,nginx) %config(noreplace) %{_sysconfdir}/sysconfig/kuberdock/kuberdock.conf
%attr (-,nginx,nginx) %{_bindir}/kuberdock_upgrade.py

%changelog
* Wed Jul 01 2015 Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.2-9
- added alembic version dir check in deploy.sh
- removed references to deleted files from auth/index.html file
- AC-584: Add check item on click event
- Little fix for "versions" folder
- Should fix AC-589; Waiting for flanneld to start before docker.
- AC-449: Add styles to alerts notification
- AC-590 Package fields changes
- AC-594: brought back database sessions
- fixed small bug related to changes in billing schema

* Sun Jun 28 2015 Igor Savenko <bliss@cloudlinux.com> 0.2-8
- bugfix related to getting rid of old code

* Sun Jun 28 2015 Igor Savenko <bliss@cloudlinux.com> 0.2-7
- removed emptyDir creating for non-persistent volumes

* Sat Jun 27 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.2-6
- AC-571: remove extra buttons from settings templates, remove extra modal dilog from add node page
- AC-527: Added comments for user and password
- AC-568: Fixed 'Unknown format' error on 'kcli kubectl describe pods <NAME>' command
- AC-549: Change kapi output
- AC-430: Add new style to selects
- AC-574: Add image name to 3-th step in adding container & change link about more position
- AC-558 Set kube price depending on package
- Properly working alembic migrations added.
- Fixed kdmigrations directory path.
- Fix yum errors.
- Fixed bug with Flask-Migrate
- Added backend CRUD for persistent storage
- Added 'loading.gif' for x-editable
- removed old unused code

* Wed Jun 24 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.2-5
- First part of update system for kuberdock.
- deploy.sh, manage.py add_node now have -t --testing option to enable testing repo.
- Change our repos to disabled by default.
- Little optimizations of deploy scripts.
- Fix ntpq exit code checking.
- AC-574: Fix docker command

* Tue Jun 23 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-4
- AC-542: Add more modal dilogs
- AC-550: Added setting AWS ELB DNS-name in web-interface
- refactored pod_item.js a bit
- moved send_events and send_logs routines to kubedock/utils.py
- AC-347: Add "Learn more..." link to variables page
- bugfix. Added missing import 'json' in kubedock/utils.py
- To deploy.sh a check has been added to verify that ROUTE_TABLE_ID envvar is set if amazon

* Mon Jun 22 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.2-3
- AC-557: Fix ports, volume mounts and environment variables duplicates
- removed conditional displaying 'Add volume' button
- removed ternary conditional logic in favour of if/else blocks in ippool/app.js
- added conversion port to int in dockerfile.py
- AC-556; Command for adding node to cluster from console.
- Fix requests logging;
- Change pd.sh placement logic;
- Add development utility function INTERACT().
- Added 'strict_slashes=False' to all pod REST routines

* Mon Jun 22 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-2
- AC-495: Add new design to calendar in user activity page

* Sun Jun 21 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.2-1
- Added AWS public interface for pods
- Returned stdout logging of public IP events
- Added passing application context to gevent
- Added basic ELB url showing in web-interface
- AC-249: Add new design to IPPool page
- AC-537 Show Pod entrypoint as space-separated list
- Fixes for AWS node deploy. Rename kub_install.template to node_install.sh
- Fix bugs with pkgname and check_status now works.
- AC-536: Fix recursive Dockerfile data retrieving problems
- AC-526: Get Dockerfile for official images
- AC-382: Sort ip list in IP Pool table
- AC-335: Check the added ports in 1 container
- AC-400: Fix 'more...' link for official Docker images

* Tue Jun 16 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-0
- AC-293: Add style to alerts windows
- AC-487: Show node memory
- added to deploy.sh and kuberdock.spec changes for impersonated install
- AC-509 WHMCS. Persistent storage в GB

* Mon Jun 15 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.1-61
- AC-474: Add style to persistent volumes & publick IPs tabs
- AWS persistent storage bugfix
- Fix bug widts button add subnet
- AC-342 Added additional fields to package IP, persistent storage, over traffic price&values
- AC-505: Add active status to li items, AC-497: change icon status in add container steps
- AC-498: Apply replication controller for one pod
- AC-506: Fix missing restartPolicy
- AC-483: Add new design to setting progile&settings profile edit pages
- Modify deploy.sh not to ask any questions on amazon
- AC-246: Add logic bulk operation to pods
- AC-490 Recursive parse dockerfiles

* Tue Jun 09 2015 Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.1-60
- AC-344: Add new style to second step in add container
- AC-331: Added 2 additional fields to package: prefix & suffix
- Fix bug with extra spaces in podname
- AC-500: transformed createdb.py to manage.py (to create and upgrade db)

* Mon Jun 08 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-59
- added installation of epel and jq to an aws node
- minor bugfix in pd.sh
- reverted persistent storage settings interface look'n'feel
- added possibility to limit line size (_make_dash subroutine, kapi/helpers.py)
- added quotes for amazon_settings.py file

* Sat Jun 06 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>  0.1-58
- Added installing aws-cli to a node if amazon instance
- AC-471: Added support for AWS-based persistent volumes
- AC-482: Stop pods and unbind public IPs if user is locked
- AC-437: fixed 'unknown' kube numbers on pods page
- AC-344: Add new style to second step in add container
- AC-397: New Trial User limit policy (10 kubes per user)
- AC-472 Show env vars from dockerfile
- AC-349: Token authorization for WHMCS
- Fix timezone settings, fix moment js. Apply timezone to container start time
- Little update spec to new etcd and gevent
- AC-426, AC-273, AC-435 Fix calculator. AC-359 Separate kube count for containers
- AC-450, AC-456, AC-457, AC-458, AC-463, AC-465, AC-466 - design fixes
- AC-446, AC-447, AC-448, AC-451, AC-453 - design fixes
- Fixed public ip with NetworkManager enabled.
- Fixed restartPolicy rendering. Removed gevent ssl workaround
- Remove style from graph on monitoring page & set default kube_type value

* Tue Jun 02 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>  0.1-57
- AC-441: Fix bug with empty kube tupe when add 2-th container
- AC-432: Add help text if tables in user page is empty
- Remove border in graph-item on container monitoring page
- AC-397: Add TrialUser limit -- 3 kubes per container in pod
- Clean up in logging. Error logs not commented

* Mon Jun 01 2015 Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>  0.1-56
- podcollection bugfixes
- AC-434: Remove exactly one proper container if pod contains multiple containers with the same image

* Mon Jun 01 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>  0.1-54
- Add new style to alert messages to login page
- AC-384: Fix pods with the same name but different users
- AC-385: Reduce CPU value in 10 times for default kubes
- Change logs url from 'es-proxy' to 'logs'

* Thu May 29 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>  0.1-53
- Added lights to field status in nodelist table
- AC-421: Show error message if login failed
- Add bulk operation to podlist, fix checkbox position
- Filter out empty strings when parsing dockerfile commands
- Added service ip to frontend instead of pod ip
- Add autohide message in login page
- Fixed nodes cpu cores retrieval for graphs
- Fixed hostports

* Thu May 28 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>  0.1-52
- AC-417: Move service pods creation to kapi
- Added posibility to edit command on container.
- Fix Don't create service pods without ports at all.

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

