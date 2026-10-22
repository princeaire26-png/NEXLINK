"""Compatibility facade for the unified NEXLINK Network Guard.

The actual enforcement implementation lives in :mod:`nexlink_agent.network_guard`
so the desktop client and bundled agent cannot drift into separate policies.
"""
from nexlink_agent.network_guard import (
    is_admin, is_blocked, remote_blocked, set_remote_block,
    block_internet, unblock_internet, update_blocked_domains,
)

# Backwards-compatible names used by the local guard UI.
is_remote_blocked = remote_blocked
update_blocked_urls = update_blocked_domains
