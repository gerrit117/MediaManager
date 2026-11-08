"""Invitation accounts, request-only catalogue records and seasonal accounting."""
from alembic import op
import sqlalchemy as sa
revision='c7d543ae845e'
down_revision='b6c432fd734d'
branch_labels=None
depends_on=None

def upgrade():
    for table in ['movie','show']:op.add_column(table,sa.Column('request_only',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('request_usage',sa.Column('scope_key',sa.String(100),nullable=True))
    op.create_index('ix_request_usage_user_scope','request_usage',['user_id','scope_key'])
    op.execute("UPDATE request_usage u SET scope_key='movie:'||r.movie_id::text FROM movie_request r WHERE u.request_id=r.id")
    op.execute("UPDATE request_usage u SET scope_key='season:'||r.season_id::text FROM season_request r WHERE u.request_id=r.id")
    op.execute("UPDATE request_usage u SET scope_key='season:'||e.season_id::text FROM episode_request r JOIN episode e ON e.id=r.episode_id WHERE u.request_id=r.id")
    op.create_table('account_invitation',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('digest',sa.String(64),nullable=False,unique=True),sa.Column('email',sa.String()),sa.Column('created_by_id',sa.Uuid(),sa.ForeignKey('user.id',ondelete='SET NULL')),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('used_by_id',sa.Uuid(),sa.ForeignKey('user.id',ondelete='SET NULL')),sa.Column('used_at',sa.DateTime(timezone=True)),sa.Column('revoked',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_table('account_security_rate',sa.Column('key',sa.String(64),primary_key=True),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    # Each user tracks their own request; download workers still reuse shared files/jobs.
    for table,first in [('movie_request','movie_id'),('season_request','season_id'),('episode_request','episode_id')]:
        bind=op.get_bind();constraints=sa.inspect(bind).get_unique_constraints(table)
        for constraint in constraints:
            if set(constraint['column_names'])=={first,'wanted_quality'}:op.drop_constraint(constraint['name'],table,type_='unique')
        op.create_unique_constraint('uq_'+table+'_user_quality',table,[first,'wanted_quality','requested_by_id'])

def downgrade():
    # Refuse to discard requests when multiple users requested the same title.
    for table,first in [('movie_request','movie_id'),('season_request','season_id'),('episode_request','episode_id')]:
        if op.get_bind().scalar(sa.text(f'SELECT count(*) FROM (SELECT {first},wanted_quality FROM {table} GROUP BY {first},wanted_quality HAVING count(*)>1) q')):raise RuntimeError('Cannot downgrade without merging per-user requests first.')
        op.drop_constraint('uq_'+table+'_user_quality',table,type_='unique');op.create_unique_constraint(table+'_'+first+'_wanted_quality_key',table,[first,'wanted_quality'])
    op.drop_table('account_security_rate');op.drop_table('account_invitation');op.drop_index('ix_request_usage_user_scope',table_name='request_usage');op.drop_column('request_usage','scope_key')
    for table in ['movie','show']:op.drop_column(table,'request_only')
