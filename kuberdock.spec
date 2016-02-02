Version: 1.0
Name: kuberdock
Summary: KuberDock
Release: 0%{?dist}.rc.3.cloudlinux
Group: Applications/System
BuildArch: noarch
License: CloudLinux Commercial License
URL: http://www.cloudlinux.com
Source0: %{name}-%{version}.tar.bz2

BuildRequires: nodejs
BuildRequires: nodejs-less
BuildRequires: nodejs-clean-css

Requires: nginx
Requires: influxdb
Requires: redis
Requires: postgresql-server
Requires: fabric >= 1.10.2
Requires: etcd == 1:2.0.9
Requires: kubernetes-master == 1:1.1.3
Requires: flannel == 1:0.5.3
Requires: dnsmasq >= 2.66
# For semanage, but in new CentOS it's installed by default:
Requires: policycoreutils-python >= 2.2
Requires: python-uwsgi
Requires: python-cerberus >= 0.9.1
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
Requires: python-celery == 1:3.1.19
Requires: python-ecdsa >= 0.11
Requires: python-gevent >= 1:1.0.2
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
Requires: python-dateutil
Requires: python-boto
Requires: python-alembic
Requires: python-flask-migrate >= 1.4.0
Requires: python-flask-script
Requires: python-bitmath
Requires: python-websocket-client >= 0.32.0
Requires: python-elasticsearch >= 1.0
Requires: PyYAML

# AutoReq: 0
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%description
Kuberdock

%prep
%setup -n %{name}-%{version}

%build
# TODO change here when merge all apps to patch only one require config
start='urlArgs: "bust="'
replace='(new Date()).getTime()'
replace_with=$(date +"%s")
sed -i "/$start/ {s/$replace/$replace_with/}" kubedock/frontend/static/js/*/require_main.js
# In case of deprecating undocumented %exclude macro
rm -rf dev-utils

%install
rm -rf %{buildroot}
python minimize.py
%{__install} -d %{buildroot}%{_defaultdocdir}/%{name}-%{version}/
mkdir -p %{buildroot}/var/opt/kuberdock
mkdir -p %{buildroot}%{_sysconfdir}/uwsgi/vassals
mkdir -p %{buildroot}%{_sysconfdir}/nginx/conf.d/
mkdir -p %{buildroot}%{_sysconfdir}/nginx/ssl/
mkdir -p %{buildroot}/var/log/kuberdock/updates
mkdir -p %{buildroot}/var/lib/kuberdock
mkdir -p %{buildroot}%{_bindir}
cp -r * %{buildroot}/var/opt/kuberdock
ln -sf  /var/opt/kuberdock/kubedock/updates/kuberdock_upgrade.py %{buildroot}%{_bindir}/kuberdock-upgrade
%{__install} -D -m 0644 conf/kuberdock-ssl.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf
%{__install} -D -m 0644 conf/shared-kubernetes.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/shared-kubernetes.conf
%{__install} -D -m 0644 conf/shared-etcd.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/shared-etcd.conf
%{__install} -D -m 0644 conf/kuberdock.conf %{buildroot}%{_sysconfdir}/sysconfig/kuberdock/kuberdock.conf


%clean
rm -rf %{buildroot}

%posttrans

%define sslcert %{_sysconfdir}/nginx/ssl/kubecert.crt
%define sslkey %{_sysconfdir}/nginx/ssl/kubecert.key
%define dhparam %{_sysconfdir}/nginx/ssl/dhparam.pem

%define kd_vassal_source /var/opt/kuberdock/conf/kuberdock.ini
%define kd_vassal %{_sysconfdir}/uwsgi/vassals/kuberdock.ini
if [ ! -f %{kd_vassal} ]; then
    cp %{kd_vassal_source} %{kd_vassal}
    chmod 644 %{kd_vassal}
fi

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

if [ ! -f %{dhparam} ] ; then
%{_bindir}/openssl dhparam -rand /proc/apm:/proc/cpuinfo:/proc/dma:/proc/filesystems:/proc/interrupts:/proc/ioports:/proc/pci:/proc/rtc:/proc/uptime -out %{dhparam} 2048 2> /dev/null
fi

# Setting labels
SESTATUS=$(sestatus|awk '/SELinux\sstatus/ {print $3}')
if [ "$SESTATUS" != disabled ];then
    semanage fcontext -a -t httpd_sys_content_t /var/opt/kuberdock/kubedock/frontend/static\(/.\*\)\?
    restorecon -Rv /var/opt/kuberdock/kubedock/frontend/static
    # Setting permission for using etch from nginx
    if [ -e /var/opt/kuberdock/nginx.pp ];then
        semodule -i /var/opt/kuberdock/nginx.pp
    fi
fi

%postun
# When 1 - it's upgrade, 0 it's remove
if [ "$1" = "0" ]; then
   rm -f %{kd_vassal}
fi

%files
%defattr(-,root,root)
%attr (-,nginx,nginx) /var/opt/kuberdock
%attr (-,nginx,nginx) /var/log/kuberdock
%attr (-,nginx,nginx) /var/lib/kuberdock
%dir %{_sysconfdir}/nginx/ssl
%config %{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf
%config %{_sysconfdir}/nginx/conf.d/shared-kubernetes.conf
%config %{_sysconfdir}/nginx/conf.d/shared-etcd.conf
%attr (-,nginx,nginx) %config(noreplace) %{_sysconfdir}/sysconfig/kuberdock/kuberdock.conf
%attr (-,nginx,nginx) %{_bindir}/kuberdock-upgrade
%exclude /var/opt/kuberdock/dev-utils

%changelog
* Tue Feb 02 2016 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Michael Bagrov <mbagrov@cloudlinux.com>, Vadim Musin <vmusin@cloudlinux.com> 1.0-0.rc.3
- AC-1976: KuberDock - Predefined Apps page - Align pagination level
- AC-1858: Do not ignore "Exclude IPs" parsing error
- "reboot_node" update helper
- Add deploy.sh options to specify flanneld backend
- AC-2048: upgrade to stock kernel
- Raise requirements to strict 1.1.3 kubernetes, add fix for node's statuses
- AC-1664: Required fields are in red
- AC-1809: display names of pods in PD list; traffic lights like in IPPool
- AC-1992, AC-2116: various KubeType improvements; refactoring; bugfix
  Backbone AssociatedModels for Kubes and Packages
  KubeTypes are sorted by default (available come first)
  Show warnings if there is no available kube types
  Bugfix:
    if there are more than one container in pod, unavailable kube types weren't
    disabled;
    if there is no any kube type in user's package, user cannot go to the final
    step of pod creation;
    disabled kube type may be selected, if there is no available kube types;
- AC-1875: Change preloader from gif to css, remove extra js lib, & loading View, some refactoring
- AC-2065, AC-2059: defaults for "pdSize" + tests
- AC-2031: recover on partially failed PD operations.
  Added common lock mechanism.
  Added locks for destructive PD operation: create, make FS, delete.
  Added recover to unmap temporary mapped ceph-drives.
  Fixed APIError for PD forbidden deletion.
- AC-2013: move feedback func to python, add checks
  work with etcd extended_statuses only from python
  add contextmanager for python, that send_feedback if exception were raise
  add some checks to sh script
- AC-2168 : KuberDock > Pod's page > In Environment variables step if fields is empty, user can't go to the next step
- AC-2033:better msg and notify when can't create PD
  When can't create PD, don't show internal PD name for user and send notification to admin
- AC-2153: KuberDock > Pod's page > remove  error message if container port empty
- AC-1977: each modification add quotes to command
- Raised SQLAlchemy connection pool limits
- AC-1782: KuberDockAC-1782 Sort Predefined apps in alphabetic way
- Small animation fixes
- AC-2174 : KuberDock > Predefined Applications > Switching sorting
- AC-2184, AC-2041: package-specific addition to the postDescription
  also improved and documented hack in kubedock/frontend/templates/apps/index.html
  for testing PA without billing system
- Small fix login page & clearfix class
- AC-2175: Change a notification about exceeding the limits page license
- AC-1653: PA fields ordering
- AC-2001: fixed bug with pod deletion; new SSE event pod:delete
  Now if listener catches pod change and pod status in db is "deleting",
  it will send pod:delete instead of pod:change to frontend.
  Frontend won't make GET request after pod deletion.
- AC-2036: Implement reliable message delivery to frontend
- AC-1779: admin is allowed to login as himself
- Fixed node installation failure in case when the bridge module was not loaded before install.
  This happened with new stock centos kernels
- AC-2013: update node part
- AC-2045,2055,2056: k8s2etcd; kubernetes 1.1.3
  add k8s to etcd middleware service
  Service watch for change in resources(only pods for now) and save them to etcd.
  Add etcd listener, that listen for etcd and process events from it.
  Also, process events stored by service between kuberdock restarts.
  Delete extended_statuses from etcd after processing.
  added update k8s to 1.1.3
  added 'After=etcd.service' to kube-apiserver.service file
  add '--watch-cache=false' to apiserver config file
  add '--cpu-cfs-quota=true' to kubelet config file
  Warning: Will restart all pods to apply new limits update kubes to new hard limits
- PA: empty additional configuration block
  Pods: status "waiting" on container page
  Pods: filter pods with status "deleting"
  Pods: added default volumes=[]  (fixed traceback in pstorage)
  ContainerStates: added kuberdock-specific reasons and exit codes
  ContainerStates: fixed "false positive" case of overlapping CS
  k8s-1.1.3: succeeded containers have reason=Error
- AC-2062: Introduced namespaces for persistent disks

* Mon Jan 18 2016 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Michael Bagrov <mbagrov@cloudlinux.com> 1.0-0.rc.2
- AC-1942: Add data icon on pod page
- AC-1946: Change bell icon in notifitation block
- AC-1969: Add icons to license & profile tab in settings page
- AC-1792: Fix navigate to user edit from login history page
- AC-1865: Remove capitalize text in labels on settings preapp page
- AC-1959: fixed expiration date and license type representation
- AC-1928: removed update log event while log has not yet come
- AC-1794: First IPPool subnet always is in focus even when user click on another one.
- AC-1914 Login to KD through WHMCS
- AC-1962: installation ID validation (it must be non-empty)
- AC-1004: Allocation of available kybe-types
- AC-1980: Add new color to ip busy status
- AC-1662: Hide unbind button in ippool
- AC-1960: fix kuberdock version in kapi.collect
- AC-1663: Don't hide error messages automatically
- AC-1991: Fix error in console on log page
- AC-1943: added date validation. Added python-dateutil.
- AC-1796: enabled lowercase letters for envvars
- AC-1877: added endpoint that returns full timezones list.
- AC-1530: Fix Pod IP isolation on the same node
- AC-1961: license statistics info - fixed count of running users containers count, added pods counts per node. Fixed rpm package version info
- AC-1823: before marking a node as having troubles one we try to restart kubelet
- AC-1906: add comments, remove warning, namespaces contents already deleted explicitly, no need for warning
- AC-1884: PD deletion now is asynchronous; Fixed pod unbinding from PD's on failed pod starts.
  Fixed unittests for kapi.podcollection. Denied pod deletion for non-owners.
  At persistent volume page now only drives existing in DB will be shown.
- AC-1567: Create user-friendly Timezone drop down list
- AC-1871: KuberDock > Add PD > Validation 'Container path' field
- AC-1919: catch NetworkError in execute_run
- AC-1733: Fix Elasticsearch clusterization
- AC-1930: Added a script to clean obsolete containers /var/lib/docker and it's cron job, running every 6 hours
- AC-2012: show notification instead of nginx error after failed ajax requests
- AC-1978: fix urls in main menu; fix "no backendData" error
- AC-1948, AC-2029: pod&container states bugfix and improvements; more tests; refactoring
- AC-1951: Change style in installation ID line
- AC-1379: Add preloaders to all pages
- AC-1993 Change billing period for default package
- AC-2063: concat updates to one, add concat-updates
- AC-2000: Persistent drive listing now implemented via DB
- AC-1968: celery replaced with patched version

* Thu Dec 31 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 1.0-0.rc.1
- Add style to license status
- AC-1659: Do not create internal pods if node failed to add
- Fixed localhost isolation
- AC-1936: fix start pod response
- fix empty logs
- Compatible fix of deps and cadvisor
- Added notifications
- AC-1910: fixed view of pods stat-graphics
- Updated kuberdock deps versions(just epoch)
- Remove old cadvisor

* Wed Dec 30 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Michael Bagrov <mbagrov@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.4-15
- AC-1817: More convenient GC settings
- AC-1913: fixed CEPH drive unmapping during initial FS creation.
- AC-1907: exception replaced with warning on failed ceph drive creation.
- AC-1775: store postDescription; image search bugfix
- AC-1835: Fix fix_pods_timeline
- Fixed influxdb on CentOS 7.2
- AC-1891: fix table head on pods page
- edit user: move to profile page after saving changes
- AC-1915: Fixes publicIP with podPort chaned and fixes publicIP unbind in some cases
- Change kubes params
- container&pod network graphs are back
- AC-1894: fixed deleting of persistent drives during user deleting
- AC-1671: Display PD size on container page
- AC-1840: Add suspended status on user page
- AC-1898 Change hostPort to podPort for yaml api
- Fixed public ip with empty protocol in spec
- validate that user's package includes pod's kube type
- AC-1926: Rename kubes to Number of Kubes
- AC-1922: Implemented server-side register functionality: when request made from admin account REMOTE_ADDR is saved to database
- Add backward compatible new kubedock-cadvisor
- AC-1846: administrator notification block.
- AC-1781, AC-1903: plans for predefined apps
- AC-1556: Display corresponding status for suspended user
- AC-1931: Placeholder must be gray
- AC-1925: Move data/stats icon in pod page;
- AC-1062: Add title to action buttons in podlist; Hide remove icon if pod is pending
- AC-1905: implemented license information saving and retrieving. InstallationID saving.
- AC-1609: actions on license invalidation
- AC-903: Delete message must have one mask
- Cluster network isolation
- AC-1916: Map registered hosts to etcd
- AC-1933: redirect http to https
- Cut old public ip parts (not all, but most garbage)
- Show user settings if logged as admin

* Fri Dec 25 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Fedor Degtyarev <fdegtyarev@cloudlinux.com> 0.4-14
- AC-1745; Kuberdock pre_start_hook
- AC-1474: limit max PD size
- Fix 00070_update.py exception if DNS-pod doesn't exists
- AC-810: User list items pagination and sorting.
- Fix node monitoring&users pages size & paddings between containers
- AC-1876; AC-1830
- AC-476: display limits on monitoring graphs; bugfix
- AC-1879: Firefox design fix in add PD fields; AC-1685: small font size fix on node&pod page;
- AC-1864: Allow containers to access the Internet; +fixes
- AC-1829: Add icons to monitoring&variables links in container page;
- AC-1542: predefined apps UI and grammar mistakes
- AC-1891: small UI fix on pods page
- AC-1669 - show Error if not resolvable node hostname
- AC-1886: Fix iptables rules creation for very first pod
- container list container image tag is hidden via JS replace
- Add delete pod item in podlist table
- AC-1573, AC-1774, AC-1802: errors duplication fix; some other bgfix
- Fixed search on Pods page
- Fixed preloader for group actions on Pod page
- Delete request for busy PD will return 400 (not 200, as before)
- AC-1806: predefined apps pagination; hid broken filters (PA, users)
- Add icons to logs&monitoring links in node detailed page
- AC-1908: fix Preloader error on addnode page
- workaround for utils localtime routine: if passed either null or underined immediate return
- AC-1847

* Fri Dec 18 2015 Alex Tishin <atishin@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>,  0.4-13.4
- Fixed listeneres bug with rare incorrect redis value
- Kuberdock net plugin with pods isolation and public ip
- Workaround for kubelet net events order
- Migration to network plugin. Small fixes
- AC-1568: small bugfix
- Fix skip test in test_utils.py because of network plugin migration
- AC-1688: Fix dns pod access to kubernetes master
- AC-1706: Implement pod internal DNS resolving
- AC-1704: added processing for failed pods start when there are no resources

* Wed Dec 16 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.4-13.3
- AC-1568: image search must accept any symbols; small improvements    
- Regex-validation should have human-readable messages.
- AC-1773 Allow multistrings in pre-apps
- AC-653: SSE; small refactoring; bugfix
- AC-1715: move API users endpoint; bugfix
- AC-1816: small workaround for tests
- AC-1692 Use bbcode in postDescription
- AC-1735: statuses fix
- AC-1759: PD dialog doesn't allow to choose from exising volumes
- AC-1451: filter by pod_id too; scrollbar fix; internal kube fix
  Now if two containers in different pods have the same container_name, their logs won't mix.
  Fixed niceScroll in container's logs page.
  Fixed a few errors with internal kube.
- AC-1718: generate sourceUrl, if it was not specified
- AC-1741: KCLI: set YAML origin

* Mon Dec 14 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Michael Bagrov <mbagrov@cloudlinux.com> 0.4-13.2
- AC-1600: unittests for kapi.nodes
- AC-1695:autogen start with char and lowercase all
- AC-1601: unittests for kapi.pd_utils
- AC-1502: cleaned pod API output
- AC-1674: Restrict elasticsearch ports only for nodes' ips, not all ports. Deprecated my old script, which is not used now
- AC-1674: Added a migration script to correct the iptables rules on old kuberdock installations
- AC-1599: unittests for kapi.ippool
- allow lifecycle in yaml
- AC-1677: Rename delete confirmation button
- AC-1539: Add smalfix to uncheck persistent if mounth path is empty

* Tue Dec 08 2015 Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.4-13.1
- AC-1539: Hotfix empty path name
- AC-1758: Container edit buttons lead to last container; couple of bugs fixed

* Mon Dec 07 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.4-13
- AC-1330: Add new style to PD adding
- AC-1608: suspend/unsuspend logic; returning ip to the pods; refactiorng
- AC-595, AC-1514: billing api bugfix, refactoring, tests
- AC-1548: web-interface moved to SPA paradigm
- AC-1539: Add PD > Checkbox should be disable without container path - fix if path removed

* Fri Nov 27 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.4-12
- AC-1426: Add style to pod/node logs && textarea in add preapp
- AC-1555: package must include period
- AC-1489: node logs are not displayed
  From now on if kuberdock can not get logs and kuberdock-logs pod is not running
  or running less than a minute, then error message will be different:
  "Logs service is collecting data. Wait few minutes please.".
  In frontend error message will show up in logs textarea, but not in bottom-left corner.
  Stop requesting logs from server if user leaves "logs" tab.
- AC-1525: Highlight the captured traceback in update
- AC-1487: show period in total price preapp
- AC-1564: check node hostname before add
- use transactions in testutils.testcases.DBTestCase; nose attrib plugin suport
- AC-1537: Container status should change according to user's action.
- AC-1540: price is displayed including PD and Public IP on pod page
- AC-1591: added unittests to api.logs, fixed minor errors in api.logs methods
- AC-903: Delete message have one mask
- AC-1535: Improve logs error handling
- AC-1526: extended error handling in CephStorage, added timeouts for remote commands. Tests and refactoring for CephStorage
- AC-1569: container states kube qty. fix; logout redirect fix; db tests fix
- AC-1654: Add style to paginator
- AC-900: ip block/unblock fix; also fixed some tests
- AC-1539: Add PD > Checkbox should be disable without container path

* Thu Nov 19 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Fedor Degtyarev <fdegtyarev@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.4-11
- Fixed duplicated message
- fix in js: mutable in model defaults
- fix 00049 update according to changes in 00062
- Predefined apps authorization-free page bugfix. Autogenerated fields are now hidden
- Disable all events if preloader show on pods app
- AC-1058: fix volumes on container's page
- From now on PersistentDisk record in database will be created immediately after pod creation (before was at first start).
- Fix Header menu in User View mode
- AC-1471: don't return empty collections
- AC-1512
- AC-1424: return caret to Administration menu
- AC-1505: Add button to change kubes QTY in container
- AC-1495: Resource limits are recalculated on every kube amount change.

* Wed Nov 18 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.4-10
- AC-1069, AC-1287, AC-1085; nested models support; refactoring
- AC-1500: fix error that occurs, if update restarting container
- AC-824: Show real ip status in ippool
- AC-1525: Show full traceback if update-script fails
- AC-1302: 'Cancel' button on 'Choose image' step should navigate to 'Final setup' after adding more containers to pod.
- AC-1424:remove static_pages, refactor menu. Remove unused static_pages app. Refactoring menu. Add MenuItemRole table.
- AC-1351: change error message for used PV
- AC-1522: fix migration in 59th update-script
- AC-1254: fix cpu to two digits after point
- AC-1494: Fix restart kube-controller-manager after each update script. Refactoring of upgrade utility.
- AC-1198: small fix in kube type validation

* Tue Nov 17 2015 Igor Savenko <bliss@cloudlinux.com> 0.4-9.1
- restored accidentally removed fixes

* Mon Nov 16 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.4-9
- moved modules mocking to module level in test_podcollection.py and test_validation.py
- test_validation fix
- removed checking calling of 'modify_node_ips' method because of its unavailability
- AC-1293: Disabled chechbox in bulk operation if podcollection is empty && some fix in logic bulk operaton
- AC-1451: display container log history
- kapi.pod_states renamed to kapi.usage; container states moved from listeners to kapi.usage
  Container logs api now returns logs from previous container's lives too. More tests for kapi.es_logs.
- Fixed some tests; added default .coveragerc config.
- AC-1477: Improve KuberDock web-ui SSL security
- AC-1094: Clean up old params in api
- AC-1490: Prevent elasticsearch search failures after document structure changes
- AC-1471: add date_from, date_to params to usage. Accept date_from, date_to params for usage query.
- AC-1429: allow non-english names
- AC-1118: rename 'Standard kube' to 'Standard'
- AC-1460: added possibility to reuse custom variables in predefined apps templates
- AC-1450: fixed timezone conversion for statistics
- AC-1478: Hide negative values in nodes monitoring plots

* Thu Nov 12 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.4-8
- AC-1430: move role edit to update script
- AC-991: fixed timezone saving and conversion
- changed ext4 filesystem to xfs for persistent volumes
- some fixes for predefined apps unauthorized page
- AC-980. Restrict create pod when no free public ip in pool. Refactored IP allocation. Removed blinker signals. Removed old api param set_public_ip
- Fixes for updates: 00045_update.py, pstorage module
- AC-1364: fix persistent-volumes path everywhere

* Wed Nov 11 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.4-7.1
- AC-1249: Add podname to confirmation remove dilog box
- AC-1056: fix KeyError
- AC-1446: Add error class to name fields if validation == false & scroll to this items
- persistent volumes link bugfix

* Wed Nov 11 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.4-7
- Fix Grammar mistakes AC-856, АС-1317, AC-1388, AC-1377, AC-1292;
- Fix validation in podname 63 max simbols - AC-914; AC-1443: Rename some fields
- AC-1400: do not show podIP if pod does not have ports
- AC-1198: improved validation in kube types API
- Node logging timestamp should contain timezone info
- AC-933: ports validation; added ports validaion in frontend, fixed in backend
- duplicate volumes bugfix; buttons on environment variables step bugfix
- AC-1447: noDataIndicator for nodes monitoring
- AC-1335: Edit user > Users back button fix navigate to user's list;
- AC-1445: Add stop button if status is pending
- AC-978: show message if no such image, fix style with word-break;
- AC-1430: hide role HostingPanel
- Added field `internal` to rbac_role model: role 'HostingPanel' is internal now.
- AC-1046: show containerPort if hostPort none; If hostPort is 'None', show containerPort.
- Fix Published and Protocol columns

* Mon Nov 09 2015 Alex Tishin <atishin@cloudlinux.com>  0.4-6.5
- AC-1436: Fix logs ordering

* Mon Nov 09 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Leonid Kanter <lkanter@cloudlinux.com> 0.4-6.4
- AC-1109: choosing an image for edited container doesn't creates a new one; refactoring
- pod api bugfix: "create" should return the same structure as "get", but "status" and "owner" were missing
- Show correct in settings for user & administrator
- Add settings link to user in dropdown navbar menu near logout
- AC-1394: no redirect to /login, if token exist
- AC-1434: fixed presentation of 'pod port' to a client
- Fix copy predefined app link bug in chrome browser
- AC-1433: show total limits on pod creation final step
- Fix fixed buttons bug in env step
- update image tables
- AC-1439: fixed broken time conversion in users pod page
- fix typo of persistent_volumes path
- AC-870: containers monitoring, plots are not dispayed
- small bugfix in environment variables validation;
- plots placeholders
- rerender pod page when pods collection fetched

* Fri Nov 06 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.4-6.3
- AC-1437: fixed null timezone error on user self-edit
- undelete user api endpoint
- Bug fix and improvement for upgrade system to do all db upgrades at once
- 

* Fri Nov 06 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com> 0.4-6.2
- added logs for terminated containers
- AC-1407: change timezone setting placement
- AC-1394: show postDescription with publicIP
- Added time fields to predefined_apps

* Fri Nov 06 2015 Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>  0.4-6.1
- fixed bug connected to missing revision
- AC-1399: Fix public IP allocation from /32 network

* Thu Nov 05 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>  0.4-6
- AC-1409 Restrict create users without existing package or without existing role
- remove style from scroll on nodelogs textarea
- remove preloader before ok button pressed
- Ntpd setup like at OpenStack
- AC-1422: default kube type now is defined in database
- AC-1368: Fix rendering detailed node page after collection.fetch
- AC-1404, AC-1423 user deletion workflow; bugfix; refactoring
- AC-1155: Fix username/email validation

* Wed Nov 04 2015 Igor Savenko <bliss@cloudlinux.com>  0.4-5.1
- brought back accidentally deleted logs fixes
- refactored some JS

* Wed Nov 04 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Michael Bagrov <mbagrov@cloudlinux.com>  0.4-5
- AC-1336: Fix bug with navigate on top after load-more event
- AC-1137: Fixed broken amazon-hosted installation with error if the wrong public key is added
- AC-1418: Fix FS limit script
- Fixed kuberdock.spec not to delete .ini at upgrade case.
- AC-1396: added validation for kube type in predefined app creation
- AC-1398: Fixed butons on env step if window has scroll
- 

* Tue Nov 03 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Michael Bagrov <mbagrov@cloudlinux.com>  0.4-4
- AC-1269 Fixed error message
- AC-1412: fixed description for invalid envvar name
- AC-1381: Fix copy-paste issue in 00041_update.py
- Improved cleaned up resource version handling
- AC-1352: two pods cannot use one Persistent Disk simultaneously
- small fix for AC-1352
- small bugfix: preloader on PD delete
- AC-1410: added node existence check to ceph.sh
- AC-1419: Fix bug in autogeneration 1-th podname
- Removed hardcoded error message at "add node" page.
- AC-1370: added quick workaround to ceph.sh when ceph.com key is unavailable
- AC-1340: Add the ability to copy the link pre app
- AC-1364:move PVolumes and PublicIPs menu to navbar menu

* Sun Nov 01 2015 Igor Savenko <bliss@cloudlinux.com>  0.4-3.1
- AC-819: bugfixes

* Fri Oct 30 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.4-3
- AC-1392: Fix empty response from ElasticSearch cluster
- AC-1316: pd isn't removed with container on final step of pod creation; other pd bugfix
- Fixed pod's ip migration from failed node. Fixed "Can not delete pod from failed node"
- AC-1393: Remove select & add placeholder & description to billing link script
- AC-1389: info message about maintance mode on 3rd part registries; bugfix; tests
- AC-1381: Fix FS limit applying to prevent container crash in some cases
- Install kuberdock.ini in post-install script, not in package itself
- Add style to Users app mobile version
- AC-1379: Add preloader to change tab event in settings app
- AC-1390: Add autogenerate podname function;
- AC-1369: Add style to post description in poditem page; Show control icons in podlist table
- AC-1358: add user hostingPanel for cPanel. Create hostingPanel user for cPanel(and other apps).
- User has role HostingPanel and password: hostingPanel. Add resource images for /api/images.
- Role HostingPanel allowed to access only resource images. Add base methods for create/delete roles and resource, and its permissions to the rbac/fixtures
- AC-1358: permissions,resource for predeffined_apps. Add permission and resource for predeffined_apps
- Anyone has permissions to GET to predeffined_apps, but only Admin can create, edit and delete.
- Add some style to logs area (pods/nodes)
- AC-1347: mark nodes with ceph client installed. Moved logic of nodes from api to kapi, added tests to kapi.nodes
- AC-1380: Implement preloader on Set up image step after clicking persistent checkbox
- Added resourceVersion handling in listeneres
- AC-1403: added check for pod existance in listeners.process_pods_event to prevent Integrity errors on saving pod state
- AC-1397: Add style to scroll node/pode logs
- AC-1350: On deleting free PD add confirmation dialog box
- AC-819: implemented node graphs rewrite node web-interface

* Tue Oct 27 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Aborilov Pavel <paborilov@cloudlinux.com>  0.4-2
- AC-1322: Force node's rsyslog to use hostname as KuberDock knows it
- AC-1251 Add style to predefined app create page
- AC-1344: hide start/stop button & chechboxes in container-list table
- Restrict to create pod when no such kube type on any node
- fix: pod create -> set up image -> "Persistent options must be set!"
- AC-1286: add pod nodes history selection
- AC-1321: Simplify logs API
- AC-1346: add reset-password command to manage.py
- AC-1303: inform user about registry inaccessibility during image search
- Fix breadcrumb in pre app, add notification to events add,remove,error, add modal dilog to delete app event
- AC-1255: Implement correct error messages & validation on front side
- Fix internal pods and kube type exists validation.
- AC-1372: add validation to environment variable name.
- AC-1376: all pods must have RC; bugfix
- Fix rare pod listener restart
- AC-1371: fix containers logs (frontend)
- AC-1373: added optional validation to custom variables in predefined apps templates
- forbid to create pods with more then 1 replicas
- AC-1374: Add template_id to pods API
- AC-1366: Show cpu/memory/disk on pod page where pod resources block

* Tue Oct 20 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>  0.4-1.3
- Add rendering node's page after node status update

* Tue Oct 20 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>  0.4-1.2
- Added rollback() when upgrade failed. Moved 00038_update to 00020_update due conflict.

* Tue Oct 20 2015 Igor Savenko <bliss@cloudlinux.com>  0.4-1.1
- kapi/helpers.py delattr bugfix

* Tue Oct 20 2015 Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.4-1
- Add some style to page configuring predefined app
- Add style to error page app/error.html
- AC-1208: user delete error
- Allow to start SUCCEEDED and FAILED pods. Implicid stop is called before.
- Added template_id to Pod. Moved kuberdock specific fields for yaml to kuberdock section
- AC-1248: further impovements
- container update bugfix
- Fix style in predefined app configure page

* Tue Oct 20 2015 Igor Savenko <bliss@cloudlinux.com> 0.3-5.6
- AC-1248: added exception handler to YAML parser

* Tue Oct 20 2015 Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.3-5.5
- api/usage return new data format
- AC-1155: Correct error message on username validation
- AC-1327: popup to confirm container update
- AC-1248: reworked unregistered user app logic

* Mon Oct 19 2015 Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.3-5.4
- AC-1251: Add style to predefined app list
- AC-1297: Replace `hostname -f` by `uname -n` in deploy.sh
- hide unverified https request warning
- AC-1247, AC-1248: further additions

* Sun Oct 18 2015 Igor Savenko <bliss@cloudlinux.com> 0.3-5.3
- implemented missed subroutine in kapi/predefined_apps.py

* Sun Oct 18 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.3-5.2
- AC-1244: Added kube type for internal services
- bugfix: sourceUrl; container page start/stop, status, container update; private images; tests
- AC-1280: Add style & icons to update container buttons
- AC-1248: implemented styleless page without any authorization.

* Fri Oct 16 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.3-5.1
- Hotfix add container bug on env step
- Add style to AC-1266
- Fixed yum output to be not so verbose
- AC-1184, AC-1186, settings -> edit profile validation and bugfix

* Fri Oct 16 2015 Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.3-5
- AC-833: added links for images
- AC-1278 set imagePullPolicy=Always to all containers
- AC-1183: added pause to login to private registry after failed login. Rework on images and unit tests
- Updated flannel to 0.5.3 + install kernel-devel on nodes
- Yaml api must reject strings or numbers as documents
- AC-1267: Add hash to PredefinedApp model
- AC-1269: fix gramatic mistake
- AC-1156: fix users control in userslist table
- AC-956: hide extra search icon
- Add check empty for timezone api
- Fixed SSE events
- AC-1267: Add 'name' to PredefinedApp model
- fix sourceUrl error in templates
- Output stdout and stderr throu pty. Now both channels can be seen.
  Reboot node from python, not from script.
  Fix systemd enable issue. Added auto status update in error case.
  Added message about node status during reboot.
- AC-1266: added system-wide settings api
- AC-1279: update container api; image api refactoring; bugfix
- AC-1183: added pause to login to private registry after failed login. Rework on images and unit tests
- Fix ntpd deploy error on nodes
- AC-1300: Use upgrade_node for setting FS quotas in 00026_update.py
- Fixed migration scripts sequence conflict
- AC-1263: Add error notify if username already exist
- AC-1226: hide add button if fields value not change in user edit template & profile edit template
- fix pods menu item for TrialUser in fixtures
- AC-1247: implemented predefined apps web-interface CRUD
- AC-1256, AC-1299, select image validation, bugfix
- Accept only allowed answers in kuberdock upgrade
- Forbid to add master as node
- Add validation to env step

* Mon Oct 12 2015 Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.3-4
- AC-1261: create pod with private image (frontend); disable cache for private repox
- AC-1264: Fix 00026_update.py for pods that are not running
- Add empty&templates Views to pods, nodes, ippool, publicIPs, Pers. Volumes
- AC-1147: rewritten persistent volumes web-interface logic
- Small refactoring users app & add preloaders to ippool app events
- AC-1090 AC-1030 AC-1260 AC-1252 AC-1258 AC-1262 AC-1209 pod creation final step fixes
- Added static files precompilation and compression

* Thu Oct 08 2015 Alex Tishin <atishin@cloudlinux.com>, Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.3-3
- AC-1113: various fixes for logs
- AC-1036
- AC-1126: Implemented rerunning failed node tasks
- AC-924, AC-1121, AC-1044, AC-1103, AC-1083, AC-1086, AC-1057, AC-1019, AC-1013, AC-1027, AC-855, AC-814, AC-927, AC-861
- AC-151: select image from private repo/registry; AC-1066: save/start; quay.io; small bugfix
- bugfix: delete stopped pod -> pod is already stopped error
- AC-796, AC-1158, AC-1152, AC-839, AC-926, AC-1151, AC-951
- AC-854: pod status updates fixed
- AC-1168 Added max kubes preference and validation
- AC-1178: Add menu item Pods for the TrialUser; small fix in tests
- AC-1168 Added max kubes preference and validation
- AC-1179: check images availability before creating a pod; api improvements; tests
- AC-1157: Log out locked user
- AC-1105: username was replaced with user id in PD names
- AC-628: Add information text if log is empty
- AC-1190: Remove # from podlist & containerlist
- deploy.sh: improved AWS checker
- Fixed usgi autoreload of kuberdock
- More robust validation for yaml
- AC-1167: Enable logs API authorization
- location fix in 401 error & notification position in podname validation
- AC-1196: login_required for logout
- AC-833: Add style to links
- AC-1180. Added command to run specified upgrade script.
- Fix listener respawn with 'containerID' key missing
- AC-1211: Remove oblosete /logs/ section from nginx config
- AC-1185: forbid locked users to perform any actions
- AC-1206: fix on user blocking
- AC-1111: deploy.sh, move fetching repositories after interactive section
- AC-1210 Add kube price to API output
- AC-1221: refresh cache
- AC-1115: Add timer to eventhandler pod & node app
- AC-1171: KuberDock stats ping back
- AC-791: Disk space limits in GB
- AC-1207: fix for unhandled exceptions from pstorage
- AC-1228: Set master time zone on nodes
- Add optional sourceUrl param to pod config
- AC-1235: User with 'Admin' role shouldn't have pods
- AC-1193 Introduce private imiges repo in kuberdock web
- fix pod without kuberdock-pod-uid error

* Thu Sep 24 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.3-2
- AC-884: Show PD size in table
- AC-1088: remove deprecated packages
- added upgrade script to kubernetes-1.0.3
- AC-1088: remove deprecated packages
- fix users and ippool
- Fixed very old update script

* Wed Sep 23 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.3-1.5
- AC-1079 Forbid admins to create pods
- logs bugfix, container create bugfix
- Small frontend fixes

* Tue Sep 22 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Michael Bagrov <mbagrov@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.3-1.4
- AC-1089: user creation api - now supports 'true' 'false' '0' '1' in boolean fields, supports field 'suspended', supports emails in username
- AC-984: Change error notification in podCreate steps & add preloader in nodeCreate step
- AC-1089: user creation api - fixed dropped username validation
- AC-841: Add notification if image name == 0 to firts step in create pode page
- AC-1052: fixes for elasticsearch containers - added some env vars, ES image replaced with new one, changed resources for log containers (revert)

* Mon Sep 21 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Michael Bagrov <mbagrov@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.3-1.3
- AC-987 Yaml api. Many validation improvemens. Small fixes
- AC-1087: A change of status brings an error
- add style email to userPage & add stop icon to container page
- user update: ignore unknown fields
- AC-1052: fixes for elasticsearch containers - added some env vars, ES image replaced with new one, changed resources for log containers
- AC-1081: forbid user to see info about other users and global ip-pool
- Part of renaming kuberdock_upgrade.py to kuberdock-upgrade
- Fixed 00007_update.py for new validation logic.

* Fri Sep 18 2015 Igor Savenko <bliss@cloudlinux.com> 0.3-1.2
- Updated deploy scripts
- deploy.sh bugfix (extra quotation)
- Hot bug fix for upgrade system
- Deploy.sh: Wrong CEPH credentials should break the installation process
- Hide username field from user edit template

* Thu Sep 17 2015 Igor Savenko <bliss@cloudlinux.com> 0.3-1.1
- CEPH PD bugfixes
- Returned pod_create.js triggers

* Thu Sep 17 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.3-1
- AC-1066: docker registry v2 search
- AC-852: front-end email validation fix
- Added check before adding node that kuberdock has correct settings file.
- assets.py: removed obsoletes
- AC-1048 create container with persistent storage bugfix
- AC-1064: Added workaround for persistentDrive s to be kept

* Wed Sep 16 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-36.1
- use old usage api format, 'cause the new one needs changes in whmcs addon
- AC-1072. Fixed deploy scripts
- AC-1058: fix public & persistantDisk checkboxes view after creating pod
- AC-1041: internal pods use localStorage; hostPath is allowed only for kuberdock-internal
- AC-1065: Getting images list and picking one are completely rewritten
- Fixed going back from a pending pod ports-volumes pages

* Tue Sep 15 2015 Aleksandr Kuznetsov <akuznetsov@cloudlinux.com>, Leonid Kanter <lkanter@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-36
- Renamed minion to node
- Fix missing " in deploy.sh
- Small first part of api cleanup
- Fixed pod collection tests.
- Added privileged mode for rbd-backed pods. Added updates script to enable privileged mode
- AC-849: Allow master to access ElasticSearch on nodes
- add node creation to AWS-deploy scripts
- AC-822: Rename final step in add pod; small slyles fixes in podpage
- add testing option to aws-deploy scripts
- AC-1028: Added ability to edit pending containers
- AC-599: usage statistics for IP and PD; tests; bugfix
- AC-1000: predefined apps template api
- AC-972, AC-1026, AC-1040, AC-1053
- AC-636: added docker_id to container_state. added API methods to select logs from elasticsearch
- Explicit kuberdock restart even if no new upgrade scripts found and applied

* Thu Sep 10 2015 Alex Tishin <atishin@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-35.1
- AC-665: reset values button (add container, third step - envvars)
- AC-969: Update logging containers
- AC-831: fix grammar mistake
- AC-866: Add text to breadcrumbs in user edit page
- AC-821, AC-805: Add new fields to user create/edit page, some design fix in user page & ippool page
- AC-614 Fixed trial user can't create pods
- AC-1003: user package change; bugfix; api tests
- AC-724: Add notifocation to bulk operation in mainenance mode
- Added update script for clearing dockerfile cache
- Small bugfix related to not all nodes are ceph-aware when polled for ceph-volumes
- AC-896: On pod save error returns stripped attributes

* Mon Sep 07 2015 Alex Tishin <atishin@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-35
- small changes in deploy.sh, --cleanup section
- Fix missing \ in deploy.sh
- kubedock/api/nodes.py small bugfixes
- AC-899: Add IP-pool pagination
- AC-890: remove default packages, except "basic"; rename "basic" to "Standard package"; small bugfix
- AC-871: Node's page=>Reinstall button doesn't work
- Fixed update system with fixed updates
- First part of renaming kuberdock_upgrade.py utility
- small changes in manage.py createdb (Standard package id)
- bugfix in api/images (caching was broken)
- AC-790 Sometimes users page doesn't displayed
- AC-835: persistent local storage
- deploy.sh bugfix (added quotes around exportable variables)
- deploy.sh small fixes (added installation of aws-cli for aws setup)
- AC-792: node name validation - 404
- AC-593 Billing API, changes for kube requests
- AC-974: In final step kubeType and kubeQuantity dropdowns always kept the same value (first). Fixed.
- AC-781: when ENTRYPOINT and CMD mixed to one field some hard-predictable bugs occur. For instance, mariadb failed to run. Resolved
- Send SSE events per user and to common channel for admins. Fixed node status handling. Faster pods/nodes status updates (removed polling kubernetes).
- AC-804: User validation + tests
- AC-803: username has been taken;
- AC-844: username validation;
- AC-798: XSS through username field

* Mon Aug 31 2015 Michael Bagrov <mbagrov@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-34
- AC-906: CEPH-client installation procedure simplification
- AC-881 Display package payment type
- AC-917 Pod's page=>Final step of creating container, MB is absent
- AC-836: iptables rules to protect elasticsearch from unauthorized access
- AC-894: allow any symbol in Pod.name
- AC-808: Added workaround to deploy.sh to get ROUTE_TABLE_ID when started manually

* Wed Aug 26 2015 Igor Savenko <bliss@cloudlinux.com> 0.2-33.3
- Added waiting for ebs is available after creation

* Wed Aug 26 2015 Igor Savenko <bliss@cloudlinux.com> 0.2-33.2
- small bugfix in kubedock/kapi/podcollection.py

* Wed Aug 26 2015 Igor Savenko <bliss@cloudlinux.com> 0.2-33.1
- small bugfix to AWS persistent storage

* Wed Aug 26 2015 Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com> 0.2-33
- AC-892: Add error if podname not less 64 characters & add success notification if correct
- AC-786: Disk space limits in MB (again)
- AC-581 Added package field for user interface
- Added jasmine to settings & users apps
- AC-799, AC-856, AC-857, AC-859, AC-888 - orphography correction
- AC-748: Unit-test python podcollection._check_trial
- AC-633 Display package name on user page
- AC-891: deploy.sh adds MONITORS and KEYRING_PATH options to ceph_settings.py
- AC-842: Research how to mount persistent storage to AWS
- AWS persistent storage moved to native implementation

* Fri Aug 21 2015 Igor Savenko <bliss@cloudlinux.com> 0.2-32
- Added upgrade script for changing schema

* Wed Aug 19 2015 Alex Tishin <atishin@cloudlinux.com>, Michail Bagrov <mbagrov@cloudlinux.com, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-31
- AC-836: Iptables script to close the dangerous ports from outside
- AC-862: Get Dockerfile from new docker hub
- AC-733: Unit-test PodCollection._get_pods; rafactoring _get_pods and _is_related
- old unit-tests fix (podcollection)
- First attempt to upgrade kuberdock
- Add jasmine to Ippool application

* Mon Aug 17 2015 Alex Tishin <atishin@cloudlinux.com>, Sergey Gruntovsky <sgruntovsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-30
- Tests for _stop_pod
- AC-791: show disc space in final step on add pod
- AC-784: Add borders to errors fields& some small design
- reworked pods list page functionality
- just another pods_app refactoring completion
- Improved update system with auto-reloading of upgrade utility
- AC-728: PodCollection.add unit-tests
- renamed t/index.html to t/pod_index.html and modified main.py accordingly
- Small fix kuberdock_upgrade.py
- AC-809: deploy.sh --cleanup; more elegant args parsing
- AC-744: Unit-test python (pod). Method _do_container_action
- AC-828: implemented for ceph backend
- AC-786: Disk space limits in MB

* Sun Aug 09 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-29
- AC-782: Add bulk run/stop pods in podlist
- Tests for _start_pod

* Thu Aug 06 2015 Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com> 0.2-28
- AC-778: Add validation to user create page
- AC-573: Show container price
- AC-729 Unit-test python (pod). Method get
- AC-730 Unit-test python (pod). Method get_by_id
- updated js tests
- AC-779: Add new design to notification windows
- AC-776: Remove extra Views.ConsoleView; AC-774: Merge two views: Views.NodeFindStep and Views.NodeFinalStep, remove extra styles & small design fixes

* Wed Aug 05 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-27
- Tests for make_namespace
- AC-701: Fix bug with display networks list after adding
- AC-724: Prepare design notification windows & remove extra code from users, notifications application, fix some design bug in nodelist page
- Tests for _get_namespaces and _drop_namespace. Switch to patcher in tests. Small improvment.
- Fix for maintenance mode.
- refactored pod_list. Breadcrumbs moved to separate view/template.
- added jasmine unit tests. pods.less and settings_app/app.js small bugfixes
- AC-724: Add notification in maintenance mode to nodes&pods application

* Mon Aug 03 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-26
- AC-721: Fix style notifi message on user create/edit pages
- Small improve of maintenance mode message
- Make kuberdock_upgrade.py executable
- Exit if selinux not enabled on node. Clean up old code.
- introduces jasmine-based unit testing
- Fix for get_api_url bug with special pod name.
- Tests for run_service and get_api_url
- AC-687: Add new design to last step in add pod

* Wed Jul 29 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-25
- Added exception handler to core/ssh_connect to handle permission errors
- Simple maintenance mode implementetion. Pods and nodes are now protected.
- sqlalchemy workaround
- require.js dependencies loader bugfix
- Hotfix cahnge logo
- AC-749: Fix setup node disk quota

* Mon Jul 27 2015 Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-24
- removed logo shrinking
- Fix container states not saved
- added firewalld rules for cpanel flanneld and kube-proxy
- replaced logos

* Mon Jul 27 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.2-23
- deploy.sh hotfix

* Mon Jul 27 2015 Alex Tishin <atishin@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-22
- AC-715: Update cluster DNS containers
- Fixed node deploy js error.
- Switch to listen events via WebSockets, add listen fabric func.
- raised flannel to 0.5.1
- modified nginx configs
- AC-597 Api usage change kube_id data type.
- AC-711 Add all default kubes to standart package
- Added -u --udp-backend option to deploy.sh to use udp for flannel
- AC-717: Fix node_install.sh due to node reboot

* Sat Jul 25 2015 Alex Tishin <atishin@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.2-21
- Fixed error during node addition. Now ip is not required and resolved from hostname as expected.
- AC-659: FS limits (+overlayfs/-selinux)

* Fri Jul 24 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-20
- AC-591 Package rename setup_fee
- Added checkpoints to updates.
- AC-249: Some fix in design in IPPoot page
- Escape bad chars in user name for namespace

* Thu Jul 23 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-19
- Remove getFreeHost logic. Now ip allocated on server during pod creation.
- Fix AC-702
- Logs pods now replacas.
- fixed stat charts for v1
- Fixed flanneld 0.5.1

* Wed Jul 22 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.2-18
- Full switch to kubernetes 1.0.1 and api v1 except kubestat.py and PD related code.
- Refactored get_api_url
- apiVersion is not hardcoded anymore

* Tue Jul 21 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-17
- AC-680: Hide extra links in settings page to admin
- Upgrade to 20.3 kubernetes. Fixed some kuberdock errors, but not all.
- Kuberdock-internal pods are disabled due bugs with namespaces CRUD.
- Start Posgresql before uwsgi
- AC-667: Hide extra elements in add container, last step
- Fix User View Mode Design

* Sun Jul 19 2015 Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-16
- AC-602: Fixed design bugs in bulk operation on podlist page & podItem page
- AC-663: Add text if not have collection in settings, fix bug with modal dilog position
- AC-491: added nginx configs, selinux module for nginx, containers in docker bridge are isolated by owners

* Thu Jul 16 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com>, Ruslan Rakhmanberdiev <rrakhmanberdiev@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.2-15
- AC-643 User suspend status
- AC-631: Show only checked network ip(s)
- Switch parse_pods_statuses to v1beta3
- AC-621 Display correct kube count on pod page
- Added reenabling feature to restart service helpers
- AC-660: mount point problem
- AC-622 Display actual kube data on single pod page
- 

* Wed Jul 15 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-14
- Added explicit docker installation on node
- Fix package version detection
- AC-650: Add style to User View Mode

* Thu Jul 09 2015 Igor Savenko <bliss@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-13
- AC-612: Added unit tests for 'PodCollection' method 'delete'
- AC-496, AC-501, AC-512, AC-607, AC-514, Add pending animation, add icons to podcontrol menu, design fixes, add icons to user statuses
- Fix bug with remove environment variables fields
- AC-277: Add filter to podlist&nodelist; Hotfix in nodelist with dublicated node
- New upgrade system, now can handle node upgrades too.
- Supports local install and many more console commands.
- Upgrade to fabric 1.10.2


* Fri Jul 03 2015 Igor Savenko <bliss@cloudlinux.com>, Leonid Kanter <lkanter@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-12
- AC-474: User persistent storage page
- add aws-kd-deploy
- AC-552: Add bulk operation in container list table
- AC-515, AC-516, AC-588: Design fixes
- Moved ippool logic from view to kapi
- AC-600: Implemeted basic functionality. Shows only used IPs

* Wed Jul 01 2015 Igor Savenko <bliss@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.2-11
- AC-335: Add validation to dublicates containers ports
- Added FakeSessionInterface

* Wed Jul 01 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com> 0.2-10
- Fixed require.js cache problem

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
- AC-509 WHMCS. Persistent storage in GB

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

* Fri May 29 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>  0.1-53
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

* Wed Apr 22 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-30
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

