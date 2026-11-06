"""Track existing media without moving source files."""
from alembic import op
import sqlalchemy as sa
revision = '94a210db512b'
down_revision = '83e109ca401a'
branch_labels = None
depends_on = None

def upgrade():
    for table in ('movie_file', 'season_file'):
        op.add_column(table, sa.Column('source_files', sa.JSON(), nullable=True))

def downgrade():
    for table in ('movie_file', 'season_file'):
        op.drop_column(table, 'source_files')
