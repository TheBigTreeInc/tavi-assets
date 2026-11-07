"""Proposed restricted host-side adapter, *not* a TaviX wire method."""
from dataclasses import dataclass

from .core import AssetError


@dataclass(frozen=True)
class HostGrant:
    """A trusted Tavi host creates grants from the authenticated extension session."""
    packs: frozenset[str]
    capabilities: frozenset[str]


class HostAssetService:
    def __init__(self, manager, trusted_grants):
        # Caller IDs/grants MUST be determined by host sessions, never by extension input.
        self.manager = manager
        self.grants = dict(trusted_grants)

    def resolve(self, trusted_caller_id, pack_id, capability):
        grant = self.grants.get(trusted_caller_id)
        if grant is None or pack_id not in grant.packs or capability not in grant.capabilities:
            raise AssetError("host access denied")
        # No filesystem paths, directory enumeration or unrestricted raw file API.
        return self.manager.resolved(pack_id, capability)
