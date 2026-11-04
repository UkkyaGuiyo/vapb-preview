"""Stable identity for safely reusing one selected UnityPackage."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

from .identity import package_id_from_sha256


@dataclass(frozen=True)
class PackageIdentity:
    path: str
    size: int
    mtime_ns: int
    sha256: str

    @property
    def source_package_id(self) -> str:
        return package_id_from_sha256(self.sha256)

    @property
    def package_name(self) -> str:
        return Path(self.path).name

    @classmethod
    def from_path(cls, path: Path) -> "PackageIdentity":
        resolved = Path(path).resolve()
        stat = resolved.stat()
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return cls(str(resolved), int(stat.st_size), int(stat.st_mtime_ns), digest.hexdigest())


def distinct_package_paths(
    paths: Iterable[Path], identities: dict[Path, PackageIdentity],
) -> list[Path]:
    """Collapse exact archive copies only when provider paths collide.

    Preserve caller preference within one content namespace. Hash opaque archive
    bytes once per path; this does not extract FBX or Texture asset members.
    The identity cache is local to one analysis, never persisted.
    """
    paths = list(dict.fromkeys(Path(path).resolve() for path in paths))
    if len(paths) < 2:
        return paths
    distinct: dict[str, Path] = {}
    for path in paths:
        identity = identities.get(path)
        if identity is None:
            identity = PackageIdentity.from_path(path)
            identities[path] = identity
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (identity.size, identity.mtime_ns):
            raise ValueError("Package changed during provider identity comparison")
        distinct.setdefault(identity.source_package_id, path)
    return list(distinct.values())


def registered_archive_identities(packages: Iterable[dict]) -> dict[Path, PackageIdentity]:
    """Use only explicitly retained archives matching their saved content identity."""
    verified = {}
    for metadata in packages:
        try:
            digest = str(metadata.get("package_sha256", "")).lower()
            expected_id = package_id_from_sha256(digest)
            if metadata.get("source_package_id") != expected_id or not metadata.get("source_archive_path"):
                continue
            path = Path(metadata["source_archive_path"]).resolve()
            if path.suffix.lower() != ".unitypackage" or not path.is_file():
                continue
            identity = PackageIdentity.from_path(path)
            after = path.stat()
            if (identity.sha256 == digest and identity.source_package_id == expected_id
                    and (identity.size, identity.mtime_ns) == (after.st_size, after.st_mtime_ns)):
                verified[path] = identity
        except (OSError, TypeError, ValueError):
            # Missing, changed or legacy archives remain unresolved; never guess.
            continue
    return verified
