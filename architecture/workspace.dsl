workspace "Tavi Assets" "0.1.3 source-backed local asset engine architecture" {
    model {
        user = person "Tavi user / local reviewer" "Previews and customizes offline sample content."
        tavi = softwareSystem "Tavi" "Trusted host and extension session boundary; asset bridge is not yet integrated."
        tavix = softwareSystem "TaviX" "Reviewed extension packaging; no data-only Tavi Assets distribution contract implemented."
        looprd = softwareSystem "LoopRD / Wallet" "Server-authoritative entitlements and purchases; production integration not implemented."
        apps = softwareSystem "Companion / Atrium / Klondike" "Future authorized asset consumers; not integrated."
        assets = softwareSystem "Tavi Assets" "Offline data-only pack management and local storefront preview." {
            engine = container "Asset Core" "Validate, stage, activate and resolve local packs." "Python: src/tavi_assets/core.py" {
                validator = component "Pack Validator" "validate(), _inside(), _check_magic(), _svg_is_safe(): checks source structure, file hashes, allowed types and SVG." "Python"
                installer = component "Pack Installer" "AssetManager.install()/uninstall(): staged copy, validation and version activation." "Python"
                recovery = component "Stage Recovery" "AssetManager._recover_locked()/recover(): lock-serialized cleanup of abandoned temporary stages; unregistered finalized releases never activated." "Python"
                registry = component "Local Registry" "AssetManager._load()/_save(), _lock(): persisted installed versions and preferences under an OS file lock." "Python"
                resolver = component "Resource Resolver" "AssetManager.resolved()/select(): maps capability plus preference to checked local bytes." "Python"
            }
            catalog = container "Catalog and Store Service" "Curated fixture catalog and fail-closed store operations." "Python: src/tavi_assets/catalog.py" {
                catalogReader = component "Catalog Reader" "Catalog(): verifies local catalog source and pack metadata." "Python"
                store = component "Store Service" "StoreService(): describe, install, select, uninstall and preview." "Python"
                entitlements = component "Entitlement Test Boundary" "DenyPaidEntitlements.can_access(): allows free catalog packs; denies paid in preview." "Python"
                wallet = component "Purchase Denial Boundary" "NoPurchases.purchase(): always rejects real purchasing." "Python"
            }
            storefront = container "Offline Storefront Preview" "Browser UI served exclusively on local loopback; no Tavi host deployment." "Python/HTML/CSS/JavaScript" {
                http = component "Preview HTTP Handler" "create_preview_server(): local HTTP read/write endpoints, host/origin and request-token checks." "Python: src/tavi_assets/preview.py"
                browser = component "Storefront UI" "Browser catalog, search, install, select and remove interactions." "JavaScript: src/tavi_assets/web/main.js"
            }
            hostAdapter = container "Restricted Host Resource Adapter" "Proposed host-boundary library, not a live extension bridge." "Python: src/tavi_assets/host.py" {
                grants = component "Trusted Grant Resolver" "HostAssetService.resolve(): per-host-supplied caller grants for pack/capability pairs." "Python"
            }
            device = container "Managed Device Files" "Registry JSON, versioned checked pack directories and preferences; local developer data." "Filesystem"
        }

        user -> browser "Uses locally" "Loopback browser"
        browser -> http "Browse, install, customize and remove" "HTTP 127.0.0.1"
        http -> store "Dispatches management operations" "Python method calls"
        store -> catalogReader "Reads curated catalog releases" "Python calls"
        store -> entitlements "Checks free availability; paid denied" "Python calls"
        store -> installer "Installs/removes approved local sample release" "Python calls"
        store -> registry "Reads local selection state" "Python calls"
        store -> resolver "Selects variant preferences" "Python calls"
        catalogReader -> validator "Checks every catalog pack source" "Python calls"
        installer -> validator "Verifies source, staging and installed bytes" "Python calls"
        installer -> registry "Activates/deactivates version records" "Python calls"
        recovery -> registry "Reads installed registry before deleting incomplete scratch state" "Python calls"
        recovery -> device "Deletes only recognized abandoned stage/registry temporary files under lock" "Filesystem"
        registry -> device "Reads/writes version and preference registry" "Filesystem"
        installer -> device "Stages, activates and removes pack files" "Filesystem"
        resolver -> validator "Revalidates installed manifest and file digests" "Python calls"
        resolver -> registry "Reads installed version and selection" "Python calls"
        resolver -> device "Reads validated asset bytes" "Filesystem"
        grants -> resolver "Resolves granted semantic resources" "Python calls"
        http -> browser "Returns UI, catalog state and previews" "HTTP loopback"
    }
    views {
        systemContext assets "AssetsContext" {
            include *
            autoLayout lr
        }
        container assets "AssetsContainers" {
            include *
            autoLayout lr
        }
        component engine "AssetCoreL3" {
            include *
            autoLayout lr
        }
        component catalog "CatalogL3" {
            include *
            autoLayout lr
        }
        component storefront "StorefrontL3" {
            include *
            autoLayout lr
        }
        component hostAdapter "HostAdapterL3" {
            include *
            autoLayout lr
        }
    }
}
