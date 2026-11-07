"""Cross-provider identities, episode requests and movie collection metadata."""
from alembic import op
import sqlalchemy as sa
revision='b6c432fd734d'
down_revision='a5b321ec623c'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('show_external_id',sa.Column('provider',sa.String(),primary_key=True),sa.Column('external_id',sa.String(),primary_key=True),sa.Column('show_id',sa.Uuid(),sa.ForeignKey('show.id',ondelete='CASCADE'),nullable=False))
    op.create_index('ix_show_external_id_show_id','show_external_id',['show_id'])
    # The PostgreSQL enum already belongs to existing movie/season request columns.
    from sqlalchemy.dialects.postgresql import ENUM
    quality=ENUM('uhd','fullhd','hd','sd','unknown',name='quality',create_type=False)
    op.create_table('episode_request',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('episode_id',sa.Uuid(),sa.ForeignKey('episode.id',ondelete='CASCADE'),nullable=False),sa.Column('requested_by_id',sa.Uuid(),sa.ForeignKey('user.id',ondelete='SET NULL')),sa.Column('authorized_by_id',sa.Uuid(),sa.ForeignKey('user.id',ondelete='SET NULL')),sa.Column('authorized',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('min_quality',quality,nullable=False),sa.Column('wanted_quality',quality,nullable=False),sa.UniqueConstraint('episode_id','wanted_quality'))
    op.create_index('ix_episode_request_episode_id','episode_request',['episode_id'])
    op.create_table('movie_collection',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('name',sa.String(),nullable=False),sa.Column('overview',sa.String(),nullable=False),sa.Column('poster_url',sa.String()),sa.Column('parts',sa.JSON(),nullable=False),sa.Column('source',sa.String(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    op.drop_table('movie_collection');op.drop_table('episode_request');op.drop_table('show_external_id')
