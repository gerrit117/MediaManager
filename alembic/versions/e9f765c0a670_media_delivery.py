"""Release protection, replacement manifests, request lifecycle and Web Push."""
from alembic import op
import sqlalchemy as sa
revision='e9f765c0a670'
down_revision='d8e654bf956f'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('release_lock',sa.Column('kind',sa.String(12),primary_key=True),sa.Column('media_id',sa.Uuid(),primary_key=True))
    op.create_table('release_replacement',sa.Column('job_id',sa.Uuid(),sa.ForeignKey('torrent.id',ondelete='CASCADE'),primary_key=True),sa.Column('kind',sa.String(12),nullable=False),sa.Column('media_id',sa.Uuid(),nullable=False),sa.Column('manifest',sa.JSON(),nullable=False),sa.Column('status',sa.String(20),nullable=False))
    op.create_table('account_notification_preference',sa.Column('user_id',sa.Uuid(),sa.ForeignKey('user.id',ondelete='CASCADE'),primary_key=True),sa.Column('categories',sa.JSON(),nullable=False))
    op.create_table('account_push_subscription',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('user.id',ondelete='CASCADE'),nullable=False),sa.Column('endpoint_hash',sa.String(64),nullable=False,unique=True),sa.Column('subscription',sa.JSON(),nullable=False))
    op.create_index('ix_account_push_subscription_user_id','account_push_subscription',['user_id'])
    op.create_table('request_notification_state',sa.Column('kind',sa.String(12),primary_key=True),sa.Column('request_id',sa.Uuid(),primary_key=True),sa.Column('state',sa.String(20),nullable=False),sa.Column('rejected',sa.Boolean(),nullable=False),sa.Column('reason',sa.String(),nullable=True),sa.Column('emby_available',sa.Boolean(),nullable=True),sa.Column('first_seen',sa.DateTime(timezone=True),nullable=False))
    op.create_table('account_notification_delivery',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('event_key',sa.String(200),nullable=False),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('user.id',ondelete='CASCADE'),nullable=False),sa.Column('channel',sa.String(10),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('next_attempt',sa.DateTime(timezone=True),nullable=False),sa.Column('sent_at',sa.DateTime(timezone=True),nullable=True),sa.Column('error',sa.String(),nullable=True),sa.UniqueConstraint('event_key','user_id','channel'))
    op.create_table('emby_media_match',sa.Column('kind',sa.String(12),primary_key=True),sa.Column('media_id',sa.Uuid(),primary_key=True),sa.Column('status',sa.String(24),nullable=False),sa.Column('emby_ids',sa.JSON(),nullable=False),sa.Column('evidence',sa.JSON(),nullable=False),sa.Column('checked_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    for table in ['emby_media_match','account_notification_delivery','request_notification_state','account_push_subscription','account_notification_preference','release_replacement','release_lock']:op.drop_table(table)
