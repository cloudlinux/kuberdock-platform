import json
from uuid import uuid4

from kubedock.api import create_app
from kubedock.core import db
from kubedock.models import User, Pod
from kubedock.billing.models import Package, Kube, ExtraTax
from kubedock.rbac.fixtures import add_permissions
from kubedock.rbac.models import Role
from kubedock.static_pages.fixtures import generate_menu


def get_dns_pod_config(uuid, domain='kuberdock', ip='10.254.0.10'):
    return {
        "node": None,
        "lastAddedImage": "gcr.io/google-containers/skydns",
        "name": "kuberdock-dns",
        "replicas": 1,
        "cluster": False,
        "restartPolicy": {
            "always": {}
        },
        "volumes": [],
        "kube_type": 0,
        "id": uuid,
        "containers": [
            {
                "terminationMessagePath": None,
                "name": "etcd",
                "workingDir": "",
                "image": "quay.io/coreos/etcd:v2.0.3",
                "volumeMounts": [],
                "command": [
                    "-listen-client-urls=http://0.0.0.0:2379,http://0.0.0.0:4001",
                    "-initial-cluster-token=skydns-etcd",
                    "-advertise-client-urls=http://127.0.0.1:4001"
                ],
                "env": [],
                "ports": [],
                "kubes": 1
            },
            {
                "terminationMessagePath": None,
                "name": "kube2sky",
                "workingDir": "",
                "image": "gcr.io/google-containers/kube2sky:1.1",
                "volumeMounts": [],
                "command": [
                    "-domain={0}".format(domain),
                ],
                "env": [],
                "ports": [],
                "kubes": 1
            },
            {
                "terminationMessagePath": None,
                "name": "skydns",
                "workingDir": "",
                "image": "gcr.io/google-containers/skydns:2015-03-11-001",
                "volumeMounts": [],
                "command": [
                    "-machines=http://127.0.0.1:4001", "-addr=0.0.0.0:53",
                    "-domain={0}.".format(domain)
                ],
                "env": [],
                "ports": [
                    {
                        "isPublic": False,
                        "protocol": "udp",
                        "containerPort": 53
                    }
                ],
                "kubes": 1
            }
        ],
        "portalIP": ip
    }


if __name__ == '__main__':
    app = create_app()
    ac = app.app_context()
    ac.push()
    db.drop_all()
    db.create_all()

    # Create default packages and kubes
    # Package and Kube with id=0 are default
    # end must be undeletable (always present with id=0) for fallback
    k1 = Kube(id=0, name='Standart kube', cpu=700, cpu_units='KCU',
              memory=64, memory_units='MB', disk_space='0', total_traffic=0)
    k2 = Kube(name='High CPU', cpu=1400, cpu_units='KCU',
              memory=64, memory_units='MB', disk_space='0', total_traffic=0)
    k3 = Kube(name='Hight memory', cpu=700, cpu_units='KCU',
              memory=254, memory_units='MB', disk_space='0', total_traffic=0)
    db.session.add_all([k1, k2, k3])
    db.session.commit()

    p1 = Package(id=0, name='basic', kube=k1, amount=1,
                 currency='USD', period='hour')
    p2 = Package(id=1, name='professional', kube=k2, amount=2,
                 currency='USD', period='hour')
    p3 = Package(id=2, name='enterprise', kube=k3, amount=3,
                 currency='USD', period='hour')
    e1 = ExtraTax(id=0, key='public_ip', name='public ip', amount=6,
                  currency='USD', period='hour')
    db.session.add_all([p1, p2, p3, e1])
    db.session.commit()

    add_permissions()

    # Create all roles with users that has same name and password as role_name.
    # Useful to test permissions.
    # Delete all users from setup KuberDock. Only admin must be after install.
    # AC-228
    # for role in Role.all():
    #     u = User.filter_by(username=role.rolename).first()
    #     if u is None:
    #         u = User.create(username=role.rolename, password=role.rolename,
    #                         role=role, package=p, active=True)
    #         db.session.add(u)
    # db.session.commit()

    # Special user for convenience to type and login
    r = Role.filter_by(rolename='Admin').first()
    u = User.filter_by(username='admin').first()
    if u is None:
        u = User.create(username='admin', password='admin', role=r, package=p1,
                        active=True)
        db.session.add(u)
    kr = Role.filter_by(rolename='User').first()
    ku = User.filter_by(username='kuberdock-internal').first()
    if ku is None:
        ku = User.create(username='kuberdock-internal', password='', role=kr,
                         first_name='KuberDock Internal', active=True)
        db.session.add(ku)
    temp_uuid = str(uuid4())
    dns_config = get_dns_pod_config(temp_uuid, 'kuberdock', '10.254.0.10')
    dns_pod = Pod(
        name='kuberdock-dns',
        config=json.dumps(dns_config),
        id=temp_uuid,
        status='pending',
        owner=ku,
    )
    db.session.add(dns_pod)
    db.session.commit()

    generate_menu()

    ac.pop()
