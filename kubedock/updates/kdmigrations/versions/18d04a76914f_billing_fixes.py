"""Package prefix and suffix length; nullable fix for Package, Kube, PackageKube

Revision ID: 18d04a76914f
Revises: 241a7b04a9ff
Create Date: 2015-12-02 18:14:13.249876

"""

# revision identifiers, used by Alembic.
revision = '18d04a76914f'
down_revision = '241a7b04a9ff'

from alembic import op
import sqlalchemy as sa

Session = sa.orm.sessionmaker()
Base = sa.ext.declarative.declarative_base()


class PackageKube(Base):
    __tablename__ = 'package_kube'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, nullable=False)
    package_id = sa.Column(sa.Integer, sa.ForeignKey('packages.id'))
    kube_id = sa.Column(sa.Integer, sa.ForeignKey('kubes.id'))


def upgrade():
    op.alter_column('kubes', 'name', existing_type=sa.VARCHAR(length=64),
                    nullable=False)
    op.create_index('one_default', 'kubes', ['is_default'], unique=True,
                    postgresql_where=sa.text(u'kubes.is_default IS true'))
    op.drop_constraint(u'kubes_is_default_key', 'kubes', type_='unique')
    op.alter_column('packages', 'name', existing_type=sa.VARCHAR(length=64),
                    nullable=False)
    op.alter_column('packages', 'prefix', existing_type=sa.VARCHAR(),
                    nullable=False)
    op.alter_column('packages', 'suffix', existing_type=sa.VARCHAR(),
                    nullable=False)

    session = Session(bind=op.get_bind())
    session.query(PackageKube).filter(sa.or_(
        PackageKube.package_id.is_(None), PackageKube.kube_id.is_(None),
    )).delete()
    session.commit()

    op.alter_column('package_kube', 'kube_id', existing_type=sa.INTEGER(),
                    nullable=False)
    op.alter_column('package_kube', 'package_id', existing_type=sa.INTEGER(),
                    nullable=False)


def downgrade():
    op.alter_column('package_kube', 'package_id', existing_type=sa.INTEGER(),
                    nullable=True)
    op.alter_column('package_kube', 'kube_id', existing_type=sa.INTEGER(),
                    nullable=True)
    op.alter_column('packages', 'suffix', existing_type=sa.String(length=16),
                    nullable=True)
    op.alter_column('packages', 'prefix', existing_type=sa.String(length=16),
                    nullable=True)
    op.alter_column('packages', 'name', existing_type=sa.VARCHAR(length=64),
                    nullable=True)
    op.create_unique_constraint(u'kubes_is_default_key', 'kubes', ['is_default'])
    op.drop_index('one_default', table_name='kubes')
    op.alter_column('kubes', 'name', existing_type=sa.VARCHAR(length=64),
                    nullable=True)
