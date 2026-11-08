# Tavi Assets 0.1.13 — LoopRD descriptor specification repair

Fixes the reported LoopRD `specification_invalid` response by supplying per-resource `fields` maps and migrating away from version 1 to 2026110901. This is a source candidate, not an online deployment. Validate the migration identifier with the target LoopRD instance before applying; preserve database state and all operator, account-auth and publication approvals. Tavi ecosystem admin delegation remains unimplemented on the Social side.
