"""Monitor aired episodes and preserve submission claims across restarts."""
from alembic import op
import sqlalchemy as sa
revision='a5b321ec623c'
down_revision='94a210db512b'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('show',sa.Column('monitor_from',sa.Date(),nullable=True))
    op.add_column('show',sa.Column('monitor_checked_at',sa.DateTime(timezone=True),nullable=True))
    op.execute("UPDATE show SET monitor_from=(CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Berlin')::date WHERE continuous_download=true")
    op.add_column('episode',sa.Column('air_date',sa.Date(),nullable=True))
    op.add_column('season_file',sa.Column('episode_numbers',sa.JSON(),nullable=True))
    op.create_table('episode_download',sa.Column('episode_id',sa.Uuid(),sa.ForeignKey('episode.id',ondelete='CASCADE'),primary_key=True),sa.Column('torrent_id',sa.Uuid(),sa.ForeignKey('torrent.id',ondelete='SET NULL')),sa.Column('checked_at',sa.DateTime(timezone=True),nullable=True),sa.Column('status',sa.String(),nullable=False),sa.Column('release_title',sa.String(),nullable=False),sa.Column('error',sa.String()))

def downgrade():
    op.drop_table('episode_download')
    op.drop_column('season_file','episode_numbers')
    op.drop_column('episode','air_date')
    op.drop_column('show','monitor_checked_at');op.drop_column('show','monitor_from')
