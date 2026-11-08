import os
# folder holding files extracted from your own Timberborn install (characters/, materials/)
EXT = os.environ.get('TIMBERBORN_EXTRACT', '/root/w/ext')
"""Landmark-fitted panda proportions for each source model (game units, rest pose)."""

ADULT = dict(
    name='BeaverAdult',
    path=EXT + '/characters/beaver/beaveradult.model.timbermesh',
    height=0.53, scale=1.0,
    arm_island_x=0.09,
    neck_y=(0.315, 0.355), head_zmin=-0.06, head_strength=1.0,
    cranium=dict(c=(0, 0.450, 0.045), r=(0.122, 0.090, 0.102)),
    cheek=dict(c=(0.066, 0.410, 0.085), r=(0.070, 0.058, 0.068), k=0.035),
    muzzle=dict(c=(0, 0.412, 0.132), r=(0.053, 0.044, 0.054), k=0.035),
    jaw=dict(c=(0, 0.384, 0.088), r=(0.078, 0.042, 0.078), k=0.060),
    ear=dict(c=(0.088, 0.520, 0.018), r=0.037, h=0.036, thick=0.55, sharp=0.75, normal_mix=0.55, splay=0.25),
    eye=(0.050, 0.478, 0.135), nose=(0, 0.446, 0.200),
    body=dict(belly_c=(0, 0.160, -0.058), belly_r=(0.152, 0.160, 0.140),
              chest_c=(0, 0.272, -0.030), chest_r=(0.128, 0.095, 0.118), k=0.06,
              strength=0.70, inward_keep=0.35, limb_fade=0.07, leg_fade=(0.08, 0.16)),
    limbs=dict(arm=0.007, leg=0.008, arm_fade=0.10, leg_len=0.16),
    tail_root=(0, 0.095, -0.205), tail_bind_zone=0.03,
    tail_stub=dict(len=0.055, w=0.040, h=0.030, dy=0.010),
    teeth_hide=(0, 0.405, 0.135),
    bind_radius=0.03,
    smooth_iters=5,
    cavity=dict(free_uv=(0.8496, 0.9180), free_r=0.044),
    node_adjust={'#Head': dict(dpos=(0, 0.010, -0.004), scale=1.15)},
    beaver_ao=EXT + '/materials/beavers/common/adult_ao_2k.png',
)

CHILD = dict(
    name='BeaverChild',
    path=EXT + '/characters/beaver/beaverchild.model.timbermesh',
    height=0.32, scale=0.6,
    arm_island_x=0.06,
    neck_y=(0.190, 0.222), head_zmin=-0.04, head_strength=1.0,
    cranium=dict(c=(0, 0.270, 0.030), r=(0.088, 0.068, 0.074)),
    cheek=dict(c=(0.047, 0.244, 0.058), r=(0.050, 0.042, 0.048), k=0.025),
    muzzle=dict(c=(0, 0.247, 0.084), r=(0.036, 0.029, 0.034), k=0.024),
    jaw=dict(c=(0, 0.228, 0.055), r=(0.056, 0.030, 0.054), k=0.040),
    ear=dict(c=(0.064, 0.316, 0.008), r=0.027, h=0.025, thick=0.58, sharp=0.75, normal_mix=0.55, splay=0.25),
    body=dict(belly_c=(0, 0.095, -0.030), belly_r=(0.088, 0.098, 0.094),
              chest_c=(0, 0.163, -0.012), chest_r=(0.076, 0.060, 0.076), k=0.04,
              strength=0.70, inward_keep=0.35, limb_fade=0.045, leg_fade=(0.05, 0.10)),
    limbs=dict(arm=0.005, leg=0.0055, arm_fade=0.065, leg_len=0.10),
    tail_root=(0, 0.048, -0.118), tail_bind_zone=0.02,
    tail_stub=dict(len=0.036, w=0.026, h=0.020, dy=0.006),
    teeth_hide=(0, 0.250, 0.075),
    bind_radius=0.02,
    smooth_iters=5,
    beaver_ao=EXT + '/materials/beavers/common/child_ao_1k.png',
    cavity=dict(region=dict(z=0.06, y=(0.205, 0.252), y_top=0.258), target_xy=(0.040, 0.240),
                free_uv=(0.8262, 0.9590), free_r=0.020),
)

# ------------------------------------------------------------------ v2: more panda, less beaver
import copy as _copy

ADULT_V2 = _copy.deepcopy(ADULT)
ADULT_V2.update(
    cranium=dict(c=(0, 0.452, 0.040), r=(0.130, 0.094, 0.106)),          # wide, round skull
    cheek=dict(c=(0.062, 0.410, 0.080), r=(0.074, 0.062, 0.070), k=0.055),  # full cheeks, blended round
    muzzle=dict(c=(0, 0.410, 0.140), r=(0.050, 0.042, 0.060), k=0.038),   # real panda snout
    jaw=dict(c=(0, 0.380, 0.085), r=(0.088, 0.046, 0.082), k=0.060),
    ear=dict(c=(0.094, 0.518, 0.012), r=0.042, h=0.040, thick=0.55, sharp=0.70, normal_mix=0.50, splay=0.35),
    body=dict(belly_c=(0, 0.158, -0.060), belly_r=(0.165, 0.168, 0.150),
              chest_c=(0, 0.278, -0.032), chest_r=(0.148, 0.100, 0.128), k=0.07,
              strength=0.85, inward_keep=0.30, limb_fade=0.06, leg_fade=(0.07, 0.15)),
    limbs=dict(arm=0.004, leg=0.004, arm_fade=0.10, leg_len=0.16),
    tubes=dict(arm_reach=0.05, arm_scale=1.55, paw_scale=1.30, paw_len=0.07, bin=0.008,
               leg_reach=0.17, leg_scale=1.40, foot_y=0.035,
               paw_short=0.78, paw_wide=1.12, paw_puff=1.35, paw_anchor_dz=-0.02),
)

CHILD_V2 = _copy.deepcopy(CHILD)
CHILD_V2.update(
    neck_y=(0.180, 0.215),
    cranium=dict(c=(0, 0.272, 0.028), r=(0.104, 0.088, 0.088)),           # oversized round head
    cheek=dict(c=(0.042, 0.246, 0.056), r=(0.054, 0.048, 0.052), k=0.040),  # chubby cheeks, kept inside the round silhouette
    muzzle=dict(c=(0, 0.250, 0.082), r=(0.031, 0.025, 0.030), k=0.024),   # tiny button snout
    jaw=dict(c=(0, 0.230, 0.050), r=(0.062, 0.032, 0.058), k=0.040),
    ear=dict(c=(0.072, 0.330, 0.006), r=0.032, h=0.029, thick=0.62, sharp=0.65, normal_mix=0.50, splay=0.30),
    body=dict(belly_c=(0, 0.092, -0.028), belly_r=(0.096, 0.100, 0.100),
              chest_c=(0, 0.160, -0.012), chest_r=(0.082, 0.058, 0.080), k=0.045,
              strength=0.90, inward_keep=0.30, limb_fade=0.04, leg_fade=(0.045, 0.09)),
    limbs=dict(arm=0.003, leg=0.003, arm_fade=0.065, leg_len=0.10),
    tubes=dict(arm_reach=0.035, arm_scale=1.55, paw_scale=1.35, paw_len=0.045, bin=0.006,
               leg_reach=0.10, leg_scale=1.45, foot_y=0.022,
               paw_short=0.72, paw_wide=1.15, paw_puff=1.45, paw_anchor_dz=-0.012),
)


CHILD_V3 = CHILD_V2   # same body; only the painted eye placement changes (see make_textures.py)
