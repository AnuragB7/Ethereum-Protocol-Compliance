"""Quick smoke test for the Merkle tree incremental ingestion."""
import tempfile
import os
import sys

# Ensure the backend package is importable when running from the tests/ folder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.merkle_tree import MerkleTree


# Create a temp codebase
tmp = tempfile.mkdtemp()
with open(os.path.join(tmp, "a.py"), "w") as f:
    f.write("def hello(): pass")
with open(os.path.join(tmp, "b.py"), "w") as f:
    f.write("def world(): pass")

store = tempfile.mkdtemp()
mt = MerkleTree(store)

# First diff — everything is "added"
added, modified, deleted = mt.diff(tmp)
print(f"1st diff: added={len(added)}, modified={len(modified)}, deleted={len(deleted)}")
assert len(added) == 2 and len(modified) == 0 and len(deleted) == 0

# Snapshot
mt.update(tmp)
print(f"Root hash: {mt.root_hash[:16]}..., files: {mt.file_count}")

# No changes — should be empty
added, modified, deleted = mt.diff(tmp)
print(f"no-change: added={len(added)}, modified={len(modified)}, deleted={len(deleted)}")
assert len(added) == 0 and len(modified) == 0 and len(deleted) == 0

# Modify a.py
with open(os.path.join(tmp, "a.py"), "w") as f:
    f.write("def hello_v2(): pass")
added, modified, deleted = mt.diff(tmp)
print(f"edit a.py: added={len(added)}, modified={len(modified)}, deleted={len(deleted)}")
assert len(modified) == 1

# Add c.py
with open(os.path.join(tmp, "c.py"), "w") as f:
    f.write("x = 1")
added, modified, deleted = mt.diff(tmp)
print(f"add c.py: added={len(added)}, modified={len(modified)}, deleted={len(deleted)}")
assert len(added) == 1

# Delete b.py
os.unlink(os.path.join(tmp, "b.py"))
added, modified, deleted = mt.diff(tmp)
print(f"del b.py: added={len(added)}, modified={len(modified)}, deleted={len(deleted)}")
assert len(deleted) == 1

print("\nALL TESTS PASSED")
