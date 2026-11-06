"""Monthly request policies and persistent usage ledger."""
from alembic import op
import sqlalchemy as sa
revision='83e109ca401a'
down_revision='2c61f662ca9e'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('user',sa.Column('monthly_request_limit',sa.Integer(),nullable=True))
    op.add_column('user',sa.Column('auto_approve_requests',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_check_constraint('user_nonnegative_monthly_limit','user','monthly_request_limit IS NULL OR monthly_request_limit >= 0')
    op.create_table('request_usage',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('user.id',ondelete='SET NULL')),sa.Column('request_id',sa.Uuid(),unique=True,nullable=False),sa.Column('kind',sa.String(16),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_request_usage_user_id','request_usage',['user_id'])
    op.create_index('ix_request_usage_created_at','request_usage',['created_at'])

def downgrade():
    op.drop_table('request_usage')
    op.drop_constraint('user_nonnegative_monthly_limit','user',type_='check')
    op.drop_column('user','auto_approve_requests');op.drop_column('user','monthly_request_limit')
