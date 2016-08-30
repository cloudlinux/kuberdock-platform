"""add_settings_groups

Revision ID: 8d3aed3e74c
Revises: 370f6c5fafff
Create Date: 2016-08-25 18:12:06.124915

"""

# revision identifiers, used by Alembic.
revision = '8d3aed3e74c'
down_revision = '370f6c5fafff'


from alembic import op
import sqlalchemy as sa

def upgrade():
    conn = op.get_bind()
    op.add_column(
        'system_settings', sa.Column('setting_group', sa.Text, default=''))
    conn.execute(
        "UPDATE system_settings SET setting_group='billing'"
        "WHERE id >= 1 AND id <= 5")
    conn.execute(
        "UPDATE system_settings SET setting_group='general'"
        "WHERE id >= 6 AND id <= 9")
    conn.execute(
        "UPDATE system_settings SET setting_group='general'"
        "WHERE id = 14")
    conn.execute(
        "UPDATE system_settings SET setting_group='domain'"
        "WHERE id >= 10 AND id <= 13")
    conn.execute(
        """UPDATE system_settings SET """
        """options=('["No provider", "cpanel_dnsonly"]') WHERE id= 10""")
    conn.execute("UPDATE system_settings SET value='No provider' WHERE id= 10")
    conn.execute(
        "UPDATE system_settings SET label='Select DNS provider' WHERE id= 10")
    conn.execute(
        "UPDATE system_settings SET label='Link to cPanel'  WHERE id= 11")
    conn.execute(
        "UPDATE system_settings SET placeholder='e.g. https://example.com'"
        "WHERE id= 11")
    conn.execute(
        "UPDATE system_settings SET label='cPanel admin username' WHERE id= 12"
    )
    conn.execute(
        "UPDATE system_settings SET "
        "placeholder='user with rights to configure DNS zones'  WHERE id= 12")
    conn.execute(
        "UPDATE system_settings SET label='cPanel access key'  WHERE id= 13")
    conn.execute(
        "UPDATE system_settings SET "
        "placeholder='remote access key from cPanel'  WHERE id= 13")
def downgrade():
    conn = op.get_bind()
    op.drop_column('system_settings', 'setting_group')
    conn.execute("UPDATE system_settings SET options='' where id= 10")
    conn.execute("UPDATE system_settings SET value=''  WHERE id= 10")
    conn.execute(
        "UPDATE system_settings SET label='Select your DNS management system'"
        "WHERE id= 10")
    conn.execute(
        "UPDATE system_settings SET label='cPanel URL for DNS management'"
        "WHERE id= 11")
    conn.execute(
        "UPDATE system_settings SET "
        "placeholder='Enter URL for cPanel which serve your DNS records'"
        "WHERE id= 11")
    conn.execute(
        "UPDATE system_settings SET "
        "label='cPanel user name for DNS management'  WHERE id= 12")
    conn.execute(
        "UPDATE system_settings SET "
        "placeholder='Enter user for cPanel which serve your DNS records'"
        "WHERE id= 12")
    conn.execute(
        "UPDATE system_settings SET "
        "label='cPanel user token for DNS management'  WHERE id= 13")
    conn.execute(
        "UPDATE system_settings SET "
        "placeholder='Enter token for cPanel which serve your DNS records'"
        "WHERE id= 13")
