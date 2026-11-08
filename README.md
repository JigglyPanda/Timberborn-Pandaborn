# Panda Colonists - a Timberborn panda skin

Every beaver in Timberborn becomes a giant panda: realistic adults, chibi-cute cubs, and real see-through fur up close.

![thumbnail](mod/PandaColonists/thumbnail.png)

## Features
* **Panda bodies** for adults and kits: round heads and ears, chubby builds, puff tails. They run on **every original
  animation**, so every job, swim, zipline, dance and sleep works.
* **Fur textures** in 5 adult and 3 kit variants per faction.
  * Folktails: classic, cream, snowy, honey, and a rare brown *Qinling* panda.
  * Iron Teeth: slate, ash, steel, soot-grimed, and a Qinling.
* **Real shell + fin fur** on close-up pandas:
  * soft anti-aliased strands that stay plush even seen head-on
  * fuzzy strands along every outline
  * combed and clumped like a real coat
  * a dense undercoat, with shading from the panda's own shape
  * a soft sheen and backlit edges
  * follow-through when pandas move, and a little breeze sway
  * wet and badwater-matted fur
  * every panda's coat is slightly different
* **Painted UI portraits** for every faction, including contaminated and new-game portraits.
* **Modded factions** that use the standard beaver body become pandas automatically.
* Outfits, hats, injuries, the selection highlight, wet fur, contamination and carried goods all still line up.
  The original beaver texture layout is kept.

## Install
1. Download `PandaColonists.zip` from [Releases](../../releases). It includes the large character models.
2. Unzip it into `Documents\Timberborn\Mods\`. You should end up with `Mods\PandaColonists\manifest.json`.
3. Enable **Panda Colonists** in the game's mod manager.

The mod is purely visual, so it's safe to add to or remove from any save.

### Performance and settings
Fur is only drawn on the closest pandas (40 by default). It uses fewer layers at medium distance and fades out
completely when you zoom out, so a zoomed-out colony costs the same as an unmodded one. You can tune it in
`PandaFurSettings.txt`:

| setting | values |
|---|---|
| `quality` | `low` / `medium` / `high` (default) / `ultra` |
| `enabled` | `false` turns the fur off (models and textures stay) |
| `motion` | `false` stops fur follow-through and sway |
| `fins` | `false` removes the outline strands |

## Repository layout
| path | contents |
|---|---|
| `mod/PandaColonists/` | The mod as installed, minus `Characters/Beaver/*.timbermesh`. Those files are 95 MB and 57 MB, too big for git, so they ship in Releases. |
| `src/scripts/` | C# runtime code: the fur renderer (`PandaColonistsFur.cs`) and modded-faction textures (`PandaReskin.cs`) |
| `src/unity/` | Fur shader, fur masks and the Unity editor build script. Drop this into the [official Timberborn modding project](https://github.com/mechanistry/timberborn-modding). |
| `src/pipeline/` | Python and Blender pipeline that turns the game's beaver models into pandas and paints the textures and portraits |
| `docs/` | Technical notes on the Timbermesh format, asset overrides, vertex animation and fur rendering |
| `tools/` | Build helpers |

## Building from source
* **Fur shader bundle:** use Unity **6000.5.11f1** (the game runs 6000.5.x).
  1. Open the official modding project.
  2. Copy `src/unity/Assets/Mods/PandaColonistsV6` into its `Assets/Mods/`.
  3. Run the menu *Panda Colonists > Build v6 Fur Bundle*.
  4. Copy the resulting `pandacolonistsv6_win` into `mod/PandaColonists/AssetBundles/`.
* **Scripts:** compile `src/scripts/*.cs` against the game's `Timberborn_Data/Managed` DLLs. See `tools/build_dlls.sh`.
* **Models, textures and portraits:** see [docs/PIPELINE.md](docs/PIPELINE.md). The pipeline needs files extracted
  from your own copy of Timberborn. No game files are included in this repository.

## Credits
Made by JigglyPanda, with Claude (Anthropic) doing the modelling pipeline, shaders and code.
Timberborn is © Mechanistry. This is an unofficial fan mod.
