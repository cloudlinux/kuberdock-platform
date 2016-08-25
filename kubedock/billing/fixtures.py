from kubedock.core import db
from kubedock.billing.models import Package, Kube, PackageKube


def add_kubes_and_packages():
    # Create default packages and kubes
    # Package and Kube with id=0 are default
    # and must be undeletable (always present with id=0) for fallback
    k_internal = Kube(id=Kube.get_internal_service_kube_type(),
                        name='Internal service', cpu=.02, cpu_units='Cores',
                        memory=64, memory_units='MB', disk_space=1,
                        disk_space_units='GB', included_traffic=0)
    k1 = Kube(id=0, name='Tiny', cpu=.12, cpu_units='Cores',
                memory=64, memory_units='MB', disk_space=1,
                disk_space_units='GB', included_traffic=0)
    k2 = Kube(name='Standard', cpu=.25, cpu_units='Cores',
                memory=128, memory_units='MB', disk_space=1,
                disk_space_units='GB', included_traffic=0, is_default=True)
    k3 = Kube(name='High memory', cpu=.25, cpu_units='Cores',
                memory=256, memory_units='MB', disk_space=3,
                disk_space_units='GB', included_traffic=0)

    p1 = Package(id=0, name='Standard package', first_deposit=0,
                    currency='USD', period='month', prefix='$',
                    suffix=' USD', is_default=True)
    pk1 = PackageKube(package=p1, kube=k1, kube_price=0)
    pk2 = PackageKube(package=p1, kube=k2, kube_price=0)
    pk3 = PackageKube(package=p1, kube=k3, kube_price=0)
    db.session.add_all([k1, k2, k3, p1, pk1, pk2, pk3, k_internal])

    db.session.commit()
