"""
Merkle Tree for Incremental Code Ingestion

Builds a content-addressable hash tree over a codebase so that on
subsequent ingestion only changed, added, or deleted files are
re-parsed and re-indexed.

Structure persisted to disk:
    <persist_dir>/merkle_state.json

    {
        "root_hash": "<sha256 hex>",
        "file_hashes": {
            "relative/path/to/file.py": "<sha256 hex>",
            ...
        }
    }

On re-ingestion the algorithm:
    1. Walks the codebase and computes per-file SHA-256 hashes.
    2. Loads the previous state from disk.
    3. Compares:
        - files whose hash changed  → modified
        - files present now but not before → added
        - files present before but not now → deleted
    4. Returns the three sets so the indexer can do targeted work.
    5. Saves the new Merkle state to disk.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Extensions the graph indexer cares about (must stay in sync with CodebaseParser)
SUPPORTED_EXTENSIONS = {
    ".py", ".java", ".cob", ".cbl",
    ".js", ".jsx", ".ts", ".tsx", ".vue",
    ".go", ".sol",
}


class MerkleTree:
    """
    Content-addressable Merkle tree over a directory of source files.

    Each leaf is the SHA-256 of a single file's contents.
    The root hash is computed by sorting the (path, hash) pairs
    alphabetically and hashing the concatenation — giving a single
    deterministic digest for the entire codebase snapshot.
    """

    def __init__(self, persist_dir: str):
        """
        Args:
            persist_dir: Directory where merkle_state.json is stored
                         (same as the graph_storage dir).
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.persist_dir / "merkle_state.json"

        # Current (persisted) state
        self._saved_hashes: Dict[str, str] = {}
        self._saved_root: str = ""
        self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def diff(self, codebase_path: str) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Compare the codebase on disk against the last-saved Merkle state.

        Args:
            codebase_path: Absolute path to the codebase root.

        Returns:
            (added, modified, deleted) — three sets of *absolute* file paths.
        """
        current_hashes = self._hash_directory(codebase_path)
        saved = self._saved_hashes

        current_rel = set(current_hashes.keys())
        saved_rel = set(saved.keys())

        added_rel = current_rel - saved_rel
        deleted_rel = saved_rel - current_rel
        common_rel = current_rel & saved_rel
        modified_rel = {p for p in common_rel if current_hashes[p] != saved[p]}

        root = Path(codebase_path)
        added = {str(root / p) for p in added_rel}
        modified = {str(root / p) for p in modified_rel}
        deleted = {str(root / p) for p in deleted_rel}

        return added, modified, deleted

    def update(self, codebase_path: str) -> str:
        """
        Snapshot the codebase and persist the new Merkle state.

        Returns:
            The new root hash.
        """
        current_hashes = self._hash_directory(codebase_path)
        root_hash = self._compute_root(current_hashes)

        self._saved_hashes = current_hashes
        self._saved_root = root_hash
        self._save_state()

        return root_hash

    @property
    def root_hash(self) -> str:
        return self._saved_root

    @property
    def file_count(self) -> int:
        return len(self._saved_hashes)

    @property
    def has_state(self) -> bool:
        """True when a previous snapshot exists on disk."""
        return bool(self._saved_hashes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hash_directory(self, codebase_path: str) -> Dict[str, str]:
        """Walk *codebase_path* and return {relative_path: sha256_hex}."""
        root = Path(codebase_path)
        hashes: Dict[str, str] = {}

        for file_path in sorted(root.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            # Skip common non-source directories
            parts = file_path.relative_to(root).parts
            if any(p.startswith(".") or p in ("node_modules", "__pycache__", ".venv", "venv", "dist", "build") for p in parts):
                continue

            rel = str(file_path.relative_to(root))
            hashes[rel] = self._hash_file(file_path)

        return hashes

    @staticmethod
    def _hash_file(path: Path) -> str:
        """SHA-256 of a single file (read in 64 KiB chunks)."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _compute_root(file_hashes: Dict[str, str]) -> str:
        """Deterministic root hash from sorted (path, hash) pairs."""
        h = hashlib.sha256()
        for path in sorted(file_hashes.keys()):
            h.update(path.encode("utf-8"))
            h.update(file_hashes[path].encode("utf-8"))
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_state(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self._saved_hashes = data.get("file_hashes", {})
                self._saved_root = data.get("root_hash", "")
                logger.info(
                    f"Merkle state loaded: {len(self._saved_hashes)} files, "
                    f"root={self._saved_root[:12]}…"
                )
            except Exception as e:
                logger.warning(f"Failed to load Merkle state: {e}")
                self._saved_hashes = {}
                self._saved_root = ""

    def _save_state(self):
        data = {
            "root_hash": self._saved_root,
            "file_hashes": self._saved_hashes,
        }
        self.state_file.write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )
        logger.info(
            f"Merkle state saved: {len(self._saved_hashes)} files, "
            f"root={self._saved_root[:12]}…"
        )
