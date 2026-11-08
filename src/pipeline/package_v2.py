"""Assemble the mod folder: /root/w/mod/PandaBeavers"""
import os, shutil, json
from PIL import Image

OUT = '/root/w/mod/PandaColonistsV2'
SRC = '/root/w/out2'
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)


def put(src, rel):
    dst = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


manifest = {
    "Name": "Panda Colonists v2",
    "Version": "2.0.0",
    "Id": "PandaColonists.ReskinV2",
    "MinimumGameVersion": "1.0.0.0",
    "Description": "v2 - realistic giant-panda adults (heavy build, thick black limbs, round paws, wide jowly heads) and chibi-cute cubs (huge round heads, big sparkly eyes, rosy cheeks). Do not enable together with Panda Colonists v1. Replaces every beaver with a giant panda. New panda bodies for adults and kits (round heads, ears, "
                   "chubby builds, puff tails) driven by all of the original animations, hand-crafted panda fur for "
                   "every Folktails and Iron Teeth variant (including rare brown Qinling pandas), painted panda UI "
                   "portraits, and automatic panda markings for modded factions. Outfits, hats, injuries, wet fur, "
                   "contamination and carried goods all still fit.",
    "RequiredMods": [],
    "OptionalMods": []
}
json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=2)

# models
put(f'{SRC}/BeaverAdult.Model.timbermesh', 'Characters/Beaver/BeaverAdult.Model.timbermesh')
put(f'{SRC}/BeaverChild.Model.timbermesh', 'Characters/Beaver/BeaverChild.Model.timbermesh')

# base-colour textures (adults 2048, kits 1024 like vanilla)
for fac in ('Folktails', 'IronTeeth'):
    for i in range(1, 6):
        put(f'{SRC}/tex_adult/BeaverAdult{i}.{fac}.png', f'Materials/Beavers/{fac}/Adult/BeaverAdult{i}.{fac}.png')
    for i in range(1, 4):
        dst = os.path.join(OUT, f'Materials/Beavers/{fac}/Child/BeaverChild{i}.{fac}.png')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        Image.open(f'{SRC}/tex_child/BeaverChild{i}.{fac}.png').resize((1024, 1024), Image.LANCZOS).save(dst, optimize=True)

# UI portraits
for fn in sorted(os.listdir(f'{SRC}/avatars')):
    if fn.endswith('.png'):
        dst = put(f'{SRC}/avatars/{fn}', f'Sprites/Avatars/{fn}')
        json.dump({"isSprite": True}, open(dst + '.meta.json', 'w'))

# runtime support for modded factions
put('/root/w/script/PandaReskin.dll', 'Scripts/PandaReskin.dll')
put('/root/w/script/PandaReskin.cs', 'Source/PandaReskin.cs.txt')

# thumbnail
if os.path.exists(f'{SRC}/thumbnail.png'):
    put(f'{SRC}/thumbnail.png', 'thumbnail.png')

open(os.path.join(OUT, 'README.md'), 'w').write("""# Panda Colonists v2 - Timberborn 1.x\n\n**Enable only one of Panda Colonists v1 / v2.** v2 = realistic adults + chibi-cute cubs.

Every beaver becomes a giant panda.

## What's replaced
* **Adult and kit models**: new panda bodies (big round head, round ears, short muzzle, chubby belly, puff tail).
  They play **all original animations** (61 adult, 39 kit), so every job, swim, zipline, dance and sleep works.
* **Fur textures**: 5 adult + 3 kit variants per faction.
  * Folktails: classic, cream, snowy, honey and a rare brown *Qinling* panda.
  * Iron Teeth: slate, ash, steel, soot-grimed industrial and a Qinling.
* **UI portraits**: painted panda avatars, contaminated avatars and new-game portraits for both factions.
* **Modded factions**: any faction mod that uses the standard beaver body becomes pandas automatically
  (via `Scripts/PandaReskin.dll`). Without such mods the script does nothing.

## Compatibility
* Texture layout of the original beaver is preserved, so worker outfits, hats, injuries, bee stings, wet fur,
  badwater contamination, carried goods and backpacks all still line up.
* Pandas have a short puff tail, so custom *tail decals* (Tails & Banners) only show as a small patch on it.
* Overrides: `Characters/Beaver/BeaverAdult.Model`, `Characters/Beaver/BeaverChild.Model`,
  `Materials/Beavers/*/(Adult|Child)/*`, `Sprites/Avatars/*`. Mods replacing the same files will conflict;
  whichever loads later wins.
* Safe to add to or remove from an existing save (purely visual).

## Performance
Panda bodies have ~2x the vertices of the beaver for smoother heads and ears; total extra VRAM is roughly
150-250 MB (higher-resolution fur + animation data). No CPU cost.
""")

tot = 0
for r, ds, fs in os.walk(OUT):
    for f in fs:
        p = os.path.join(r, f); tot += os.path.getsize(p)
        print(f'{os.path.getsize(p)/1e6:8.2f} MB  {os.path.relpath(p, OUT)}')
print(f'total {tot/1e6:.1f} MB')
