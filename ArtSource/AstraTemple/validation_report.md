# Temple of the Canopy

Open `/Game/AstraTemple/Maps/L_TempleOfTheCanopy` and press Play to explore the original environment. Its first-person character supports mouse look, WASD and ZQSD. The saved composition camera is `View_Reference`. The project now starts on its playable team deathmatch variant. [Canopy Clash](Deathmatch/MatchValidation.md)

## Visual review

The supplied frame determined the stepped sanctuary, face above the deep entrance, fig on its eastern terrace, shaded masonry gate, diagonal crossing and open water. The unseen ritual nave, rain court, cloister, spring cave and ridge paths are reconstructions. The valley measures 403.2 m on each side. Three flights of forty actual steps climb 24 m from the plaza to the hall. Two spring branches and an upper feeder descend through eight waterfalls.

The Unreal and reference frames share the foreground arch, bridge, central stair axis, carved face and falls behind the terrace. The reference has denser leaf layers, more varied canopy outlines and more irregular erosion and ornament on the stone. Its own foreground bridge also presents more of the pier faces. The level retains those visual differences. The scene uses a stationary sun, fixed exposure and local reflected light. Revised renders restored cloud detail behind the rain court and removed the broad white reflection in the basin's aerial view.

[Reference and Unreal at matching aspect ratio](Review/ReferenceComparison.jpg) · [Nine saved level views](Review/TempleViews.jpg) · [Portal detail](Review/Final-PortalDetail.png) · [West spring passage](Review/Final-Grotto.png) · [Terrain plan](semantic_layout.png)

## Native construction and checks

Epic's Unreal MCP was used throughout to build the Landscape, assemble meshes and foliage, author materials and lighting, trace the terrain, save cameras and run the native player. Mesh construction sources, scanned source material and native assets are included. The project contains 89 native static mesh assets. The loaded map contains 449 actors, including the cameras and technical lighting helpers.

The project enables Epic's editor toolset. On a fresh project launch, Unreal automatically loaded the temple and started the local MCP endpoint. The native configuration read back as automatic start enabled, port 8000 and path `/mcp`. The separate offscreen authoring instance was exercised on loopback port 8001.

The exploration-level play and performance checks below used the installed Unreal editor. The subsequent team deathmatch build uses Windows SDK 10.0.26100.0.

| Check | Result and evidence |
|---|---|
| Saved level | Verified by opening another world and reloading the saved temple. Map Check returned zero errors and zero warnings. All 44 local materials recompiled without errors. [Saved-world check](Review/SavedWorldCheck.json) |
| Final asset audit | All meshes outside the project namespace are the technical sky dome or editor-only camera representations. No visible basic-shape blockout actors were found. [Native asset registry](asset_registry.json) |
| Architecture and edges | The rear retaining wall, returns and terrace ends were checked on ten masonry sections. Eleven samples on the original central walk retained their support. [Bearing measurements](Review/CourtBearing.json) · [Rear foundations](Review/CourtFromAbove.png) |
| Grotto and ridge | Native traces measured a minimum of 2.56 m of overhead clearance across a 2.20 m strip. The first-person character subsequently walked through the grotto to the upper shrine. [Clearance](Review/GrottoClearance.json) · [Ridge walk](Review/Traversal_ridge.json) |
| Water and vegetation | Native single-layer water, submerged beds, projected local reflections, falling ribbons and jets, foam and spray. Wind on foliage was checked in Unreal. [Leaf motion](Nature/Previews/UE_LeafWind.webp) · [Plant specimens](Review/ScannedUnderstory.png) |
| Lower Ford bank | A Landscape mask blends scanned cushion moss and forest leaf litter over 2,342 m² of the approach and eastern shore. Forty-four low ferns follow the bank. The mask excludes all 411 sampled path-centre points. [Before and after at eye level](Review/LowBankBeforeAfter.jpg) · [Moss and leaf-litter sources](BankUnderstory/Sources.json) |
| Provenance | Local authoring includes the modular masonry kit, carvings, figs, roots and waterfall geometry. Downloaded geology, bark, understory and sky sources have recorded provenance. [Botanical source records](FloraStudies/Provenance.json) · [Nature inventory](Nature/nature_assets.json) · [Ground sources](Terrain/ground_sources.json) · [Sky source](Terrain/sky_source.json) |

## Traversal

The tests used the project character, movement inputs and collision capsule from the actual PlayerStart. Distances include common approach segments. The table reports each complete recorded walk independently.

| Walk | Checkpoints | Distance |
|---|---:|---:|
| First gate, bridge, stairs, ritual hall and return | 73 / 73 | 409.94 m |
| Broken cloister | 12 / 12 | 167.01 m |
| Eastern gallery and shrine | 16 / 16 | 159.32 m |
| Upper spring | 47 / 47 | 320.81 m |
| Spring grotto, ridge shrines and Crown summit | 94 / 94 | 494.89 m |

The main walk and eastern gallery were repeated after painting and planting the Lower Ford bank. The cloister and Crown summit runs include the optimized tree shadow geometry. The upper spring run predates that change. Water movement, shading and input continue under a single lighting condition.

[Detailed input and traversal results](runtime_validation.json) · [Frame time and GPU profiles](render_profile.json)

## Desktop performance

The native engine frame profiler measured the full main walk at 105.06 fps with an 11.66 ms 95th-percentile frame and the eastern shrine walk at 102.50 fps with an 11.74 ms 95th-percentile frame. Both used a 1,239 × 350 Play In Editor viewport and included the frames in which player screenshots were captured. [Temple walk profile](Review/Performance_main.json) · [Ford walk profile](Review/Performance_east.json)

An i7-10700KF and RTX 3080 rendered the default map in separate Unreal `-game` processes with Direct3D 12. Each cell reports 300 frames at a fixed first-person viewpoint after warm-up. The original interactive editor remained open throughout. The project retains 200% TSR history and applies the two virtual-shadow settings tested in the matched 1080p runs. [Control](Review/Standalone_Candidate_control_1920x1080.json) · [Shadow settings](Review/Standalone_Candidate_shadows_1920x1080.json)

| Output | Jungle approach, mean fps | Frame time p95 | Bridge, mean fps | Frame time p95 |
|---|---:|---:|---:|---:|
| [1280 × 720](Review/Standalone_1280x720.json) | 106.70 | 10.60 ms | 113.07 | 9.97 ms |
| [1920 × 1080](Review/Standalone_1920x1080.json) | 97.41 | 11.38 ms | 103.87 | 10.60 ms |
