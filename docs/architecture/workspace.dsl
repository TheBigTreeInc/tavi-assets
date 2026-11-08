workspace "Tavi Assets" "Source-backed data-only asset management and proposed consumer SDK, with reference adapters" {
    model {
        user = person "Tavi user / local reviewer" "Previews and customizes offline sample content."
        tavi = softwareSystem "Tavi" "Trusted host and extension session boundary; asset bridge is not yet integrated."
        tavix = softwareSystem "TaviX" "Reviewed extension packaging; no data-only Tavi Assets distribution contract implemented."
        looprd = softwareSystem "LoopRD / Wallet" "Server-authoritative entitlements and purchases; production integration not implemented."
        apps = softwareSystem "Companion / Atrium / Klondike" "Future authorized asset consumers; not integrated."
        assets = softwareSystem "Tavi Assets" "Data-only pack management, portable JS reference service and local preview; no production Tavi host bridge." {
            engine = container "Asset Core" "Validate, stage, activate and resolve local packs." "Python: src/tavi_assets/core.py" {
                metadataValidator = component "Typed Object Graph Validator" "metadata.validate_metadata(): validates kinds, tags, optional game-specific rarity, references and collections without executable effects or marketplace semantics." "Python: src/tavi_assets/metadata.py"
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
                discovery = component "Granted Metadata Discovery" "HostAssetService.describe()/list_objects()/get_object()/list_collections()/get_collection()/preferences(): pack-authorized, path-free object information." "Python: src/tavi_assets/host.py"
                grants = component "Trusted Grant Resolver" "HostAssetService.resolve(): per-host-supplied caller grants for pack/capability pairs." "Python"
            }
            consumerSdk = container "Reference Consumer SDK" "Proposed transport-injected SDK. No deployed TaviX host feature or production transport exists." "JavaScript ES module and .d.ts" {
                client = component "Typed Asset Consumer" "createTaviAssetsClient(): negotiates tavi.assets/v1 and performs grant-scoped pack and object discovery, resource slot resolution and existing metadata/selection calls." "JavaScript: sdk/client.mjs"
                developerFixture = component "Local Developer Fixture Host" "developer/fixture-host.mjs: explicit local file fixtures, artificial session grants and reference bridge-backed SDK transport for game tests only." "Node.js ES module"
                fakeHost = component "Mock Transport in SDK Tests" "tests/consumer_sdk_smoke.mjs emulates host info/requests; not an actual extension host." "Node.js test fixture"
            }
            portableRuntime = container "Portable Asset Service Reference" "Tavi Assets-owned JS implementation; not yet embedded into any Tavi client." "JavaScript ES modules: portable_service/" {
                portableValidator = component "Portable Pack Validator" "validation.validatePack(): validates bounded data-only manifest/media, SVG allowlist and SHA-256 hashes before approved activation and resource delivery." "JavaScript: portable_service/validation.mjs"
                portableService = component "Embeddable Asset Service" "AssetService: privileged install/update/uninstall, metadata queries, preference precedence and resource resolution." "JavaScript: portable_service/service.mjs"
                dependencyResolver = component "Verified Feature Dependency Resolver" "resolveAssetRequirements(): validates proposed per-feature requirements, selects installed granted capabilities under semver bounds, returns readiness only; never installs, purchases or grants." "JavaScript: portable_service/dependencies.mjs"
                grantValidator = component "TaviX Scoped Grant Validator" "validateTavixHostContext() and validateTavixAssetDependencies(): bind host-session extension identity/version/digest, subset of verified manifest requests and per-pack capability/customization scopes. Local reference; not an entitlement authority." "JavaScript: portable_service/grants.mjs"
                portableBridge = component "Trusted Host Bridge Proposal" "TrustedAssetHostBridge: session-bound caller grants, cross-pack metadata search, multi-slot checks and strict assets.* dispatch; no production host hookup." "JavaScript: portable_service/service.mjs"
                memoryAdapter = component "Memory Storage Adapter" "MemoryAssetStorage: serializes atomic in-process transaction tests; no restart persistence across processes." "JavaScript: portable_service/storage.mjs"
                nodeAdapter = component "Node File Storage Reference" "NodeFileAssetStorage: 8 MiB single-snapshot atomic replace with fail-closed lock; development only, not a Windows/Android production storage layer." "Node: portable_service/node-file-storage.mjs"
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
        validator -> metadataValidator "Checks typed objects/collections, rarity and references" "Python calls"
        installer -> registry "Activates/deactivates version records" "Python calls"
        recovery -> registry "Reads installed registry before deleting incomplete scratch state" "Python calls"
        recovery -> device "Deletes only recognized abandoned stage/registry temporary files under lock" "Filesystem"
        registry -> device "Reads/writes version and preference registry" "Filesystem"
        installer -> device "Stages, activates and removes pack files" "Filesystem"
        resolver -> validator "Revalidates installed manifest and file digests" "Python calls"
        resolver -> registry "Reads installed version and selection" "Python calls"
        resolver -> device "Reads validated asset bytes" "Filesystem"
        grants -> resolver "Resolves granted semantic resources" "Python calls"
        discovery -> registry "Requests validated active pack manifest through AssetManager.manifest_for" "Python calls"
        client -> fakeHost "Uses injected mock info/request transport in test suite" "Node.js mock calls"
        developerFixture -> portableBridge "Constructs trusted development-only session and scoped grants" "In-process JavaScript calls"
        developerFixture -> portableService "Installs explicitly provided free test fixtures through test authorizer" "In-process JavaScript calls"
        client -> developerFixture "Uses synthetic transport from local fixture host in game examples" "JavaScript SDK calls"
        portableBridge -> grantValidator "Validates fresh host-supplied verified manifest and scoped TaviX projection on every request" "In-process JavaScript"
        dependencyResolver -> grantValidator "Checks exact pack-specific capabilities and half-open version ranges" "In-process JavaScript"
        portableBridge -> dependencyResolver "Evaluates host-verified declaration from trusted session only" "In-process JavaScript calls"
        dependencyResolver -> portableService "Consumes already validated installed manifest snapshots from privileged service" "Service.getManifest()"
        portableBridge -> portableService "Authorized metadata, application override, and resource requests" "In-process JavaScript calls"
        portableService -> portableValidator "Checks manifest, media and SHA-256 before activation and resource reads" "JavaScript calls"
        portableService -> memoryAdapter "Atomic in-memory state transactions in tests" "StorageAdapter interface"
        portableService -> nodeAdapter "Atomic bounded snapshot transactions in Node-only tests" "StorageAdapter interface"
        nodeAdapter -> device "Writes reference snapshot; not used by Python engine" "Node filesystem, reference-only"
        fakeHost -> portableBridge "Session-bound in-process reference test" "Node.js smoke fixture"
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
        component portableRuntime "PortableRuntimeL3" {
            include *
            autoLayout lr
        }
        component consumerSdk "ConsumerSdkL3" {
            include *
            autoLayout lr
        }
    }
}
