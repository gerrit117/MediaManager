"""Store each account's optional interface language."""
from alembic import op
import sqlalchemy as sa
revision = "d8e654bf956f"
down_revision = "c7d543ae845e"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("user", sa.Column("preferred_language", sa.String(2), nullable=True))

def downgrade():
    op.drop_column("user", "preferred_language")
