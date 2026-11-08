# Asset pipeline

The pipeline is Python 3 with numpy, scipy, Pillow and protobuf, plus Blender's `bpy` module for rendering, AO
baking and previews. It was developed on Linux.

## 0. Inputs (from your own game install)
Extract these with any Unity asset extractor, e.g. AssetRipper or UnityPy, from `Timberborn_Data`. Put them in a
folder and point `TIMBERBORN_EXTRACT` at it:
```
characters/beaver/beaveradult.model.timbermesh
characters/beaver/beaverchild.model.timbermesh
materials/beavers/common/adult_ao_2k.png, child_ao_1k.png      (the game's AO, used to place the mouth cap)
adult_normal_2k_rgb.png, chilkd_normal_1k_rgb.png             (decoded normal maps, previews only)
```
Some scripts still assume the original working folder `/root/w` for outputs (`out2/`, `out3/`, `prev/`). Edit the
paths at the top of each script, or create that folder.

## 1. Model: `build_model.py`
`python3 build_model.py ADULT_V2 out2/BeaverAdult.Model.timbermesh` (also `CHILD_V2`)
* `panda.PandaBuilder.build_rest` refines the beaver mesh with red-green subdivision, then sculpts the panda.
  * Head, body and muzzle come from SDF smooth-unions of ellipsoids (`geom.sd_ellipsoid`, `smin`, `project_to_sdf`).
  * Ears are half-ellipsoid bumps, limbs are thickened tubes, and the tail is a stub sphere.
  * Proportions live in `configs.py`.
* `remap_cavity` closes the beaver's open mouth with an ear-clipped cap. The cap is mapped to a free spot in the
  UVs that is neutral in the game's AO, normal and contamination maps.
* `bind` / `transfer` move every animation frame from the beaver onto the panda. Each panda vertex follows a
  Kabsch (best rigid) transform of its nearest beaver neighbourhood. Normals are rebuilt per smoothing group, and
  tangents are rebuilt from the UVs.
* Output is written with `tmesh.save`: zlib level 6 (header must be `78 9C`) around a protobuf (`model.proto`).
  Offsets and rotations are pre-rounded to half floats, because the game stores them as half floats.

## 2. Textures: `make_textures.py`
`python3 make_textures.py ADULT_V2|CHILD_V3 out2/BeaverAdult.Model.paint.npz outdir`
* The painter rasterises the panda's surface position and normal into UV space. It then paints the panda
  pattern procedurally: eye patches, ears, limbs and the shoulder band. It adds fur strokes, cub eyes and blush,
  and AO baked on the panda (`bake_ao.py`).
* The beaver UV layout is kept, which is why outfits, injuries and contamination still fit.

## 3. Portraits: `portrait.py`
Renders painted avatars with Blender: Cycles, a stylised oil filter and an outline.

## 4. Fur mask: `make_furmask.py`
* R channel: fur length. It is 0 on the eyes, nose and paw pads, short on the face, and longest on the tail.
* G channel: panda AO. The v6.1 masks in `src/unity` are the R channel blurred, plus the AO from `bake_ao.py`.

## 5. Checks
* `validate.py <modfolder>`: format, vertex counts, frame counts, texture sizes.
* `qa.py`, `preview.py`, `lineup.py`, `sheet.py`, `fur_preview5.py`: offline renders of poses and fur.
