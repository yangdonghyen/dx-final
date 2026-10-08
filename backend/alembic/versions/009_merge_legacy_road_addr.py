"""Marker for a revision that was applied to the shared DB outside this repository.

The database was already stamped `009_merge_legacy_road_addr`, but the original
file is not in this project. The only schema difference found on the DB is
`places.road_address`; its exact type is unknown here, so this marker does not
recreate it. Upgrading and downgrading this revision changes nothing.
"""

revision = "009_merge_legacy_road_addr"
down_revision = "008_youtube_destination_fields"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
