# Context brief: a Timberborn custom-characters mod

> Paste this to the Claude instance working on the new project. It comes from the team that built **Pandaborn**
> (https://github.com/JigglyPanda/Timberborn-Pandaborn), a mod that turns every Timberborn beaver into a panda.
> Everything under "Verified facts" was tested in the real game (Timberborn 1.x, Unity 6000.5.x, Windows).
> Everything under "Ideas" is a proposal, not yet tested.

## 1. The goal
Build a Timberborn **characters framework**: replace the colonists with any 3D character.

* **Simple side:** a player finds a model online (say a Snorlax `.glb`), drops it in a folder, and plays.
  The model is automatically fitted, rigged to the game's animations, textured, and given a portrait.
* **Advanced side:** artists ship high-quality character packs with hand-tuned fitting, multiple variants per
  faction, kits (children), custom fur or shaders, portraits and settings. They can publish them as their own
  Steam Workshop / mod.io mods that depend on the framework.
* Like Pandaborn, it must be purely visual. Save-safe, every job and animation working, outfits, tools and
  carried goods still attached, and **performance as top priority**.

## 2. Verified facts about Timberborn modding

### Mod folder and loading
* Mods live in `Documents\Timberborn\Mods\<ModFolder>\` and need a `manifest.json`:
  `{"Name","Version","Id","MinimumGameVersion","Description","RequiredMods":[],"OptionalMods":[]}`.
  Ids must be unique, so keep an Id stable across versions so players' installs upgrade.
* **The name players see** in the in-game mod list is the manifest's `"Name"`. The folder name is never shown, and
  Steam Workshop installs a mod into `steamapps\workshop\content\1062090\<item id>\` anyway. Every folder with a
  `manifest.json` is listed as its own mod, though. When a mod is renamed or gets a new Id, old folders left behind
  still appear under their old names and still override files, so tell users to delete them.
* When two mods override the same file, the one that loads later wins.
* **Asset override:** a mod file at the same relative path as a vanilla asset replaces it. Paths are matched
  lowercase with the extension stripped. This works for `.timbermesh` models and `.png` textures, e.g.
  `Characters/Beaver/BeaverAdult.Model.timbermesh` and `Materials/Beavers/Folktails/Adult/BeaverAdult1.Folktails.png`.
* A sprite needs a sidecar `<file>.png.meta.json` containing `{"isSprite": true}`. Avatars live under
  `Sprites/Avatars/`: `FolktailsAdult`, `FolktailsChild`, `FolktailsContaminatedAdult/Child`, `FolktailsFullNewGame`,
  and the same set for IronTeeth.
* **Code:** DLLs in `<mod>/Scripts/` are loaded automatically.
  * Dependency injection is Bindito. Make a `[Context("Game")] public class X : Configurator`.
  * Bind components with `Bind<T>().AsTransient()`.
  * Attach per-entity logic with
    `MultiBind<TemplateModule>().ToProvider(...)` + `new TemplateModule.Builder().AddDecorator<BeaverSpec, MyComponent>()`.
  * `MyComponent : BaseComponent, IPostInitializableEntity` gets constructor injection, e.g. `IAssetLoader`
    or `FactionService`. `GetComponent<Child>()` tells kits from adults.
* **Compile** against `Timberborn_Data/Managed/*.dll` with Roslyn `csc.dll -nostdlib`, excluding
  `Mono.Security` and `System.EnterpriseServices`. `System.Core` may be missing, so avoid `HashSet` and use
  `Dictionary`. NuGet may be blocked in a sandbox; that's fine, since nothing extra is needed.
* **How code loads:** the game reads every `*.dll` anywhere in an enabled mod's folder with
  `Assembly.Load(bytes)`. So `Assembly.Location` is empty; get your folder from `IModStarter.StartMod(IModEnvironment)`
  via `modEnvironment.ModPath`. All mods' DLLs are loaded first, then every `IModStarter` runs, then Bindito scans
  `GetTypes()` of every assembly with no try/catch. A DLL that references a mod that isn't installed therefore crashes the
  game. Pandaborn ships its optional Mod Settings page as `Scripts/PandabornSettings.bin` and loads it from its
  `IModStarter` only when the `ModSettings.Core` assembly is present.
* **Mod Settings mod** (`eMka.ModSettings`, the de-facto settings UI):
  * Subclass `ModSettingsOwner` with a `(ISettings, ModSettingsOwnerRegistry, ModRepository)` constructor.
  * Expose public get-only properties (`ModSetting<bool/int/float/string>`, `RangeIntModSetting`,
    `LimitedStringModSetting`) built with `ModSettingDescriptor.Create(name).SetTooltip(...)`.
  * Set `ModId` to your manifest Id, and override `ChangeableOn => ModSettingsContext.All` for live changes.
  * Bind it with `Bind<T>().AsSingleton()` in `[Context("MainMenu")]` and `[Context("Game")]`.
  * List it in the manifest as `"OptionalMods": [{"Id": "eMka.ModSettings"}]`. That also orders the load.
* **Asset bundles:** files at `<mod>/AssetBundles/<name>_win` load automatically.
  * Inside the bundle, asset paths are truncated after `resources/`. So
    `Assets/Mods/X/AssetBundles/Resources/Foo/Bar.mat` loads as `IAssetLoader.LoadSafe<Material>("Foo/Bar")`.
  * Build with the official project https://github.com/mechanistry/timberborn-modding. It uses Unity
    6000.5.11f1 with URP 17.5; the game itself runs 6000.5.5f1.
  * Its Windows graphics APIs are D3D11 and D3D12.
  * Delete its example mods if their game DLLs aren't imported, or compile errors block the editor menu.
  * Bundles are re-loaded between game sessions, so re-fetch loaded materials if they become null.

### Factions
* Each faction is a `FactionSpec` blueprint: `Id`, `Textures` / `ChildTextures` (the random pool for `_BaseMap`),
  `Avatar`, `ChildAvatar`, `ContaminatedAdultAvatar`, `ContaminatedChildAvatar`, `NewGameFullAvatar`, and more.
  `ISpecService.GetSpecs<FactionSpec>()` lists every faction, including modded ones (Emberpelts, Leaf Coats, ...).
* **Re-skinning any faction without shipping assets per faction** works. Pandaborn does it from an
  `ILoadableSingleton` bound in `[Context("MainMenu")]` and `[Context("Game")]`. At load it uses reflection to
  rewrite the spec's `<Name>k__BackingField` fields, copying textures and avatars from the Folktails spec (giant
  panda) or the IronTeeth spec (red panda), or restoring that faction's cached originals. Changes reach colonists
  textured from then on, and a save reload updates everyone. A characters framework can pick a character per
  faction at the same hook.
* Untested: a faction mod that ships its own beaver *model* would replace the shared body for everyone, whichever
  loads last.

### Characters
* Each colonist model is one `.timbermesh`:
  * the file is zlib (header must be exactly `78 9C`, i.e. level 6) wrapped around protobuf `model.proto`, which is in
    the panda repo `src/pipeline/`
  * node 1 is the main body mesh
  * other nodes such as `#Head` are attachment points; hats, tools and carried goods follow them, and they have
    their own animated transforms
* **Vertex animation (VAT), not skinning.** Each vertex stores per-frame **offset** and **rotation quaternion**.
  * The animated normal is `q·(-1,0,0)` and the tangent is `q·(0,0,-1)`.
  * The game converts the data to half floats, so pre-round your data to halves.
  * The adult beaver has 61 animations, about 3,500 frames in total: walk, run (on all fours), carry, swim,
    zipline, dance, sleep, builder, and the like.
  * The runtime binds two textures per renderer material, `_Offsets` and `_Rotations`, plus floats
    `_AnimationTime`, `_AnimatedVertexCount`, `_FrameCount`, `_Looped` and `_AnimationEnabled`.
  * The shader (`AnimateVAT.hlsl` in the game) samples `(vertexIndex+0.5)/count` against the frame. Timbermesh
    meshes are CPU-readable.
* **Material:** characters use the `BeaverURP` shader graph, which is opaque URP Lit.
  * Properties: `_BaseMap`, `_BaseColor`, `_OcclusionMap`, `_WorkerOutfitDiffuse`, `_ContaminationDiffuse`,
    `_BadwaterContamination`, `_InjuryDiffuse`, `_MudSplat`/`_MudPit`, `_TailDecalDiffuse`, `_TintColor`/`_TintEnabled`
    (the selection highlight), and `_WetFur`.
  * The faction texture is assigned at runtime as `_BaseMap` (`CharacterMaterialModifier` / `BeaverTextureSetter`).
  * The **AO and normal maps are fixed in the material and cannot be overridden by a mod**. Design around that:
    a new model must keep the beaver UV layout, or the beaver's AO/normal relief shows through, e.g. "double eyes".
* **The fixed normal map also fixes where eyes can go.** The beaver's eye sockets and eyelid rings are in the normal
  map, so eyes painted anywhere else show the beaver's eyes through as a second pair. Pandaborn found the socket
  centre by template-matching the eyelid ring in the normal map, sat the painted eyes there, and added dark eye rims
  to hide what relief remained.
* **Keeping the beaver's UV layout** is what makes outfits, injuries and contamination line up automatically.
  A model with arbitrary UVs needs its own material and shader (see Ideas).

### Rendering and performance lessons (from the fur work)
* A custom shader can draw extra geometry next to the character. Copy the VAT properties from the character's
  material every frame with a `MaterialPropertyBlock`, and replicate `AnimateVAT` maths in your shader.
* Alpha-blended extras: put them in the `Transparent` queue so they work with or without URP depth priming.
* Evaluate shadows at the strand root or base surface, not on offset shells, to avoid shadow acne and grain.
* Hard alpha clipping of sub-pixel detail looks grainy because the game has no TAA. Use analytic anti-aliasing
  with `fwidth`, and fall back to average coverage when detail gets smaller than a pixel.
* Budget the extras:
  * draw them only on the N nearest characters
  * use a distance LOD and fade them out
  * collapse unused vertices in the vertex shader
  * share the generated meshes per source mesh

## 3. What was hard (pitfalls)
* The beaver's mouth is an open cavity with teeth paint. Closing it needed a capped hole mapped to a UV spot
  that is neutral in the game's AO, normal and contamination maps.
* The beaver normal map's eyelid ring made "double eyes" on cubs. The fix was to paint the new eyes where the
  relief sits.
* Big files: the adult model is about 96 MB and the kit about 57 MB, which is over GitHub's limits, so they ship
  in Releases.
* Anything that needs Unity (shaders, bundles) must be built on the user's PC.
* `run` animations are quadrupedal in vanilla. An "upright running" option could swap in the walk clip at runtime.
  The user liked all-fours running on the pandas and dropped the toggle.
* **Painting facial markings in UV space looks wrong.** The UV islands are stretched and split, so shapes that look
  right flat come out distorted. The red panda face went through four rounds of "doesn't look like a red panda"
  before it worked:
  * Paint in head-surface **angle space**: azimuth and elevation around the head centre, normalised by landmark
    angles (eye, nose), so u = azimuth / eye azimuth and v = elevation between nose and eye.
  * Draw soft blobs and bands there: muzzle, cheek patches, brows, tear tracks and eye ring. Then bake them through
    each texel's 3D position into the texture.
  * Work from real photos of the animal. Tear tracks that are too dark or end in blobs read as "poop tears".
* **Portraits:** painterly or oil-paint filters read as "AI-generated / trashy" to players. Clean studio renders of
  the mod's own models with real particle hair (Blender Cycles: weld UV seams, subsurf level 2, about 60k strands
  coloured from the texture) looked much better. Generative AI use is disclosed in the README and release notes.
* **Blender runs out of memory** (7–8 GB) with four furry characters in one scene. Render each character as its
  own transparent layer and composite.
* **Keep the installed copy in sync with the release.** Textures in the user's installed mod were once a revision
  behind the release folder, so they were testing old faces. Diff the installed copy against the build output
  after each change.

## 4. Ideas for the characters framework (untested proposals)

### The key trick: rig any mesh to the beaver *without* re-baking animations
Every beaver vertex already carries a full rigid frame per animation frame (position and rotation). So treat the
beaver's ~1,700 vertices as ~1,700 "bones":
1. Fit the custom model into the beaver's rest pose: scale to height, align forward to +Z and up to +Y.
2. For each custom vertex, store its k nearest beaver vertices (k = 4) with weights, plus its offset in each one's
   rest frame.
3. In a custom vertex shader, sample the beaver VAT for those k vertices and blend:
   `p = Σ wᵢ (posᵢ(t) + qᵢ(t)·qᵢ(0)⁻¹·(p₀ − posᵢ(0)))`.
   It's linear blend skinning with the beaver as the skeleton.

This gives **every game animation for free**, at load time, with no offline baking. Pandaborn did an offline
version of this (Kabsch neighbourhood transfer) and it held up across all 61 animations.

Very different body plans need more than nearest-vertex binding. Snorlax, for example, is a ball with a head.
* Use **region labels** (head, torso, left/right arm and leg, tail) on both meshes, so a custom arm binds only to
  the beaver arm.
* Get the labels from the user, from a simple landmark picker, or by auto-segmenting with a few heuristics.
* Optionally "inflate" the beaver toward the custom shape before binding, as Pandaborn did with SDF
  sculpting.

### Rendering path for arbitrary models
* Draw the custom mesh with its own material and textures, using any UVs and its own normal map.
* Hide the original beaver renderer, by disabling it or giving it an empty mesh.
* Carry over the game's state onto the new material: outfits, contamination, wet, tint and injuries.
  * For arbitrary UVs, use a tinted overlay or a world-space/triplanar effect.
  * Or offer an optional "beaver-UV" projection for artists who want exact outfits.
* Keep the attachment nodes (`#Head`, hands) working. Read the beaver node transforms and apply the character's
  offsets and scale from its config.

### Runtime model import (the simple side)
* glTF/GLB is the friendliest format. Ship a runtime loader such as glTFast, compiled to a DLL, or a minimal
  custom GLB reader for meshes and textures only.
* FBX is harder: convert it offline, or ask the user to export GLB from Blender.
* Validate and auto-fix on import:
  * decimate above a vertex budget (≈10–20k vertices)
  * downscale textures above 2K
  * recompute normals
  * pick a forward axis automatically by matching the head to the beaver's head region
* Generate portraits automatically: render the character off-screen at load with a portrait camera, and cache the
  PNG as a sprite.

### Character pack format (the advanced side)
```
Mods/MyCharacterPack/
  manifest.json                         (RequiredMods: the framework's Id)
  characters/snorlax/character.json     (name, factions, adult/child, scale, offsets, region labels,
                                         attachment offsets, weight in the random pool, shader options)
  characters/snorlax/model.glb
  characters/snorlax/textures/*.png
  characters/snorlax/portrait.png       (optional; otherwise auto-rendered)
```
* Assign a character per faction or per colonist, randomly weighted, with an optional in-game picker. Keep the
  choice stable per colonist by hashing its entity id.

### Performance guardrails
* Use one shared mesh and material per character type, and per-instance data through MaterialPropertyBlocks.
* Cap vertex count and texture size, and use LODs for distant colonists: decimated mesh, or fall back to the
  beaver.
* Do all binding work once at load, and cache it on disk keyed by a hash of the model.

### Legal note
Fan models of trademarked characters (Pokémon and the like) are fine for personal use. Publishing them to the
Workshop can draw takedowns, so keep the framework neutral and let players bring their own models.

## 5. Suggested milestones
1. Replace the adult beaver with a static custom mesh that follows the beaver's position, and hide the beaver.
2. Add the GPU "beaver as skeleton" binding, so the mesh follows all animations. Test walk, run, swim and sleep.
3. Add the character.json format, kits, factions, attachments and auto portraits.
4. Add the runtime GLB loader and auto-fit for the simple side.
5. Add region labels and a landmark tool for odd body plans, plus optional fur and shaders from Pandaborn.
6. Package for Steam Workshop / mod.io, with a sample pack (the pandas could be the first pack).

## 6. Working setup that worked well for us
* Claude runs in a cloud Linux workspace that can be linked to the user's Windows PC through the Claude desktop
  app. It can list, stage and commit files there. Commits top out around 14 MB per file; staging allows up to
  400 MB.
* There is no shell on the PC. Unity steps were done by Claude driving the screen with computer use, after the
  user signed in to Unity Hub and approved each step.
* Offline preview renders with headless Blender (Cycles) caught most problems before the user tested in game.
  In-game screenshots from the user were still essential for tuning.
* **Computer-use limits on Windows:**
  * File Explorer can only be clicked, not typed into.
  * File dialogs block F2 and rename.
  * With no shell, Claude can't rename, move or delete folders on the PC. It can only write files, so ask the user
    for renames and deletes.
* **GitHub:** pushing works through the session's git proxy. Creating or editing **Releases is refused** ("not
  permitted for this session type"), so the user publishes releases by hand. Claude prepares the release folder
  and the notes.
* **Release layout** (Pandaborn): the mod folder zipped as `Pandaborn/` with `manifest.json`, `thumbnail.png`
  (also the Workshop preview), `README.md`, `PandaFurSettings.txt`, `Scripts/`, `AssetBundles/`, `Materials/`,
  `Sprites/`, and `Characters/Beaver/` holding only the two `.timbermesh` models (about 180 MB zipped).
