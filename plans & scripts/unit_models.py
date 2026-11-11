"""Sketchfab (CC BY 4.0) Star Wars vehicles -> animated HOI4 unit models for the walker battalions.

  blender -b --factory-startup --python "WIPGFX/plans & scripts/unit_models.py" -- convert [name ...]
  python "WIPGFX/plans & scripts/unit_models.py" textures      source PNGs -> diffuse / normal / spec DDS
  python "WIPGFX/plans & scripts/unit_models.py" wire          gfx/entities/hod_sw_walkers.{gfx,asset}

Models go to gfx/models/units/hod_walkers/<name>.mesh + <name>_<anim>.anim. Rigs are rebuilt for the game: the
source animation is baked onto a small skeleton (dropped bones hand their skin weights to the nearest kept ancestor),
the mesh is decimated, nose to -Y, ground at z = 0 (the vanilla convention, checked against iron_strider.mesh).

CREDITS (CC BY 4.0, author must be credited):
  AT-TE Walker (Animated) - R3negadeAidan   https://sketchfab.com/3d-models/at-te-walker-animated-81ef81cf6c554055b741b43a1a08d69f
  -Star Wars- AAT - ARKON-83                 https://sketchfab.com/3d-models/star-wars-aat-9ed126f4616a482fabee52b0e0d46e52
  AT-RT - Just Ryk                           https://sketchfab.com/3d-models/at-rt-6796698b4d564377838c06319ec96f90
"""
import json, math, os, re, sys

WIP = "WIPGFX" if os.path.isdir("WIPGFX") else "../ProjectKessilianWIPGFX/ProjectKessilianWIP"   # run from the mod root
SRC = WIP + "/3d/sketchfab"
OUT = "gfx/models/units/hod_walkers"
SIDE = WIP + "/3d/sketchfab/_baked/unit_models.json"     # texture sources per material, written by convert
TEX_PX = 1024

# keep: bones of the game rig (regex on source bone names); length: largest horizontal extent in mesh units;
# anims: game animation -> (source action or None, first frame, last frame)
SPECS = {
    "hod_atte": dict(src="at-te_walker_animated", mode="bake", length=10.0, tris=12000, protect=r"Turret",
                     keep=r"(GLTF_created_0_rootJoint|Hips_56|Head_21|Butt_36|Hips_Offset_55|Turret_Base_Pivot_13|Turret_12"
                          r"|Turret_Barrel_11|(Left|Right)(Front|Back)(Shoulder|Leg|LowLeg)_\d+|(Left|Right)Middle(Leg|LowLeg)_\d+"
                          r"|(Left|Right)(Front|Back|Middle)Ankle_\d+)$",
                     gun="Turret_Barrel_11", forward="Head_21", back="Butt_36",   # heading: rear section -> head
                     anims={"idle": (None, 0, 1), "move": (None, 0, 480), "attack": (None, 0, 1)}),
    "hod_aat": dict(src="-star_wars-_aat", mode="bake", length=8.0, tris=7000, keep=r".*", gun="Main Gun_02",
                    forward="Main Gun_end_05", norm_action="Static_Object_9",   # turret centred: the idle swings it
                    anims={"idle": ("Idle_Object_9", 0, 150), "move": ("Idle_Object_9", 0, 150), "attack": ("Static_Object_9", 0, 1)}),
    "hod_atrt": dict(src="at-rt", mode="rebuild", height=6.0, tris=7500,
                     # Phase I clone at AT-RT scale (3.2 m walker, 1.83 m trooper); offset from the controls to the saddle
                     rider=dict(src=WIP + "/3d/_glb/rider_clone_p1.glb", scale=0.46, offset=(0.0, -0.1, -0.2))),
}
# Battlefront II mod-tools models (F:/BF2_ModTools, msh_to_glb.py -> WIP/3d/_glb/bf2): static, one root bone; hover
# craft bob. length = longest horizontal extent, height = top of the model (map units, entity scale 1.0)
_BF2 = WIP + "/3d/_glb/bf2"
for _n, _kw in {
    "rep_hover_fightertank": dict(length=5.5, hover=True), "imp_hover_fightertank": dict(length=5.5, hover=True),
    "cis_tread_tank": dict(length=5.0), "cis_tread_hailfire": dict(length=4.5),
    "rep_hover_barcspeeder": dict(length=3.5, hover=True),
    "rep_hover_speederbike": dict(length=3.0, hover=True,   # 614-AvA: Phase II clone rider
                                  rider=dict(src=WIP + "/3d/_glb/rider_clone_p2.glb", scale=0.22, offset=(0.0, 0.6, 0.6), tris=2000)), "cis_hover_stap": dict(height=3.0, hover=True),
    # planes (fighters ~3 long like the TIE, gunships / transports / bombers bigger)
    "rep_fly_arc170fighter": dict(length=3.4, plane=True), "rep_fly_vwing": dict(length=3.0, plane=True),
    "rep_fly_anakinstarfighter": dict(length=2.8, plane=True), "all_la_at_gunship": dict(length=4.5, plane=True),
    "cis_fly_droidfighter": dict(length=3.0, plane=True), "cis_fly_tridroidfighter": dict(length=3.0, plane=True),
    "cis_fly_droidgunship": dict(length=4.5, plane=True), "cis_fly_maf": dict(length=3.0, plane=True),
    "cis_fly_greviousfighter": dict(length=3.2, plane=True), "imp_fly_trooptrans": dict(length=4.5, plane=True),
    "all_fly_ywing": dict(length=3.8, plane=True), "imp_fly_tiefighter": dict(length=2.6, plane=True),
    "imp_fly_tiebomber": dict(length=3.0, plane=True), "imp_fly_tieinterceptor": dict(length=2.6, plane=True),
    # Conversion Pack (DATA/_LVL_PC/SIDE vehicles / items / alt .lvl, swbf-unmunge -> WIP/3d/bf2_unmunge), 2026-11-08
    "rep_walk_sphat": dict(length=9.0, legs=dict(n=12, top=0.35, swing=10)), "cis_hover_mtt": dict(length=8.0, hover=True),
    "cis_hover_gat": dict(length=4.5, hover=True), "cis_hover_hag": dict(length=6.0, hover=True),
    "rep_hover_swampspeeder": dict(length=4.5, hover=True),
    # Old Republic speeder bike (BF2 community model, WIP/3d/Raxus Prime/Old_Republic_Speederbike): infantry support platform
    "orp_hover_speederbike": dict(length=3.2, hover=True,
                                  rider=dict(src=WIP + "/3d/_glb/rider_clone_p1.glb", scale=0.19, offset=(0.0, 0.45, 0.58), tris=2000)),
    "rep_fly_v19": dict(length=3.0, plane=True), "rep_fly_jedifighter": dict(length=2.6, plane=True),
    "imp_fly_shuttleproto": dict(length=4.5, plane=True), "cis_fly_geofighter": dict(length=3.0, plane=True),
    "cis_fly_scarab": dict(length=2.8, plane=True), "arc_la_at_gunship": dict(length=4.5, plane=True),
    # 2026-11-08 (user): Republic BTL-B Y-wing (WIP/3d/YWing), AAC-1 speeder tank (WIP/3d/rebel_bf3_tank, BF3 hover tank)
    # replacing the PX-10, 74-Z = BF2's Imperial speeder bike with a stormtrooper (scout) rider
    "rep_fly_ywing": dict(length=3.8, plane=True), "all_bf3_hover_tank": dict(length=6.0, hover=True),
    # Separatist fighter tank (BF2 Classic LGD folder, SIDE/cis.lvl via swbf-unmunge): CIS heavy repulsor tank droid
    "cis_hover_fightertank": dict(length=6.0, hover=True),
    "imp_hover_speederbike": dict(length=3.0, hover=True,
                                  rider=dict(src=WIP + "/3d/_glb/rider_clone_storm.glb", scale=0.22, offset=(0.0, 0.6, 0.6), tris=2000)),
}.items():
    SPECS[f"hod_{_n}"] = dict(src=f"{_BF2}/{_n}.glb", mode="glb_static", tris=5000, tex_px=512, **_kw)   # sources are <= 512 px
# hover tanks with a clone gunner standing in the turret hatch (2026-11-08, user): TX-130S (2nd tank tech) and the 2-M
# Saber (last tank tech). BF2's Imperial fighter tank is the same mesh in grey.
_GUNNER = dict(scale=0.17, offset=(0.0, 1.45, 1.45), tris=2000)   # TX-130S: Phase II clone, 2-M: stormtrooper (user)
SPECS["hod_tx130s"] = dict(SPECS["hod_rep_hover_fightertank"], rider=dict(_GUNNER, src=WIP + "/3d/_glb/rider_clone_p2.glb"))
SPECS["hod_saber2m"] = dict(SPECS["hod_imp_hover_fightertank"], rider=dict(_GUNNER, src=WIP + "/3d/_glb/rider_clone_storm.glb"))
# Sketchfab downloads (glb, static like the BF2 ones; yaw = degrees about Z that point the nose to -Y). CREDITS:
#   AT-OT All Terrain Open Transport die-cast - dandruffkielbasa (CC BY-NC)  sketchfab.com/3d-models/6b076a8badd6428aa33f4e426a18f95d
#   Star Wars Empire Troop Transport | Andor - Losss (CC BY-SA)              sketchfab.com/3d-models/a33a4d5fceb74b929dbabb3cb5506b29
#   Clone Turbo Tank HAVw A6 Juggernaut - bruhepic925 (CC BY)                sketchfab.com/3d-models/4e331a37fe614fc783f0dcbcb77310cb
SPECS["hod_atot"] = dict(src=WIP + "/3d/at-ot_all_terrain_open_transport_die-cast.glb", mode="glb_static", tris=12000, tex_px=1024, length=7.0, yaw=90, rebake=True, drop=r"Cube$",
                         legs=dict(n=6, top=0.5))
SPECS["hod_itt"] = dict(src=WIP + "/3d/star_wars_empire_troop_transport__andor.glb", mode="glb_static", tris=6000, tex_px=1024, length=5.5, hover=True, yaw=180)
# AT-AP: WIP/3d/at-ap (source unknown), static: no walk cycle yet. (AT-XT: BF2 Conversion Pack rep_walk_atxt)
# Republic at War (EaW mod; credits.txt lines required, see CREDITS.md) rigged + animated via alo_to_glb.py --anim
RAW = WIP + "/3d/_glb/raw_anim"
def _RAW_A(idle="idle_00", move="move_00", attack=None):    # action name prefixes (case as in the .ala names); None end = whole action
    # standing units play idle: the EaW idle action (walkers must not walk on the spot)
    return {"idle": (idle, 0, None), "move": (move, 0, None), "attack": (attack or idle, 0, None)}
SPECS["hod_rev_atte"] = dict(src=RAW + "/rev_atte.glb", mode="bake", length=10.0, tris=8000, protect=r"Barrel|turret|Turret",
                             # side turrets fold into the hull, shadow bones dropped (bone budget <= 76 like vanilla)
                             keep=r"(?!.*shadow)(Bone_Root|Mesh_(Thorax|Frontshell|Backshell|[Ll]eg\w+)|Bone_Foot(FL|FR|ML|MR|BL|BR)|Turret_00|Barrel_0\d)$",
                             gun="Barrel_00", forward="Mesh_Frontshell", back="Mesh_Backshell", anims=dict(_RAW_A(attack="attack_00"), idle=("movestart_00", 0, 1)))   # no idle action: the standing pose before it moves off
SPECS["hod_rev_atrt"] = dict(src=RAW + "/rev_atrt.glb", mode="bake", height=6.0, tris=5000, protect=r"Gun",
                             keep=r"(?!.*shadow)(root|bPelvis|b_(back|chest|head|[lr](clav|bicep|forearm|hand)|lhip|rhip|lthigh|rthigh|lcalf|rcalf|lfoot|rfoot)|[LR][Ll]eg\d|[LR]foot|Gun01|Cylinder04)$",
                             gun="Gun01", forward="Gun01", back="b_back", anims=_RAW_A("IDLE_00", "MOVE_00"))
SPECS["hod_rev_sabertank"] = dict(src=RAW + "/rev_sabertank.glb", mode="bake", length=5.5, tris=4000, protect=r"Cannon", hover=True,
                                  keep=r"(main|Cannon_[LR])$", gun="Cannon_L", forward="Cannon_L", back="main",
                                  anims=_RAW_A("IDLE_00", "MOVE_00", "ATTACK_00"))
SPECS["hod_rev_juggernaut"] = dict(src=RAW + "/rev_a6_juggernaut.glb", mode="bake", length=7.5, tris=6000, protect=r"barrel",
                                   keep=r"(b_hip|b_\w*wheel\w*|b_turret(_01)?|b_barrel|window)$", gun="b_barrel",
                                   forward="b_1st_left_wheel", back="b_5th_left_wheel", anims=_RAW_A())
SPECS["hod_rev_utat"] = dict(src=RAW + "/rev_utat.glb", mode="bake", length=8.0, tris=5000, protect=r"Barrel",
                             keep=r"(Hull|Turret|Barrel)$", gun="Barrel", forward="Barrel", back="Hull", anims=_RAW_A("IDLE_00", "MOVE_00"))
SPECS["hod_rev_barc"] = dict(src=RAW + "/rev_barc_speeder.glb", mode="bake", length=3.5, tris=4000, hover=True,
                             keep=r"B_(Bike|Pelvis|Chest|Head|Backpack|Bicep_[LR]|FArm_[LR]|Hand_[LR]|Thigh_[LR]|Calf_[LR]|Foot_[LR])$",
                             gun="B_Bike", forward="B_Hand_R", back="B_Pelvis", anims=_RAW_A())
# Battlefront II walkers with their own BF2 walk cycles (msh_anim_to_glb.py -> WIP/3d/_glb/bf2_anim; the AT-XT walks
# with the AT-ST clips, skel=imp_walk_atst.msh). idle / attack = the BF2 idle clip (standing), move = the walk
BF2A = WIP + "/3d/_glb/bf2_anim"
_WALK = {"idle": ("idle", 0, None), "move": ("walk", 0, None), "attack": ("idle", 0, None)}
SPECS["hod_imp_walk_atst"] = dict(src=BF2A + "/imp_walk_atst.glb", mode="bake", height=8.0, tris=5000, protect=r"barrel|aimer",
                                  keep=r"(bone_(root|pelvis|neck|head|[lr]_(thigh|calf|foot|ball|toe))|aimer_\w+|barrel_[lr]gun)$",
                                  gun="barrel_lgun", forward="barrel_lgun", back="bone_root",
                                  anims=dict(_WALK, attack=("idle", 0, None)))   # stands (BF2 idle sway) while firing
SPECS["hod_rep_walk_atxt"] = dict(src=BF2A + "/rep_walk_atxt.glb", mode="bake", height=8.0, tris=5000, protect=r"[Bb]arrel|Aimer",
                                  keep=r"(bone_(root|pelvis|neck|head|[lr]_(thigh|calf|foot|ball|toe))|cube5|Barrel_\d|barrel_mortar_[LR]|Aimer_mortar_[LR])$",
                                  gun="Barrel_1", forward="Barrel_1", back="bone_root", anims=_WALK)
SPECS["hod_lance_walker"] = dict(src=BF2A + "/orp_walk_lance.glb", mode="bake", height=8.0, tris=6000, protect=r"barrel|aimer|turret",
                                 # Old Republic lance walker (BF2 mod, WIPGFX/3d/old_republic_lance_walker): AT-ST skeleton
                                 keep=r"(bone_(root|pelvis|neck|head|[lr]_(thigh|calf|foot|ball|toe))|aimer_\w+|barrel_(left|right|mid))$",
                                 gun="barrel_mid", forward="barrel_mid", back="bone_root", anims=_WALK)
# BF2 droids / one-man AT-ST with their own walk clips (msh_anim_to_glb.py, skel = the clip folder's basepose.msh)
SPECS["hod_cis_walk_spider"] = dict(src=BF2A + "/cis_walk_spider.glb", mode="bake", height=4.5, tris=5000,
                                    keep=r"bone_\w+$", gun="bone_root", forward="bone_fl_foot", back="bone_bl_foot", anims=_WALK)
SPECS["hod_cis_walk_dwarfspider"] = dict(src=BF2A + "/cis_walk_dwarfspider.glb", mode="bake", height=3.0, tris=5000, protect=r"[Aa]imer",
                                         keep=r"(bone_\w+|aimer_y_head|Aimer_x_Gun)$", gun="Aimer_x_Gun", forward="bone_fl_foot",
                                         back="bone_bl_foot", anims=_WALK)
SPECS["hod_cis_walk_droideka"] = dict(src=BF2A + "/cis_walk_droideka.glb", mode="bake", height=2.5, tris=5000, protect=r"gun",
                                      keep=r"bone_\w+$", gun="bone_r_gun", forward="bone_head", back="bone_b_leg2", anims=_WALK)
SPECS["hod_rep_walk_oneman_atst"] = dict(src=BF2A + "/rep_walk_oneman_atst.glb", mode="bake", height=6.0, tris=5000, protect=r"aimer",
                                         keep=r"(bone_\w+|aimer_[xy])$", gun="aimer_x", forward="aimer_x", back="bone_root", anims=_WALK)
SPECS["hod_imp_walk_atat"] = dict(src=BF2A + "/imp_walk_atat.glb", mode="bake", height=11.0, tris=6000, protect=r"barrel|aimer",
                                  keep=r"(bone_\w+|aimer_\w+|barrel_[LR]cannon)$",
                                  gun="barrel_Lcannon", forward="aimer_head", back="bone_root", anims=_WALK)
# AT-AT prototype: SWBF3 Clone Wars AT-AT (BF2 community port, WIP/3d/swbf3 clone wars atat) walking with the BF2 AT-AT clips
SPECS["hod_cw_atat"] = dict(SPECS["hod_imp_walk_atat"], src=BF2A + "/swbf3_cw_atat.glb", height=10.5,
                          tint=(128, 130, 134), tint_dark=(78, 80, 86), tint_cut=0.75)   # user 2026-11-09: gunmetal like the Men of War AT-AT Rep
# New Order Mod (EaW) free assets, CC BY-NC-SA 2.0, model/texture Du}{, rigging/edits Sudno (alo_to_glb.py, static):
# T4-B heavy tank = the heavy repulsor tank slot, T-16 Skyhopper = first Republic fighter (2026-11-08, user)
SPECS["hod_t4b"] = dict(src=WIP + "/3d/_glb/eaw/rv_t4btank.glb", mode="glb_static", tris=6000, tex_px=1024, length=6.5, turrets=[r"Turret_00|Barrel_0"])
SPECS["hod_t16"] = dict(src=WIP + "/3d/_glb/eaw/reb_t16.glb", mode="glb_static", tris=4000, tex_px=1024, length=3.0, plane=True)
# Thrawn's Revenge 3.3 (EaW mod, user's copy C:/Users/steve/Desktop/ThrawnsRevenge33; permission needed before release, see
# CREDITS.md): Rebels-era AT-RT (animated, 979 light walker tech), K79-S80 troop transport, Imperial drop transport, Theta shuttle
TR = WIP + "/3d/_glb/thrawn"
SPECS["hod_tr_atrt"] = dict(src=RAW + "/at-rt.glb", mode="bake", height=6.0, tris=5000, protect=r"Barrel",
                            keep=r"(centre|hip2?\.[LR]|calf\.[LR]|foot\.[LR]|Turret_00|Barrel_00|B_(Pelvis|Chest|Head|Bicep_[LR]|FArm_[LR]|Hand_[LR]|Thigh_[LR]|Calf_[LR]|Foot_[LR]))$",
                            gun="Barrel_00", forward="Barrel_00", back="centre", anims=_RAW_A("Idle_00", "Move_00"))
SPECS["hod_tr_itt"] = dict(src=TR + "/imperialtrooptransport.glb", mode="glb_static", tris=5000, tex_px=1024, length=5.5, hover=True)
SPECS["hod_tr_idt"] = dict(src=TR + "/imperial_dropship_transport.glb", mode="glb_static", tris=5000, tex_px=1024, length=4.5, plane=True)
SPECS["hod_tr_ataa"] = dict(src=WIP + "/3d/_glb/eaw_vanilla/ev_at-aa.glb", mode="glb_static", tris=5000, tex_px=1024, height=3.5, legs=dict(n=4, top=0.4, swing=12))   # 2026-11-09 procedural legs: its EaW clips are the old base-EaW .ala format the importer cannot read. AT-AA (vanilla EaW EV_AT-AA.ALO + its real EV_AT-AA.DDS from the game .meg, 2026-11-09; was TR + damage texture)
SPECS["hod_tr_spmat"] = dict(src=TR + "/ev_spmat.glb", mode="glb_static", tris=6000, tex_px=1024, length=7.5, legs=dict(n=6, top=0.35, swing=10))   # SPMA-T (2026-11-08), procedural legs 2026-11-09
SPECS["hod_tr_theta"] = dict(src=TR + "/theta-class_t-2c_shuttle_land.glb", mode="glb_static", tris=5000, tex_px=1024, length=4.5, plane=True)
# 2026-11-08 (user, WIP/3d/b; EaW mod assets, credits in CREDITS.md): AT-ACT (Star Wars Pinball model, rig Warper243, animated),
# AT-TC troop carrier (kubli), Imperial heavy repulsortank (kubli), RM-09 shuttle. alo_to_glb.py from WIP/3d/b/_staged (EaW MODELS/TEXTURES layout)
EAW2 = WIP + "/3d/_glb/eaw2"
SPECS["hod_atact"] = dict(src=RAW + "/ev_imperial_construction_atat_walker.glb", mode="bake", height=12.0, tris=7000, protect=r"Barrel|Turret",
                          keep=r"(B_Body|B_(Hip|Thigh|Shin|Leg|Foot|Toes)_[LR]0\d|B_Turret(_0\d)?|B_Head|B_Barrel_0\d)$",
                          gun="B_Barrel_00", forward="B_Head", back="B_Body", anims=_RAW_A("idle_00", "move_00"))
SPECS["hod_attc"] = dict(src=EAW2 + "/ev_at_tc.glb", mode="glb_static", tris=6000, tex_px=1024, length=6.5, turrets=[r"(Turret|Barrel)_L", r"(Turret|Barrel)_R"])
SPECS["hod_ihrt"] = dict(src=EAW2 + "/ev_heavy_repulsortank.glb", mode="glb_static", tris=7000, tex_px=1024, length=6.5, hover=True)
SPECS["hod_rm09"] = dict(src=EAW2 + "/rv_rm-09_transport.glb", mode="glb_static", tris=4000, tex_px=1024, length=4.5, plane=True)
# Fall of the Republic 1.4 (EaW mod, user's copy C:/Users/steve/Desktop/FotR14; permission/credits: see CREDITS.md):
# AT-OT, animated, its 4 guns on their hardpoint bones (alo_to_glb.py --anim main+Bone=part)
SPECS["hod_fotr_atot"] = dict(src=RAW + "/rep_atot.glb", mode="bake", length=8.0, tris=8000, protect=r"Gun",
                              keep=r"(Body|Head|Gun[BF]\.[LR]|(BodyJoint|UpperLeg|TopJoint|BottomJoint|Foot)\d\.[LR])$",
                              gun="GunF.L", forward="Head", back="Body", anims=_RAW_A("Idle_00", "Move_00"))
# Fall of the Republic 1.4 batch (2026-11-08, user: "convert them all" except heavy transports). Static: alo_to_glb.py -> 3d/_glb/fotr
FOTR = WIP + "/3d/_glb/fotr"
# glb_static turrets (2026-11-09): procedural turret bones, the main gun and the two artillery tops of the super tanks
_SUPER = [r"^(Turret|Barrel)_baked", r"(Turret|Barrel)\.002", r"ArtilleryTop_low_baked", r"ArtilleryTop_low\.002"]
for _n, _f, _kw in (("av7", "av7_antivehicle_cannon", dict(length=5.0, turrets=[r"barrel|console|body"])), ("utaa", "rep_utaa", dict(length=7.0, turrets=[r"UTAA\.00[23]"])),
                    ("sphat", "spha-t", dict(length=9.0)), ("aat", "armored_assault_tank", dict(length=6.5, hover=True)),
                    ("persuader", "cis_persuadertank", dict(length=7.0)), ("hagm", "cis_hagm", dict(length=6.0, hover=True)),   # persuader: no turret, its top is the drive wheel
                    ("supertank", "tradefed_super_tank", dict(length=8.0, turrets=_SUPER)), ("gat", "cis_gat", dict(length=5.0, hover=True)),
                    ("hailfire", "hailfire", dict(length=5.0)),
                    ("v19", "pa_torrent", dict(length=3.0, plane=True)), ("btlb", "btl-b_y-wing", dict(length=4.0, plane=True)),
                    ("arc170", "arc-170_starfighter", dict(length=4.0, plane=True)), ("laat", "low_altitude_assault_transport", dict(length=4.5, plane=True)),
                    ("hmp", "hmp_lander", dict(length=4.5, plane=True)),
                    ("utat", "unstable_terrain_artillery_transport", dict(length=7.5, turrets=["mount"]))):   # UT-AT artillery (2026-11-08)
    SPECS["hod_fotr_" + _n] = dict(src=f"{FOTR}/{_f}.glb", mode="glb_static", tris=6000, tex_px=1024, **_kw)
# animated (alo_to_glb.py --anim -> raw_anim)
# SPHA: body + its SPHA-T turbolaser part on Attach_00 (FotR HP_SPHAT_Main): --anim raw_anim Self_Propelled_Heavy_Artillery.alo+Attach_00=SPHA-T.alo, then fix_spha_gun.py (gun on the hull top)
SPECS["hod_fotr_spha"] = dict(src=RAW + "/self_propelled_heavy_artillery.glb", mode="bake", length=10.0, tris=8000, protect=r"Attach",
                              keep=r"(Walker|Attach_0\d|(RootLeg|UpperLegLeg|LowerLegLeg)\d\.[LR])$",
                              gun="Attach_00", forward="RootLeg1.L", back="RootLeg6.L", anims=_RAW_A("Idle_00", "Move_00"))
SPECS["hod_fotr_j1"] = dict(src=RAW + "/j1_proton_cannon.glb", mode="bake", length=6.0, tris=5000, protect=r"Barrel",
                            keep=r"(Chassis|(Hip|Thigh|Calf|Foot)_[FB]\.[LR]|Barrel_00)$",
                            gun="Barrel_00", forward="Hip_F.L", back="Hip_B.L", anims=_RAW_A("Idle_00", "Move_00"))
SPECS["hod_fotr_crab"] = dict(src=RAW + "/cis_crab_droid.glb", mode="bake", length=5.0, tris=5000,
                              keep=r"(Body\w*|[LR]_Mandible)$", gun="L_Mandible", forward="L_Mandible", back="Body_L_rear_top",
                              anims=_RAW_A("Idle_00", "Move_00", "Attack_Idle_00"))
SPECS["hod_fotr_og9"] = dict(src=RAW + "/cis_og-9_homing_spider_droid.glb", mode="bake", height=6.0, tris=7000, protect=r"Attach",
                             keep=r"((Hip|Thigh|Calf|Foot)_[\w.]+|Attach_0\d)$", gun="Attach_00", forward="Hip_FR.R", back="Hip_BR.R",
                             anims=_RAW_A("idle_00", "move_00"))
# 2026-11-08 (user: "the CIS are a mess"): Separatist set from Fall of the Republic 1.4 (permission needed, see CREDITS.md)
for _n, _f, _kw in (("cis_supertank2", "confederate_super_tank", dict(length=8.0, turrets=_SUPER)),   # +Attach_00/01/02 = Top/Left/Right turrets
                    ("cis_protodeka", "cis_protodeka", dict(length=9.0, hover=True)), ("cis_haml", "cis_haml", dict(length=6.0, hover=True)),
                    ("cis_ca_artillery", "cis_ca_artillery", dict(length=7.0, turrets=[0.68])), ("cis_advestap", "cis_advestap", dict(height=4.5, hover=True)),
                    ("cis_stap", "cis_stap", dict(height=4.5, hover=True)), ("cis_transport", "cis_transport_land", dict(length=8.0, hover=True))):
    SPECS["hod_fotr_" + _n] = dict(src=f"{FOTR}/{_f}.glb", mode="glb_static", tris=6000, tex_px=1024, **_kw)
# MTTs (2026-11-08, user: "the MTT is open"): rigged, posed on the Idle clip = rack stowed, hatches shut; the 30k-face droid
# stack inside the rack is dropped
for _n, _f in (("mtt", "multi-troop_transport"), ("cis_mtt", "cis_multi-troop_transport")):
    SPECS["hod_fotr_" + _n] = dict(src=f"{RAW}/{_f}.glb", mode="bake", length=8.0, tris=7000, hover=True, drop=r"droid(s|pack)",
                                   keep=r"(hull|rack|rack_hinge_[12]|rack_tube|hatch|bottom_hatch|Attach_0[01])$",
                                   gun="Attach_00", forward="rack", back="hull", anims=_RAW_A("Idle_00", "Idle_00", "Idle_00"))
SPECS["hod_fotr_cis_dsd"] = dict(src=RAW + "/cis_dsd.glb", mode="bake", height=3.5, tris=5000,
                                 keep=r"(Body|Turret_00|MuzzleA_00|(Front|Back)(Hip|Thigh|Shin|Ankle|Foot)\.[LR])$",
                                 gun="MuzzleA_00", forward="MuzzleA_00", back="Body", anims=_RAW_A("Idle_00", "Move_00"))
SPECS["hod_fotr_cis_lr57"] = dict(src=RAW + "/cis_lr57.glb", mode="bake", height=7.0, tris=5000,
                                  keep=r"(Body|UpperBody|Arm\.[LR]|Hand\.[LR]|MuzzleA_0[0-3]|(Hip|Thigh|Shin|Foot)\.[LR])$",
                                  gun="MuzzleA_00", forward="MuzzleA_00", back="Body", anims=_RAW_A("Idle_00", "Move_00"))
SPECS["hod_fotr_cis_hagm"] = dict(src=RAW + "/cis_hagm.glb", mode="bake", length=6.5, tris=5000, hover=True,
                                  keep=r"(Turret|Barrel_00|MuzzleA_00)$", gun="MuzzleA_00", forward="MuzzleA_00", back="Turret",
                                  anims=_RAW_A("Idle_00", "Move_00", "Deploy_00"))
SPECS["hod_fotr_cis_tridroid"] = dict(src=RAW + "/cis_tridroid.glb", mode="bake", height=7.0, tris=6000,
                                      keep=r"(centre|Head|MuzzleA_0\d|(pelvis|hip|thigh|calf|foot)\d)$",
                                      gun="MuzzleA_00", forward="MuzzleA_00", back="centre", anims=_RAW_A("idle_00", "move_00"))
# 2026-11-09: hailfire animated (FotR hailfire.alo + its idle / move clips; was static)
SPECS["hod_fotr_hailfire"] = dict(src=RAW + "/hailfire.glb", mode="bake", length=5.0, tris=6000, drop=r"Icosphere",
                                  keep=r"(hull|wheel_[lr]|MuzzleA_00|MuzzleB_00)$", gun="MuzzleA_00", forward="MuzzleA_00", back="hull",
                                  anims=_RAW_A("idle_00", "Move_00"))
_DROID = r"(Pelvis|Chest|Neck|Head|Backpack|B_Attach_Gun|MuzzleA_00|(Shoulder|Bicep|Forearm|Hand|Hip|Thigh|Calf|Foot)\.[LR])$"
for _n, _f, _h in (("cis_b1", "b1_battledroid", 6.2), ("cis_b2", "cis_b2_sbd", 6.8), ("cis_bx", "bx_commando_droid", 6.4)):
    SPECS["hod_fotr_" + _n] = dict(src=f"{RAW}/{_f}.glb", mode="bake", height=_h, tris=4000, keep=_DROID, infantry=True,
                                   gun="MuzzleA_00", forward="MuzzleA_00", back="Pelvis", anims=_RAW_A("Idle_00", "Move_00", "AttackIdle_00"))
# 2026-11-08 (user: "reuse too much of the same armour", "the air tree misses a lot of different models", "droideka somewhere"):
# Fall of the Republic 1.4 (fotr) and Republic at War 1.2.1 (raw: static, raw_anim: rigged) extras, credits in CREDITS.md
RAWS = WIP + "/3d/_glb/raw"
for _n, _f, _kw in (("cis_maf", f"{FOTR}/cis_maf", dict(length=4.5, plane=True)), ("tf_maf", f"{FOTR}/tf_maf", dict(length=4.5, plane=True)),
                    ("csa_c1", f"{FOTR}/csa_c1defensedroid", dict(height=8.0)), ("hailfire_riot", f"{FOTR}/hailfire_riot_control", dict(length=5.0)),
                    ("c9979", f"{FOTR}/cis_c-9979_lander", dict(length=6.0, plane=True)),
                    ("sheathipede", f"{FOTR}/cis_sheathipede-class_transport_shuttle", dict(length=4.0, plane=True)),
                    ("vulture", f"{FOTR}/cis_vulturecis", dict(length=3.0, plane=True)), ("belb22", f"{FOTR}/cis_belbullab_22", dict(length=3.4, plane=True)),
                    ("belb24", f"{FOTR}/cis_belbullab_24", dict(length=3.6, plane=True)), ("trifighter", f"{FOTR}/cis_trifighter", dict(length=3.0, plane=True)),
                    ("nantex", f"{FOTR}/cis_nantex", dict(length=3.2, plane=True)), ("hyena", f"{FOTR}/cis_hyena", dict(length=3.8, plane=True)),
                    ("raw_hyena", f"{RAWS}/sev_hyena_bomber", dict(length=4.2, plane=True)),
                    ("raw_droidbomber", f"{RAWS}/sev_droid_bomber", dict(length=3.8, plane=True)), ("raw_ginivex", f"{RAWS}/sev_fanblade_fighter", dict(length=3.2, plane=True)),
                    ("raw_vulture", f"{RAWS}/sev_vulture", dict(length=3.0, plane=True)), ("raw_hmp", f"{RAWS}/sev_hmp", dict(length=4.5, plane=True))):
    SPECS["hod_x_" + _n] = dict(src=_f + ".glb", mode="glb_static", tris=5000, tex_px=1024, **_kw)
# droideka (FotR UI_DEKA, its own roll / deploy clips), RaW dwarf spider and crab droid (the second generation of each)
SPECS["hod_x_droideka"] = dict(src=RAW + "/ui_deka.glb", mode="bake", height=5.5, tris=4000, drop=r"Sphere", norm_action="IDLE_00",   # Sphere02 = shield bubble
                               keep=r"(?!IK Chain|Point01|MuzzleA_0\d_Flash|.*\.\d{3}$)[\w ]+$",
                               gun="MuzzleA_00", forward="MuzzleA_00", back="Dummy01", anims=_RAW_A("IDLE_00", "MOVE_00", "ATTACKIDLE_00"))
# Droideka Mk II (2026-11-09, user): Forces of Corruption UI_DROIDEKA (scorpion tail gun), from corruption/Data/models.meg
# (eaw_meg.py) + Patch.meg UI_DROIDEKA.DDS, alo_to_glb.py --anim
SPECS["hod_x_foc_deka2"] = dict(src=RAW + "/ui_droideka.glb", mode="bake", height=5.5, tris=4000, drop=r"(Sphere|Icosphere|collision)", norm_action="ATTACKIDLE_00",
                                keep=r"(?!Camera|collision|Sphere01|p_droideka|H$|.*\.\d{3}$)[\w ]+$",
                                gun="MuzzleA_00", forward="MuzzleA_00", back="b_hip", anims=_RAW_A("ATTACKIDLE_00", "WALK_00", "ATTACK_00"))   # IDLE_00 = rolled-up ball
SPECS["hod_x_raw_dwarf"] = dict(src=RAW + "/sev_dwarf_spider.glb", mode="bake", height=4.0, tris=4000,
                                keep=r"(B_body|B_Base|B_(Thigh|Shin|Foot|Toes)_[LR][RF]|MuzzleA_00)$",
                                gun="MuzzleA_00", forward="MuzzleA_00", back="B_body", anims=_RAW_A("idle_00", "move_00"))
SPECS["hod_x_raw_crab"] = dict(src=RAW + "/sev_crabdroid.glb", mode="bake", length=5.5, tris=4000,
                               keep=r"(B_Leg_\w+|B_Pelvis|B_Chest|top|Cylinder01|MuzzleA_0[01]|(Thigh|Calf)_0\d)$",
                               gun="MuzzleA_00", forward="MuzzleA_00", back="B_Pelvis", anims=_RAW_A("idle_00", "move_00"))
# 2026-11-08 CIS round 3 (user): old-pattern B1 (E-5), Republic Commando B1 (E-5s), hypothetical B3 (CIS special unit: FotR's black
# shoulder-launcher B2, cis_b2_sbd_ptl, on the B2 clips, scaled up), Espo walker (light walker), blue STAP (advanced droid rider), I-beam fighter, Sabaoth bomber
for _n, _f, _kw in (("blue_stap", f"{FOTR}/cis_blue_stap", dict(height=4.5, hover=True)), ("ibeam", f"{FOTR}/if_i_beam_fighter", dict(length=3.2, plane=True)),
                    ("sabaoth_bomber", f"{FOTR}/sabaoth_bomber", dict(length=4.2, plane=True)),
                    ("raw_aat_blue", f"{RAWS}/sev_aat_blue", dict(length=6.5, hover=True)),
                    ("clone_z95", f"{FOTR}/rep_clone_z95", dict(length=3.2, plane=True)), ("ntb630", f"{FOTR}/rep_ntb", dict(length=4.6, plane=True))):   # 2026-11-09 user: REP T-16 -> clone Z-95, BTL-A4 -> NTB-630   # 2026-11-09: CIS-colour AAT (RaW), hover tank 2
    SPECS["hod_x_" + _n] = dict(src=_f + ".glb", mode="glb_static", tris=5000, tex_px=1024, **_kw)
# Imperial-service AAT (user ref: green camo, rust): the FotR AAT repainted by camo() in textures()
SPECS["hod_x_imp_aat"] = dict(SPECS["hod_fotr_aat"], camo=True)
# Vulture Interceptor (GMod workshop "[LVS] Vulture Interceptor", cl_peregrine.mdl via source_mdl_to_obj.py; facing per model: the TIE droid and A-DSD needed yaw=-90)
SPECS["hod_x_vulture_interceptor"] = dict(src=WIP + "/3d/_glb/gmod/cis_vulture_interceptor.glb", mode="glb_static", tris=5000, tex_px=1024, length=3.0, plane=True, yaw=90, gain=1.5)
# Droid TIE (GMod workshop 1655057679 "[LFS] Mega Ship Pack", sfp_tiedroid.mdl via source_mdl_to_obj.py): CIS droid interceptor, 2026-11-09
SPECS["hod_x_tie_droid"] = dict(src=WIP + "/3d/_glb/gmod/cis_tie_droid.glb", mode="glb_static", tris=5000, tex_px=1024, length=3.2, plane=True, yaw=-90, gain=2.0,
                                tint=(112, 120, 136), tint_dark=(58, 92, 168), tint_cut=0.6,   # CIS repaint (user 2026-11-09): blue-grey hull, Separatist-blue panels
                                decal=WIP + "/3d/_glb/gmod/cis_tie_droid_decal.png")   # CIS emblem on the pod top: uv_decal.py sfp_tiedroid.obj OUT 1024 -64.5 0 22 100
# A-DSD (Star Wars: Republic Commando, Droid.ukx DwarfSpiderDroid + DroidTextures.utx, own UE2 reader rc_export.py; static, procedural legs)
SPECS["hod_x_rc_adsd"] = dict(src=WIP + "/3d/_glb/rc/rc_adsd.glb", mode="glb_static", tris=4000, tex_px=1024, height=5.0, yaw=-90, gain=1.4,
                              legs=dict(n=4, top=0.45, swing=12))
# Scorpenek annihilator droid stand-in (user 2026-11-09, light walker tech 4): no Scorpenek model exists in any source (FotR's own
# campaign uses a droideka for them too), so the Republic Commando droideka (Droid.ukx Droideka, deployed bind pose), big and gunmetal
SPECS["hod_x_rc_scorpenek"] = dict(src=WIP + "/3d/_glb/rc/rc_droideka.glb", mode="glb_static", tris=4000, tex_px=1024, height=7.5, yaw=-90,
                                   tint=(116, 118, 126), legs=dict(n=3, top=0.4, swing=10))
# user 2026-11-09 (full Republic at War, workshop 1129810972): Scorpenek (light walker 4, replaces the RC stand-in),
# Octuptarra in CIS blue/white (SeV_Octuptarra_Rocket, heavy walker 3), blue-grey Confederate AAT (SeV_AAT_CIS, hover tank 2)
SPECS["hod_x_raw_scorpenek"] = dict(src=RAW + "/sev_scorpenek.glb", mode="bake", height=7.5, tris=5000, drop=r"(Sphere|Icosphere|COL)",
                                    keep=r"(Body|b_barrel_00|Eyecap|cannon_0\d|muzzleA_0\d|(Leg|Joint|Shin|foot)_(FR|FL|BR|BL))$",
                                    gun="muzzleA_00", forward="muzzleA_00", back="Body", anims=_RAW_A("idle_00", "move_00", "attack_00"))
SPECS["hod_x_raw_octuptarra"] = dict(src=RAW + "/sev_octuptarra_rocket.glb", mode="bake", height=7.0, tris=6000, drop=r"Icosphere",
                                     keep=r"(Body|Head|GUNS|Barrel|MuzzleA_00|MuzzleB_00|(Hip|Leg|Shin|New_Foot)_0\d)$",
                                     gun="MuzzleA_00", forward="MuzzleA_00", back="Body", anims=_RAW_A("idle_00", "Move_00", "attack_00"))
SPECS["hod_x_raw_aat_cis"] = dict(src=RAWS + "/sev_aat_cis.glb", mode="glb_static", tris=5000, tex_px=1024, length=6.5, hover=True)
# TIE Mauler (vanilla EaW EV_TIECRAWLER.ALO = the game's "TIE Mauler"), hover tank 3 (crawler tech), Confederate blue-grey/white repaint
SPECS["hod_x_tie_mauler"] = dict(src=RAWS + "/ev_tiecrawler.glb", mode="glb_static", tris=5000, tex_px=1024, length=5.5,
                                 tint=(178, 184, 196), tint_dark=(58, 92, 168), tint_cut=0.7)
# Umbaran Mobile Heavy Cannon (user 2026-11-09: light walker tech 3, replaces the Class I): Men of War AS2 mod "ASV Star Wars"
# (workshop 244450/2608842652, usw_vehicles.pak con umbaran_hmc via mow_ply.py; static, procedural six legs) - PERMISSION NEEDED
SPECS["hod_x_umbaran_hmc"] = dict(src=WIP + "/3d/_glb/mow/con_umbaran_hmc.glb", mode="glb_static", yaw=-90, tris=5000, tex_px=1024, height=5.0,
                                  legs=dict(n=6, top=0.35, swing=10))
# user 2026-11-09, more from the Men of War "ASV Star Wars" mod (mow_ply.py, static, procedural legs) - PERMISSION NEEDED:
# B3 (CIS special), Scorpenek (light walker 4), Umbaran hover tank (hover tank 3, replaces the TIE Mauler);
# Republic: clone hover tank (heavy repulsortank slot), AT-AT Rep (AT-AT prototype slot). Men of War models face +X: yaw=-90 (turns +X to the -Y nose)
_MOW = WIP + "/3d/_glb/mow/"
SPECS["hod_x_mow_b3"] = dict(src=_MOW + "con_b3_droid.glb", mode="glb_static", yaw=-90, tris=45000, tex_px=1024, height=8.5, gain=1.4, legs=dict(n=2, top=0.45, swing=14))
SPECS["hod_x_mow_scorpenek"] = dict(src=_MOW + "con_scorpenek_droid.glb", mode="glb_static", yaw=-90, tris=40000, tex_px=1024, height=7.5, legs=dict(n=4, top=0.5, swing=12))
SPECS["hod_x_mow_umbaran_hovertank"] = dict(src=_MOW + "con_umbaran_hovertank.glb", mode="glb_static", yaw=-90, tris=5000, tex_px=1024, length=6.0, hover=True)
SPECS["hod_x_mow_clone_hovertank"] = dict(src=_MOW + "rep_clone_hovertank.glb", mode="glb_static", yaw=-90, tris=5000, tex_px=1024, length=6.5, hover=True)
SPECS["hod_x_mow_at_at_rep"] = dict(src=_MOW + "rep_at_at_rep.glb", mode="glb_static", yaw=-90, tris=7000, tex_px=1024, height=10.5, legs=dict(n=4, top=0.5, swing=12))
# canon pass (user 2026-11-10): RX-200 Falchion replaces the Rebel AAC-1 (px), LAAT/c (RaW, carrying an AT-TE) replaces the
# Rebel RM-09, Sabaoth starfighter replaces the made-up "I-Beam Fighter" (CIS torrent)
SPECS["hod_x_mow_falchion"] = dict(src=_MOW + "rep_falchion_tank.glb", mode="glb_static", yaw=-90, tris=5000, tex_px=1024, length=7.0, hover=True)
# 2026-11-10 Starfleet tab: one static map model per ship (plans & scripts/sw_tree/naval_tree.py wires <TAG>_<ship>_entity)
for _n, _len in {"rev_pelta": 6, "rev_light_frigate": 6, "sev_diamond_cis_refit": 6, "sev_wavecrest": 6, "sev_patrol_frigate": 6,
                 "rev_light_assault_cruiser": 7.5, "rev_lightcruiser": 7.5, "rev_centax_frigate": 7.5, "sev_munificent": 7.5,
                 "sev_recusant": 8, "sev_carrier": 7.5, "rev_victory": 10, "ev_stardestroyer_mki": 11, "sev_providence": 10,
                 "sev_bulwark": 10.5, "rev_venator": 11, "sev_invisible_hand": 11, "sev_lucrehulk": 12, "rev_acclamator1": 9,
                 "sev_hardcell": 7, "sev_supplyship": 9, "rev_dreadnaught": 9, "rev_mandator": 14, "sev_subjugator": 14}.items():
    SPECS["hod_ship_" + _n] = dict(src=RAWS + "/" + _n + ".glb", mode="glb_static", tris=8000, tex_px=1024, length=_len, plane=True)
SPECS["hod_ship_rv_corvette"] = dict(src=FOTR + "/rv_corvette.glb", mode="glb_static", tris=8000, tex_px=1024, length=6, plane=True)
SPECS["hod_ship_nr_quasar"] = dict(src=FOTR + "/nr_quasar.glb", mode="glb_static", tris=8000, tex_px=1024, length=9, plane=True)
SPECS["hod_ship_tr_escort_carrier"] = dict(src=TR + "/imperial_escort_carrier.glb", mode="glb_static", tris=8000, tex_px=1024, length=10, plane=True)   # replaces the Quasar Fire (user: weird Venator sequel)
# 2026-11-11 user picks from the alt_review page (FotR / RaW / Thrawn's Revenge): hod_m_<key>, picker only (sw_tree/alt_new.py)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sw_tree"))
import alt_new  # noqa: E402
SPECS.update(alt_new.specs(WIP))
# 2026-11-10 user: Venator / Victories / Acclamator II / Separatist ships looked poor -> FotR versions (alo_to_glb.py, HOD_TEAM=rep for the Republic red)
for _n, (_src, _len) in {"fotr_consular_lac": (FOTR + "/consular-class_lac.glb", 7.5), "fotr_victory1": (FOTR + "/victory_i-class_star_destroyer.glb", 10),
                         "fotr_victory2": (FOTR + "/victory_ii-class_star_destroyer.glb", 10), "fotr_venator": (FOTR + "/ev_venator.glb", 11),
                         "fotr_acclamator1": (FOTR + "/ev_acclamator_i.glb", 9), "rev_acclamator_assault_ship": (RAWS + "/rev_acclamator_assault_ship.glb", 9.5),
                         "fotr_dreadnaught": (FOTR + "/dreadnaught.glb", 9), "fotr_mandator2": (FOTR + "/rep_mandatorii.glb", 14),
                         "fotr_munificent": (FOTR + "/cis_munificent.glb", 7.5), "fotr_recusant": (FOTR + "/cis_recusant.glb", 8),
                         "fotr_captor": (FOTR + "/cis_captor.glb", 7.5), "fotr_providence": (FOTR + "/cis_providence.glb", 10),
                         "fotr_provdread": (FOTR + "/cis_providence_dreadnought.glb", 10.5), "fotr_lucid_voice": (FOTR + "/providence_lucid_voice.glb", 11),
                         "fotr_lucre_control": (FOTR + "/lucrehulk_control_cship.glb", 12), "fotr_hardcell": (FOTR + "/cis_hardcell.glb", 7),
                         "fotr_lucre_bship": (FOTR + "/lucrehulk_bship.glb", 12), "fotr_subjugator": (FOTR + "/subjugator.glb", 14)}.items():
    SPECS["hod_ship_" + _n] = dict(src=_src, mode="glb_static", tris=8000, tex_px=1024, length=_len, plane=True)
SPECS["hod_x_raw_laatc"] = dict(src=RAWS + "/rev_laat-c_space.glb", mode="glb_static", tris=6000, tex_px=1024, length=5.0, plane=True)
SPECS["hod_x_sabaoth_fighter"] = dict(src=FOTR + "/sabaoth_fighter.glb", mode="glb_static", tris=5000, tex_px=1024, length=3.2, plane=True)
SPECS["hod_x_droch"] =dict(src=FOTR + "/droch-class_boarding_ship.glb", mode="glb_static", tris=5000, tex_px=1024, length=4.5, plane=True)   # 2026-11-09: real Droch (was the TF MAF stand-in)
# A-DSD advanced dwarf spider (no model anywhere, 2026-11-09): the RaW dwarf spider, bigger, repainted gunmetal blue
SPECS["hod_x_adsd"] = dict(SPECS["hod_x_raw_dwarf"], height=5.0, tint=(118, 128, 150))
# Droideka Mk I (RaW SeV_droidekka_mk1, user 2026-11-09: Droideka -> Droideka Mk II special techs); walks on walk_00 (move_00 = rolled ball)
SPECS["hod_x_raw_deka"] = dict(src=RAW + "/sev_droidekka_mk1.glb", mode="bake", height=5.0, tris=3000, drop=r"Sphere", norm_action="attackidle_00",
                               keep=r"(?!COL_MAIN|Sphere01|MUZZLEA_0\d_FLASH)[\w\-]+$",
                               gun="MUZZLEA_00", forward="MUZZLEA_00", back="B_BACK", anims=_RAW_A("attackidle_00", "walk_00", "attack_00"))   # idle_00 = curled up
SPECS["hod_x_raw_b1"] = dict(src=RAW + "/sei_battledroid.glb", mode="bake", height=6.2, tris=4000, infantry=True,
                             keep=r"(B_Pelvis|B_Chest|B_Head|B_Backpack|B_Gun|MuzzleA_00|B_(Bicep|FArm|Hand|Thigh|Calf|Foot)_[RL])$",
                             gun="MuzzleA_00", forward="B_Chest", back="B_Backpack", anims=_RAW_A("IDLE_00", "MOVE_00", "ATTACKIDLE_00"))
SPECS["hod_x_repcom_b1"] = dict(src=RAW + "/b1_battledroid_repcom.glb", mode="bake", height=6.2, tris=4000, keep=_DROID, infantry=True,
                                gun="MuzzleA_00", forward="MuzzleA_00", back="Pelvis", anims=_RAW_A("Idle_00", "Move_00", "AttackIdle_00"))
SPECS["hod_x_b3"] = dict(src=RAW + "/cis_b2_sbd_ptl.glb", mode="bake", height=8.5, tris=4000, infantry=True, keep=_DROID,
                         gun="MuzzleA_00", forward="MuzzleA_00", back="Pelvis", anims=_RAW_A("Idle_00", "Move_00", "AttackIdle_00"))
# 2026-11-09 (user): Republic special battalions, RaW 1.2.1 clones (alo_to_glb.py --anim): ARC trooper (Phase I),
# clone commando
_CLONE = r"(B_Pelvis|B_Chest|B_Neck|B_Head|B_helmet|B_Backpack|B_Gun|MuzzleA_00|B_(Clav|Bicep|FArm|Hand|Thigh|Calf|Foot)_[RL])$"
for _n, _f, _h in (("raw_arc", "rei_arc_trooper", 6.0), ("raw_commando", "rei_clonecommando", 6.2)):
    SPECS["hod_x_" + _n] = dict(src=f"{RAW}/{_f}.glb", mode="bake", height=_h, tris=4000, infantry=True, keep=_CLONE,
                               gun="MuzzleA_00", forward="B_Chest", back="B_Backpack", anims=_RAW_A("idle_00", "move_00", "attackidle_00"))
# Imperial successors (user 2026-11-09: real models, no repaints): Battlefront II clone shock trooper (DATA SIDE/rep146th.lvl,
# red Coruscant Guard markings = the first Imperial shock troopers) and the black JKA clone commando (LGD SIDE/rep.lvl,
# imp_inf_JKA_Clone_Commando = Katarn armour in Imperial black). swbf-unmunge -> msh_anim_to_glb.py with the BF2
# human_rifle idle / walk / shoot clips, skel=basepose.msh, attach=hp_weapons:rep_weap_inf_rifle.msh (BF2 soldiers carry no
# gun of their own). Oriented on the aiming pose: at rest (T-pose) the gun hand is out to the side. tris high: low-poly
# sources, decimating them faceted the armour.
for _n, _f in (("imp_shock", "rep_inf_shocktrooper"), ("imp_commando", "imp_inf_jka_clone_commando")):
    SPECS["hod_x_" + _n] = dict(src=f"{BF2A}/{_f}.glb", mode="bake", height=6.0, tris=12000, infantry=True, norm_action="shoot",
                               keep=r"(?!DummyRoot)\w+$", gun="hp_weapons", forward="hp_weapons", back="bone_ribcage",
                               anims={"idle": ("idle", 0, None), "move": ("walk", 0, None), "attack": ("shoot", 0, None)})
SPECS["hod_x_imp_commando"]["gain"] = 1.6   # black armour: atlas colours < ~100 RGB render black in game
SPECS["hod_x_espo"] =dict(src=RAW + "/csa_espo_walker.glb", mode="bake", height=5.5, tris=3000,
                           keep=r"(Dummy01|Bone0[1-8]|Turret_00|gun_[rl]|MuzzleA_0[0-2])$",
                           gun="MuzzleA_00", forward="Turret_00", back="Dummy01", anims=_RAW_A("IDLE_00", "Move_00"))
# Vulture droid in walking mode (FotR CIS_Vulture_Ground): light walker level 3, in place of the advanced dwarf spider (user 2026-11-08)
SPECS["hod_x_vulture_walk"] = dict(src=RAW + "/cis_vulture_ground.glb", mode="bake", height=4.5, tris=3000,
                                   keep=r"(Vulture|Leg_[LR]_0[01]|Head|Muzzle_[AB])$",
                                   gun="Muzzle_A", forward="Muzzle_A", back="Vulture", anims=_RAW_A("IDLE_00", "MOVE_00", "ATTACKIDLE_00"))
SPECS["hod_atap"] = dict(src=WIP + "/3d/at-ap/source/at-ap.glb", mode="glb_static", tris=8000, tex_px=1024, height=11.0,
                         legs=dict(n=2, top=0.5, swing=10))   # procedural rig: the two ground legs (front leg folded)
SPECS["hod_juggernaut"] =dict(src=WIP + "/3d/clone-turbo-tank-havw-a6-juggernaut/source/clone turbo tank.glb", mode="glb_static", tris=6000, tex_px=1024, length=7.0, yaw=180)
MSH_BONES = ["bone_root", "bone_head"] + [f"bone_{s}_{p}" for s in "lr" for p in ("thigh", "calf", "foot", "ball", "toe")]


# ─────────────────────────────── Blender side ───────────────────────────────
def convert(*only):
    import bpy  # type: ignore
    from mathutils import Euler, Matrix, Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    os.makedirs(OUT, exist_ok=True)
    side = json.load(open(SIDE)) if os.path.exists(SIDE) else {}

    class Mat:
        def __init__(self, stem):
            self.shader = ["PdxMeshAdvanced"]
            self.diff, self.n, self.spec = [f"{stem}_diffuse.dds"], [f"{stem}_normal.dds"], [f"{stem}_spec.dds"]

    def select(objs, active=None):
        bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
        for o in bpy.context.scene.objects:
            o.select_set(o in objs)
        bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)

    def world_box(meshes):
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for o in meshes:
            ev = o.evaluated_get(dg)
            pts += [ev.matrix_world @ v.co for v in ev.data.vertices]
        return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]

    def texture_sources(mat):
        """baseColor / metallicRoughness image paths of a glTF material"""
        out = {}
        if not mat or not mat.use_nodes:
            return out
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                for link in node.outputs["Color"].links:
                    sock = link.to_socket.name
                    kind = "base" if sock == "Base Color" else "mr" if link.to_node.type == "SEPARATE_COLOR" else None
                    if kind:
                        out[kind] = bpy.path.abspath(node.image.filepath)
        return out

    def finish(name, meshes, rig, locs, anims):
        """materials, decimation, export"""
        s = SPECS[name]
        select(meshes, meshes[0])
        if len(meshes) > 1:
            bpy.ops.object.join()
        mesh = bpy.context.view_layer.objects.active
        mesh.data.update()                  # direct vertex edits leave the evaluated (cached) mesh stale
        bpy.context.view_layer.update()
        tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
        if tris > s["tris"]:
            dec = mesh.modifiers.new("dec", "DECIMATE")
            dec.ratio = s["tris"] / tris
            if s.get("protect"):                  # thin parts (gun barrels) collapse under decimation: leave them whole
                prot = mesh.vertex_groups.new(name="_protect")
                ids = {g.index for g in mesh.vertex_groups if re.search(s["protect"], g.name)}
                prot.add([v.index for v in mesh.data.vertices if any(g.group in ids and g.weight > 0.3 for g in v.groups)], 1.0, "REPLACE")
                dec.vertex_group, dec.invert_vertex_group = "_protect", True
            for m in list(mesh.modifiers):        # the armature modifier must come after the decimation
                if m.type == "ARMATURE":
                    mesh.modifiers.remove(m)
            bpy.ops.object.modifier_apply(modifier="dec")
            arm_mod = mesh.modifiers.new("rig", "ARMATURE")
            arm_mod.object = rig
        if mesh.vertex_groups.get("_protect"):
            mesh.vertex_groups.remove(mesh.vertex_groups["_protect"])
        bpy.ops.object.vertex_group_limit_total(limit=3)   # vanilla rigs: 3 influences
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        bpy.ops.object.material_slot_remove_unused()   # decimation can empty a small material: an empty sub-mesh breaks the .mesh
        me = mesh.data   # the game indexes a sub-mesh with 16 bits: past 65535 vertices the rest is not drawn -> split big ones
        for i in range(len(me.materials)):
            new, count = None, 0
            for p in [p for p in me.polygons if p.material_index == i]:
                count += p.loop_total
                if count > 60000:
                    me.materials.append(me.materials[i])
                    new, count = len(me.materials) - 1, p.loop_total
                if new is not None:
                    p.material_index = new
        side[name] = []
        for i, slot in enumerate(mesh.material_slots):
            stem = f"{name}_{i}" if len(mesh.material_slots) > 1 else name
            side[name].append(dict(stem=stem, **texture_sources(slot.material)))
            pm = bie.create_shader(Mat(stem), stem, os.path.abspath(OUT))
            pm[PDX_SHADER] = "PdxMeshAdvanced"
            slot.material = pm
        mesh.name = mesh.data.name = name
        for o in [o for o in bpy.context.scene.objects if o not in (mesh, rig) and o not in locs]:
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.context.scene.frame_set(0)
        bie.export_meshfile(os.path.abspath(f"{OUT}/{name}.mesh"), exp_mesh=True, exp_skel=True, exp_locs=True)
        select([rig], rig)
        for game_anim, (action, f0, f1) in anims.items():
            f1 = max(f1, f0 + 1)   # a static pose still needs 2 samples ("Animation has only one sample", error.log)
            rig.animation_data.action = bpy.data.actions[action]
            bpy.context.scene.frame_start, bpy.context.scene.frame_end = f0, f1
            bie.export_animfile(os.path.abspath(f"{OUT}/{name}_{game_anim}.anim"), frame_start=f0, frame_end=f1)
        lo, hi = world_box([mesh])
        print(f"{name}: {tris} -> {len(mesh.data.polygons)} faces, {len(rig.data.bones)} bones, "
              f"size {hi[0]-lo[0]:.2f} x {hi[1]-lo[1]:.2f} x {hi[2]-lo[2]:.2f}")

    def add_locator(name, rig, bone, pos):
        e = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(e)
        e.parent, e.parent_type, e.parent_bone = rig, "BONE", bone
        # blaster bolts (hosw_*_blastershot) fly along the locator's X: the barrel's X points forward (-Y), as the E-11 muzzle
        e.matrix_world = Matrix.Translation(pos) @ (Matrix.Rotation(-math.pi / 2, 4, "Z") if name == "barrel" else Matrix())
        return e

    def normaliser(meshes, fwd_from, fwd_to, length=None, height=None):
        """an empty above every top-level object: yaw so fwd_from->fwd_to points to -Y, scale, centre, ground"""
        norm = bpy.data.objects.new("norm", None)
        bpy.context.scene.collection.objects.link(norm)
        for o in [o for o in bpy.context.scene.objects if o.parent is None and o is not norm]:
            mw = o.matrix_world.copy()
            o.parent = norm
            o.matrix_world = mw
        d = fwd_to - fwd_from
        yaw = math.atan2(d.x, -d.y)                  # angle that turns d onto -Y
        norm.matrix_world = Matrix.Rotation(yaw, 4, "Z")
        bpy.context.view_layer.update()
        lo, hi = world_box(meshes)
        k = length / max(hi[0] - lo[0], hi[1] - lo[1]) if length else height / (hi[2] - lo[2])
        c = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]))
        norm.matrix_world = Matrix.Scale(k, 4) @ Matrix.Translation(-c) @ norm.matrix_world
        bpy.context.view_layer.update()
        return norm

    def msh_walker(name, s):
        """Battlefront II walker: parts in bind pose, each bound to one skeleton bone; rebuilt rig + walk cycle"""
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import swbf_msh
        from mathutils import Quaternion  # type: ignore
        d = swbf_msh.read(s["src"])
        by = {m["name"]: m for m in d["models"]}
        by_index = {m["index"]: m["name"] for m in d["models"]}
        # the .msh (Softimage XSI export) is right-handed, Y up, +Z ahead; the game wants Z up, -Y ahead
        C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
        W = {}
        def world(n):
            if n not in W:
                t = by[n]["tran"]
                x, y, z, w = t["rot"]
                loc = Matrix.Translation(t["pos"]) @ Quaternion((w, x, y, z)).to_matrix().to_4x4()
                W[n] = (world(by[n]["parent"]) if by[n]["parent"] in by else Matrix()) @ loc
            return W[n]
        def kept(bone):          # a part bound to a bone the game rig drops goes to its nearest kept ancestor
            while bone not in MSH_BONES:
                bone = by[bone]["parent"]
            return bone
        verts, faces, groups = [], [], {}
        for m in d["models"]:
            if m["type"] != 1 or m["hidden"] or not m["envelope"] or m["name"].startswith("polymsh"):
                continue
            bone = kept(by_index[m["envelope"][0]])
            for g in m["segments"]:
                base = len(verts)
                pts = [C @ Vector(p) for p in g["pos"]]
                nrm = [C @ Vector(n) for n in g["nrm"]] if g["nrm"] else None
                verts += pts
                for a, b, c in g["tris"]:
                    f = (base + a, base + b, base + c)
                    if nrm:     # strips and the mirror leave winding mixed: face the way the source normals point
                        if (pts[b] - pts[a]).cross(pts[c] - pts[a]).dot(nrm[a] + nrm[b] + nrm[c]) < 0:
                            f = (f[0], f[2], f[1])
                    faces.append(f)
                groups.setdefault(bone, []).extend(range(base, len(verts)))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        uvs = [uv for m in d["models"] if m["type"] == 1 and not m["hidden"] and m["envelope"] and not m["name"].startswith("polymsh")
               for g in m["segments"] for uv in (g["uv"] or [(0, 0)] * len(g["pos"]))]
        uv = mesh.uv_layers.new(name="uv0")
        uv.data.foreach_set("uv", [c for p in mesh.polygons for li in p.loop_indices
                                   for c in uvs[mesh.loops[li].vertex_index]])   # the .msh V is already bottom-up (tiles wrap)
        o = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(o)
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.abspath(s["texture"]))
        mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        mesh.materials.append(mat)
        for bone, ids in groups.items():
            o.vertex_groups.new(name=bone).add(ids, 1.0, "REPLACE")
        # scale to the game height, centred, feet on the ground
        lo = Vector([min(v[i] for v in verts) for i in range(3)])
        hi = Vector([max(v[i] for v in verts) for i in range(3)])
        k = s["height"] / (hi.z - lo.z)
        N = Matrix.Scale(k, 4) @ Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)))
        mesh.transform(N)
        head = {b: N @ (C @ world(b).translation) for b in MSH_BONES}
        tip = N @ (C @ world("eff_l_toe").translation)
        rig_data = bpy.data.armatures.new("rig")
        rig = bpy.data.objects.new("rig", rig_data)
        bpy.context.scene.collection.objects.link(rig)
        select([rig], rig)
        bpy.ops.object.mode_set(mode="EDIT")
        child = {"bone_root": None, "bone_head": None}
        for sd in "lr":
            chain = [f"bone_{sd}_{p}" for p in ("thigh", "calf", "foot", "ball", "toe")]
            for a, b in zip(chain, chain[1:]):
                child[a] = b
            child[chain[-1]] = None
        for b in MSH_BONES:
            eb = rig_data.edit_bones.new(b)
            eb.head = head[b]
            eb.tail = head[child[b]] if child[b] else head[b] + Vector((0, 0, 0.1 * s["height"]))
            if b.endswith("_toe"):
                eb.tail = N @ (C @ world(f"eff_{b[5]}_toe").translation)
        for b in MSH_BONES[1:]:
            par = by[b]["parent"]
            while par not in MSH_BONES:
                par = by[par]["parent"]
            rig_data.edit_bones[b].parent = rig_data.edit_bones[par]
        bpy.ops.object.mode_set(mode="OBJECT")
        o.modifiers.new("rig", "ARMATURE").object = rig
        # walk: 48-frame loop, legs half a cycle apart. Each leg swings about the hip; the swinging leg folds at the
        # ankle to clear the ground; toes stay level; the body drops so the planted foot stays on the ground
        select([rig], rig)
        bpy.ops.object.mode_set(mode="POSE")
        rig.animation_data_create()
        rig.animation_data.action = bpy.data.actions.new("walk")
        rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
        rot_at = lambda p, ang: Matrix.Translation(p) @ Matrix.Rotation(ang, 4, "X") @ Matrix.Translation(-p)
        swing, fold = math.radians(16), math.radians(22)
        for f in range(49):
            ph = 2 * math.pi * f / 48
            drop = Matrix.Translation((0, 0, -(1 - math.cos(swing)) * (head["bone_l_thigh"].z - tip.z) * abs(math.sin(ph))))
            rig.pose.bones["bone_root"].matrix = drop @ rest["bone_root"]
            rig.pose.bones["bone_head"].matrix = drop @ rest["bone_head"]
            for sd, off in (("l", 0.0), ("r", math.pi)):
                a = -swing * math.sin(ph + off)                              # forward = toward -Y
                b = fold * max(0.0, math.cos(ph + off))                      # fold while the leg swings forward
                hip, ankle, ball = (head[f"bone_{sd}_{p}"] for p in ("thigh", "foot", "ball"))
                m_leg = drop @ rot_at(hip, a)
                m_shin = m_leg @ rot_at(ankle, -b)
                ball_n = m_shin @ ball
                m_toe = Matrix.Translation(ball_n - ball)                    # toes level: no rotation
                for bn, m in ((f"bone_{sd}_thigh", m_leg), (f"bone_{sd}_calf", m_leg), (f"bone_{sd}_foot", m_shin),
                              (f"bone_{sd}_ball", m_toe), (f"bone_{sd}_toe", m_toe)):
                    rig.pose.bones[bn].matrix = m @ rest[bn]
                    bpy.context.view_layer.update()
            for pb in rig.pose.bones:
                pb.keyframe_insert("location", frame=f)
                pb.keyframe_insert("rotation_quaternion", frame=f)
        bpy.ops.object.mode_set(mode="OBJECT")
        barrel = N @ (C @ world("hp_cannon_1").translation)
        locs = [add_locator("barrel", rig, "bone_head", barrel),
                add_locator("smoke", rig, "bone_root", head["bone_root"] + Vector((0, 0.3 * s["height"], 0)))]
        finish(name, [o], rig, locs, {"idle": ("walk", 0, 48), "move": ("walk", 0, 48), "attack": ("walk", 0, 48)})

    def add_rider(name, r, at):
        """seated trooper (make_rider.py glb, pelvis at origin) at <at> + r["offset"], scaled; returns his mesh objects"""
        before, images_before = set(bpy.context.scene.objects), set(bpy.data.images)
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(r["src"]))
        parts = [x for x in bpy.context.scene.objects if x not in before and x.type == "MESH"]
        tex_dir = os.path.abspath(os.path.join(os.path.dirname(r["src"]), "tex"))
        os.makedirs(tex_dir, exist_ok=True)
        for im in set(bpy.data.images) - images_before:   # packed glb images: the texture step needs files
            if (im.packed_file or not im.filepath) and im.size[0]:
                im.filepath_raw, im.file_format = os.path.join(tex_dir, f"{name}_rider_{bpy.path.clean_name(im.name)}.png"), "PNG"
                im.save()
                im.filepath = im.filepath_raw
        rtris = sum(len(p.vertices) - 2 for x in parts for p in x.data.polygons)
        for x in parts:                             # his own budget, or the vehicle's decimation eats him
            dec = x.modifiers.new("dec", "DECIMATE")
            dec.ratio = min(1.0, r.get("tris", 2500) / rtris)
            select([x], x)
            bpy.ops.object.modifier_apply(modifier="dec")
        place = Matrix.Translation(Vector(at) + Vector(r["offset"])) @ Matrix.Scale(r["scale"], 4)
        for x in parts:
            x.parent = None
            x.data.transform(place @ x.matrix_world)
            x.matrix_world = Matrix()
        for x in [x for x in bpy.context.scene.objects if x not in before and x not in parts]:
            bpy.data.objects.remove(x, do_unlink=True)    # glTF scene empties
        return parts

    def rebake(name, meshes, s):
        """decimated copy with new smart-UVs, base colour baked from the full mesh (Cycles, selected to active)"""
        select(meshes, meshes[0])
        bpy.ops.object.duplicate()
        low = bpy.context.selected_objects
        bpy.context.view_layer.objects.active = low[0]
        if len(low) > 1:
            bpy.ops.object.join()
        low = bpy.context.view_layer.objects.active
        import bmesh  # type: ignore
        bm = bmesh.new(); bm.from_mesh(low.data)   # weld the copy only (welding breaks UVs, but they are re-made below)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=s.get("merge", 0.004))
        bm.to_mesh(low.data); bm.free()
        tris = sum(len(p.vertices) - 2 for p in low.data.polygons)
        dec = low.modifiers.new("dec", "DECIMATE")
        dec.ratio = s["tris"] / tris
        dec.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier="dec")
        while low.data.uv_layers:
            low.data.uv_layers.remove(low.data.uv_layers[0])
        low.data.uv_layers.new(name="UVMap")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003)
        bpy.ops.object.mode_set(mode="OBJECT")
        px = s.get("tex_px", 1024) * 2
        img = bpy.data.images.new(f"{name}_baked", px, px)
        tex_dir = os.path.abspath(os.path.join(os.path.dirname(s["src"]), "tex"))
        img.filepath_raw, img.file_format = os.path.join(tex_dir, f"{name}_baked.png"), "PNG"
        mat = bpy.data.materials.new(f"{name}_baked")
        mat.use_nodes = True
        nt = mat.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.links.new(node.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        nt.nodes.active = node
        low.data.materials.clear()
        low.data.materials.append(mat)
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"
        sc.cycles.samples = 4
        sc.render.bake.use_pass_direct = sc.render.bake.use_pass_indirect = False
        sc.render.bake.use_selected_to_active = True
        sc.render.bake.cage_extrusion = 0.12     # the decimated shell drifts off the detailed surface
        sc.render.bake.max_ray_distance = 0.3
        sc.render.bake.margin = 16
        for o in bpy.context.scene.objects:
            o.select_set(o in meshes or o is low)
        bpy.context.view_layer.objects.active = low
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})
        img.save()
        for o in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
        return low

    def hover_sway(pb, height, f0, f1, hover=True):
        """hover craft float: bob + pitch / roll sway; ground vehicles rock on their suspension. Loops over f0..f1
        (whole cycles of ~48 frames). Bone space of an upright bone: Y = up, X = pitch axis, Z = the long (roll) axis"""
        bob = (0.08 if hover else 0.015) * height
        pitch, roll = (math.radians(3.0), math.radians(4.0)) if hover else (math.radians(0.8), math.radians(0.6))
        n = max(1, round((f1 - f0) / 48))
        pb.rotation_mode = "QUATERNION"
        for f in range(f0, f1 + 1):
            t = 2 * math.pi * n * (f - f0) / max(f1 - f0, 1)
            pb.location = (0, bob * (1 + math.sin(t)) if hover else bob * 0.5 * (1 + math.sin(2 * t)), 0)
            pb.rotation_quaternion = Euler((pitch * math.sin(t + 1.0), 0, roll * math.sin(t))).to_quaternion()
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("rotation_quaternion", frame=f)

    def find_legs(meshes, L, lo, hi):
        """procedural legs for unrigged walkers (scans / triangle soup included): feet = clusters of the lowest vertices,
        each leg traced upward band by band (legs may slant) up to the hip height L["top"] (fraction of the height)"""
        H = hi[2] - lo[2]
        top = L.get("top", 0.45) * H
        pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
        pts = pts[::max(1, len(pts) // 60000)]
        low = [Vector((p.x, p.y)) for p in pts if p.z < lo[2] + 0.06 * H]
        n = L["n"]
        cs = [low[0]]
        while len(cs) < n:                       # farthest-point seeds, then Lloyd iterations
            cs.append(max(low[::max(1, len(low) // 3000)], key=lambda q: min((q - c).length for c in cs)))
        for _ in range(15):
            grp = [[] for _ in cs]
            for q in low:
                grp[min(range(n), key=lambda i: (q - cs[i]).length)].append(q)
            cs = [sum(g, Vector((0, 0))) / len(g) if g else cs[i] for i, g in enumerate(grp)]
        spacing = min((cs[i] - cs[j]).length for i in range(n) for j in range(i + 1, n)) if n > 1 else H
        rad = L.get("radius", 99) * spacing     # default: every vertex below the hips belongs to its nearest leg
        bands = 12
        legs = []
        for c in cs:
            line, cur = [], c.copy()
            for k in range(bands):
                z0, z1 = lo[2] + top * k / bands, lo[2] + top * (k + 1) / bands
                near = [Vector((p.x, p.y)) for p in pts if z0 <= p.z < z1 and (Vector((p.x, p.y)) - cur).length < rad]
                if near:
                    cur = sum(near, Vector((0, 0))) / len(near)
                line.append(((z0 + z1) / 2, cur.copy()))
            legs.append(dict(line=line, rad=rad, top=lo[2] + top, foot=Vector((c.x, c.y, lo[2])),
                             hip=Vector((line[-1][1].x, line[-1][1].y, lo[2] + top))))
        print("LEGS", [(round(l["foot"].x, 2), round(l["foot"].y, 2)) for l in legs])
        return legs

    def skin_legs(meshes, legs):
        """vertices near a leg's traced centre line go to that leg, fading into the body over the top quarter"""
        for o in meshes:
            gs = [o.vertex_groups.new(name=f"leg_{i}") for i in range(len(legs))]
            root = o.vertex_groups["root"]
            for v in o.data.vertices:
                p = o.matrix_world @ v.co
                best = None
                for i, lg in enumerate(legs):
                    if p.z > lg["top"]:
                        continue
                    z, c = min(lg["line"], key=lambda zc: abs(zc[0] - p.z))
                    d = (Vector((p.x, p.y)) - c).length
                    if d < lg["rad"] and (best is None or d < best[1]):
                        best = (i, d)
                if best:
                    lg = legs[best[0]]
                    w = min(1.0, max(0.0, (lg["top"] - p.z) / (0.25 * (lg["top"] - lg["foot"].z))))
                    gs[best[0]].add([v.index], w, "REPLACE")
                    root.add([v.index], 1.0 - w, "REPLACE")

    def walk_legs(rig, legs, L, height):
        """48-frame gait: legs swing fore / aft about the hip (feet forward = -Y while lifted), neighbours in
        opposite phase (pairs / tripods); the body bobs a little"""
        amp, lift = math.radians(L.get("swing", 14)), L.get("lift", 0.05) * height
        order = sorted(range(len(legs)), key=lambda i: legs[i]["foot"].y)
        phase = {}
        for rank, i in enumerate(order):
            side = 1 if legs[i]["foot"].x > 0 else 0
            phase[i] = math.pi * ((rank // 2 + side) % 2) if len(legs) > 3 else math.pi * side
        if len(legs) == 3:                      # AT-AP style: two main legs alternate, the third between them
            mid = min(range(3), key=lambda i: abs(legs[i]["foot"].x))
            phase[mid] = math.pi / 2
        root = rig.pose.bones["root"]
        root.rotation_mode = "QUATERNION"
        for f in range(49):
            t = 2 * math.pi * f / 48
            root.location = (0, 0.012 * height * (1 + math.sin(2 * t)), 0)     # bone space: Y = up
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_quaternion", frame=f)
            for i, lg in enumerate(legs):
                pb = rig.pose.bones[f"leg_{i}"]
                pb.rotation_mode = "QUATERNION"
                tt = t + phase[i]
                Rl = rig.data.bones[pb.name].matrix_local
                d = (Matrix.Translation((0, 0, lift * max(0.0, math.cos(tt)))) @ Matrix.Translation(lg["hip"])
                     @ Matrix.Rotation(-amp * math.sin(tt), 4, "X") @ Matrix.Translation(-lg["hip"]))
                pb.matrix_basis = Rl.inverted() @ d @ Rl
                pb.keyframe_insert("location", frame=f)
                pb.keyframe_insert("rotation_quaternion", frame=f)

    def close_loop(act, f0, f1):
        """HOI4 replays a loop from its first frame: spread any end / start mismatch (feet a stride off, a turret a few
        degrees round) over the clip so the last frame meets the first. Big jumps (quaternion sign flips) are left."""
        for fc in act.fcurves:
            kp = [k for k in fc.keyframe_points if f0 <= k.co[0] <= f1]
            if len(kp) < 3:
                continue
            d = fc.evaluate(f0) - fc.evaluate(f1)
            if 1e-5 < abs(d) < (0.5 if "rotation" in fc.data_path else 3.0):
                for k in kp:
                    t = (k.co[0] - f0) / (f1 - f0)
                    k.co[1] += d * t
                    k.handle_left[1] += d * t
                    k.handle_right[1] += d * t
            fc.update()

    def glb_static(name, s):
        """static model (Battlefront II glb): one root bone, nose -Y, ground at z 0; hover craft bob up and down"""
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(s["src"]))
        tex_dir = os.path.abspath(os.path.join(os.path.dirname(s["src"]), "tex"))   # .glb textures are packed: the
        os.makedirs(tex_dir, exist_ok=True)                                        # texture step needs files
        for im in bpy.data.images:
            if im.packed_file or not im.filepath:
                if im.size[0] == 0:
                    continue
                path = os.path.join(tex_dir, f"{name}_{bpy.path.clean_name(im.name)}.png")
                im.filepath_raw, im.file_format = path, "PNG"
                im.save()
                im.filepath = path
        for o in [o for o in bpy.context.scene.objects if s.get("drop") and re.match(s["drop"], o.name)]:
            bpy.data.objects.remove(o, do_unlink=True)    # stray placeholder objects in some downloads
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        yaw = math.radians(s.get("yaw", 0))
        normaliser(meshes, Vector((0, 0, 0)), Vector((math.sin(yaw), -math.cos(yaw), 0)), length=s.get("length"), height=s.get("height"))
        select(meshes, meshes[0])
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        if s.get("merge"):     # scanned / die-cast models are loose triangles: weld them or decimation shreds the mesh
            import bmesh  # type: ignore
            for o in meshes:
                bm = bmesh.new(); bm.from_mesh(o.data)
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=s["merge"])
                bm.to_mesh(o.data); bm.free()
        if s.get("rebake"):    # fragmented scan UVs turn to noise when decimated: bake the colours onto a fresh low mesh
            meshes = [rebake(name, meshes, s)]
        if s.get("rider"):     # offset from the ground centre of the normalised model
            meshes += add_rider(name, s["rider"], (0, 0, 0))
        lo, hi = world_box(meshes)
        rig = bpy.data.objects.new("rig", bpy.data.armatures.new("rig"))
        bpy.context.scene.collection.objects.link(rig)
        select([rig], rig)
        bpy.ops.object.mode_set(mode="EDIT")
        b = rig.data.edit_bones.new("root")
        b.head, b.tail = (0, 0, 0), (0, 0, max(hi[2] - lo[2], 0.5) * 0.5)
        legs = find_legs(meshes, s["legs"], lo, hi) if s.get("legs") else []
        for i, lg in enumerate(legs):
            e = rig.data.edit_bones.new(f"leg_{i}")
            e.head, e.tail, e.parent = lg["hip"], lg["foot"], b
        # turrets: each entry = object-name regex (the part's own meshes) or a float (every vertex above that fraction
        # of the height, for one-piece models); each gets a bone at the foot of its centre that yaws and recoils
        H = hi[2] - lo[2]
        tur = []
        for sel in s.get("turrets", []):
            vs = [(o, v.index, o.matrix_world @ v.co) for o in meshes for v in o.data.vertices
                  if (re.search(sel, o.name) if isinstance(sel, str) else (o.matrix_world @ v.co).z > lo[2] + sel * H)]
            assert vs, (name, sel)
            c = sum((p for _, _, p in vs), Vector()) / len(vs)
            piv = Vector((c.x, c.y, min(p.z for _, _, p in vs)))
            e = rig.data.edit_bones.new(f"turret_{len(tur)}")
            e.head, e.tail, e.parent = piv, piv + Vector((0, 0, 0.3 * H)), b
            tur.append(dict(vs=vs, piv=piv, muzzle=min((p for _, _, p in vs), key=lambda p: p.y)))
        assert not (legs and tur), name
        bpy.ops.object.mode_set(mode="OBJECT")
        for o in meshes:
            o.vertex_groups.new(name="root").add(range(len(o.data.vertices)), 1.0, "REPLACE")
            o.modifiers.new("rig", "ARMATURE").object = rig
        for i, t in enumerate(tur):
            for o, vi, _ in t["vs"]:
                o.vertex_groups["root"].remove([vi])
                (o.vertex_groups.get(f"turret_{i}") or o.vertex_groups.new(name=f"turret_{i}")).add([vi], 1.0, "REPLACE")
        if legs:
            skin_legs(meshes, legs)
        rig.animation_data_create()
        act = rig.animation_data.action = bpy.data.actions.new("main")
        pb = rig.pose.bones["root"]
        if legs:
            walk_legs(rig, legs, s["legs"], hi[2] - lo[2])
            rig.animation_data.action = bpy.data.actions.new("idle")       # standing: body sways, feet planted
            hover_sway(pb, hi[2] - lo[2], 0, 48, hover=False)
            for i in range(len(legs)):
                lb = rig.pose.bones[f"leg_{i}"]
                lb.rotation_mode = "QUATERNION"
                lb.matrix_basis = Matrix()
                for f in (0, 48):
                    lb.keyframe_insert("location", frame=f)
                    lb.keyframe_insert("rotation_quaternion", frame=f)
        else:
            hover_sway(pb, hi[2] - lo[2], 0, 48, hover=bool(s.get("hover")))
        if tur:
            def pose_turret(i, f, yaw, kick):   # yaw about the bone's foot, kick = recoil back along +Y (nose is -Y)
                tb = rig.pose.bones[f"turret_{i}"]
                tb.rotation_mode = "QUATERNION"
                Rl, p = rig.data.bones[tb.name].matrix_local, tur[i]["piv"]
                tb.matrix_basis = Rl.inverted() @ (Matrix.Translation(p + Vector((0, kick, 0))) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Translation(-p)) @ Rl
                tb.keyframe_insert("location", frame=f)
                tb.keyframe_insert("rotation_quaternion", frame=f)
            for i in range(len(tur)):            # move: turrets locked forward
                for f in (0, 48):
                    pose_turret(i, f, 0, 0)
            rig.animation_data.action = bpy.data.actions.new("idle")      # idle: slow scan, turrets out of step
            hover_sway(pb, H, 0, 96, hover=bool(s.get("hover")))
            for i in range(len(tur)):
                for f in range(0, 97, 4):
                    pose_turret(i, f, math.radians(s.get("scan", 20)) * math.sin(2 * math.pi * f / 96 + i * 2.1), 0)
            rig.animation_data.action = bpy.data.actions.new("attack")    # attack: aim ahead, two shots with recoil
            hover_sway(pb, H, 0, 48, hover=bool(s.get("hover")))
            back = 0.06 * (hi[1] - lo[1])
            for i in range(len(tur)):
                for f in range(49):
                    k = (f + 6 * i) % 24                                   # several turrets fire in turn
                    pose_turret(i, f, 0, back * (k / 2 if k < 2 else max(0.0, 1 - (k - 2) / 12)))
        locs = [add_locator("barrel", rig, "turret_0" if tur else "root", tur[0]["muzzle"] if tur else Vector((0, lo[1], (lo[2] + hi[2]) / 2))),
                add_locator("smoke", rig, "root", Vector((0, hi[1], (lo[2] + hi[2]) / 2)))]
        stand = "idle" if legs else "main"
        if tur:
            finish(name, meshes, rig, locs, {"idle": ("idle", 0, 96), "move": ("main", 0, 48), "attack": ("attack", 0, 48)})
            return
        finish(name, meshes, rig, locs, {"idle": (stand, 0, 48), "move": ("main", 0, 48), "attack": (stand, 0, 48)})

    for name, s in SPECS.items():
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if s["mode"] == "msh_walker":
            bpy.context.scene.render.fps = 24
            msh_walker(name, s)
            continue
        if s["mode"] == "glb_static":
            bpy.context.scene.render.fps = 24
            glb_static(name, s)
            continue
        src = s["src"] if s["src"].endswith(".glb") else f"{SRC}/{s['src']}/scene.gltf"   # .glb: alo_to_glb.py --anim output
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(src))
        if src.endswith(".glb"):          # packed textures -> files for the texture step (as glb_static does)
            tex_dir = os.path.abspath(os.path.join(os.path.dirname(src), "tex"))
            os.makedirs(tex_dir, exist_ok=True)
            for im in bpy.data.images:
                if im.size[0] and (im.packed_file or not im.filepath):
                    path = os.path.join(tex_dir, f"{name}_{bpy.path.clean_name(im.name)}.png")
                    im.filepath_raw, im.file_format = path, "PNG"
                    im.save()
                    im.filepath = path
        for o in [o for o in bpy.context.scene.objects if o.name.startswith("Icosphere") or (s.get("drop") and re.match(s["drop"], o.name))]:
            bpy.data.objects.remove(o, do_unlink=True)
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        arm = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"][0]
        bpy.context.scene.render.fps = 24

        if s["mode"] == "bake":
            def act_name(n):      # glTF import appends the rig name to every action: match by prefix
                return n if not n or n in bpy.data.actions else next(a.name for a in bpy.data.actions if a.name.startswith(n))
            s = dict(s, anims={g: (act_name(a), f0, f1 if f1 is not None else int(bpy.data.actions[act_name(a)].frame_range[1]))
                                for g, (a, f0, f1) in s["anims"].items()})
            if s.get("norm_action"):
                s["norm_action"] = act_name(s["norm_action"])
            # 1. pose the source at its first frame, normalise around it
            first = bpy.data.actions[s.get("norm_action") or s["anims"]["move"][0]] if (s.get("norm_action") or s["anims"]["move"][0]) else None
            if first:
                arm.animation_data.action = first
            bpy.context.scene.frame_set(0)
            pw = lambda b: arm.matrix_world @ arm.pose.bones[b].head
            normaliser(meshes, pw(s.get("back") or s["gun"]), pw(s["forward"]), length=s.get("length"), height=s.get("height"))
            # 2. game rig: kept bones at the source's rest positions (world), parented to the nearest kept ancestor
            keep = [b.name for b in arm.data.bones if re.match(s["keep"], b.name) and not b.name.endswith(("_end_05", "_end_06", "_end_07"))]
            def kept_ancestor(bone):
                p = bone.parent
                while p and p.name not in keep:
                    p = p.parent
                return p.name if p else None
            rest = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local) for b in arm.data.bones}
            rig_data = bpy.data.armatures.new("rig")
            rig = bpy.data.objects.new("rig", rig_data)
            bpy.context.scene.collection.objects.link(rig)
            select([rig], rig)
            bpy.ops.object.mode_set(mode="EDIT")
            for n in keep:
                eb = rig_data.edit_bones.new(n)
                h, t = rest[n]
                eb.head, eb.tail = h, t if (t - h).length > 1e-4 else h + Vector((0, 0, 0.05))
                # same rest orientation (roll) as the source bone, or copied world rotations deform the skin wrongly
                eb.align_roll((arm.matrix_world.to_3x3() @ arm.data.bones[n].matrix_local.to_3x3()) @ Vector((0, 0, 1)))
            # one still bone named "Root" at the origin above everything: the Clausewitz skeleton convention (modding guide)
            top = rig_data.edit_bones.new("Root")
            top.head, top.tail = Vector((0, 0, 0)), Vector((0, 0, 0.05))
            if s.get("hover"):      # repulsorcraft float on a "hover" bone under Root (swayed after the bake)
                hv = rig_data.edit_bones.new("hover")
                hv.head, hv.tail, hv.parent = Vector((0, 0, 0)), Vector((0, 0, 0.05)), top
                top = hv
            for n in keep:
                pa = kept_ancestor(arm.data.bones[n])
                rig_data.edit_bones[n].parent = rig_data.edit_bones[pa] if pa else top
            bpy.ops.object.mode_set(mode="POSE")
            for n in keep:                            # location + rotation only: the source carries the normaliser scale
                for kind in ("COPY_LOCATION", "COPY_ROTATION"):
                    c = rig.pose.bones[n].constraints.new(kind)
                    c.target, c.subtarget = arm, n
            # 3. bake every source action the game animations use onto the rig
            baked = {}
            for game_anim, (action, f0, f1) in s["anims"].items():
                key = action or "_main"
                if key not in baked:
                    if action:
                        arm.animation_data.action = bpy.data.actions[action]
                    span = max(f1, 1)
                    bpy.ops.nla.bake(frame_start=0, frame_end=span if key != "_main" else s["anims"]["move"][2],
                                     only_selected=False, visual_keying=True, clear_constraints=False,
                                     use_current_action=False, bake_types={"POSE"})
                    baked[key] = rig.animation_data.action.name
            for pb in rig.pose.bones:
                for c in list(pb.constraints):
                    pb.constraints.remove(c)
            anims = {g: (baked[a or "_main"], f0, f1) for g, (a, f0, f1) in s["anims"].items()}
            for act, f0, f1 in set(anims.values()):
                close_loop(bpy.data.actions[act], f0, f1)
            if s.get("hover"):
                lo, hi = world_box(meshes)
                for g, (act, f0, f1) in anims.items():
                    rig.animation_data.action = bpy.data.actions[act]
                    hover_sway(rig.pose.bones["hover"], hi[2] - lo[2], f0, f1)
            # 4. meshes: world space, skin weights moved onto kept bones, bound to the rig
            bpy.ops.object.mode_set(mode="OBJECT")
            for o in meshes:
                mw = o.matrix_world.copy()
                o.parent = None
                o.matrix_world = mw
                for m in list(o.modifiers):
                    if m.type == "ARMATURE":
                        o.modifiers.remove(m)
                select([o], o)
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                target = {}
                for g in o.vertex_groups:
                    if g.name in keep:
                        target[g.index] = g.name
                    elif g.name in arm.data.bones:
                        target[g.index] = kept_ancestor(arm.data.bones[g.name]) or keep[0]
                gid = {n: (o.vertex_groups.get(n) or o.vertex_groups.new(name=n)) for n in keep}
                acc = {}
                for v in o.data.vertices:
                    for g in v.groups:
                        if g.group in target and o.vertex_groups[g.group].name not in keep:
                            acc.setdefault((v.index, target[g.group]), 0.0)
                            acc[(v.index, target[g.group])] += g.weight
                for (vi, n), w in acc.items():
                    gid[n].add([vi], w, "ADD")
                for g in [g for g in o.vertex_groups if g.name not in keep]:
                    o.vertex_groups.remove(g)
                # vertices left without weight (groups that were no bone) would stay behind at rest: nearest kept bone
                heads = {n: rest[n][0] for n in keep}
                for v in o.data.vertices:
                    if sum(g.weight for g in v.groups if o.vertex_groups[g.group].name in keep) < 1e-3:
                        n = min(heads, key=lambda b: (heads[b] - v.co).length)
                        gid[n].add([v.index], 1.0, "REPLACE")
                mod = o.modifiers.new("rig", "ARMATURE")
                mod.object = rig
            bpy.data.objects.remove(arm, do_unlink=True)
            bpy.context.view_layer.update()
            gun_tail = rig.matrix_world @ rig.data.bones[s["gun"]].tail_local
            lo, hi = world_box(meshes)
            locs = [add_locator("barrel", rig, s["gun"], gun_tail),
                    add_locator("smoke", rig, keep[0], Vector((0, hi[1] * 0.8, (hi[2] - lo[2]) * 0.55))),
                    add_locator("exhaust", rig, keep[0], Vector((0, hi[1] * 0.8, (hi[2] - lo[2]) * 0.55)))]
            finish(name, meshes, rig, locs, anims)

        else:   # rebuild: the source rig is unusable (Source-engine export); new leg rig from its skin groups
            o = meshes[0]
            # the export stores parts out of place and lets its armature put them back: bake that deformation in
            dg = bpy.context.evaluated_depsgraph_get()
            # a brand-new mesh from plain data: whatever the source mesh carries breaks Blender's modifiers
            src = o.data
            ev = o.evaluated_get(dg).data
            clean = bpy.data.meshes.new(src.name + "_clean")
            clean.from_pydata([o.matrix_world @ v.co for v in ev.vertices], [], [list(p.vertices) for p in src.polygons])
            for m in src.materials:
                clean.materials.append(m)
            clean.polygons.foreach_set("material_index", [p.material_index for p in src.polygons])
            if src.uv_layers:
                uv = clean.uv_layers.new(name="uv0")
                uv.data.foreach_set("uv", [c for d in src.uv_layers[0].data for c in d.uv])
            new_o = bpy.data.objects.new(o.name, clean)
            bpy.context.scene.collection.objects.link(new_o)
            for g in o.vertex_groups:
                ng = new_o.vertex_groups.new(name=g.name)
            for v in src.vertices:
                for g in v.groups:
                    new_o.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
            bpy.data.objects.remove(o, do_unlink=True)
            o = new_o
            clean.update()
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = mw
            for m in list(o.modifiers):
                o.modifiers.remove(m)
            select([o], o)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            for x in [x for x in bpy.context.scene.objects if x is not o]:
                bpy.data.objects.remove(x, do_unlink=True)

            def centroid(prefixes, verts=None):
                ids = {g.index for g in o.vertex_groups if g.name.startswith(prefixes)}
                pts = [v.co.copy() for v in o.data.vertices if any(g.group in ids and g.weight > 0.5 for g in v.groups)]
                return sum(pts, Vector()) / len(pts), pts
            seat, _ = centroid(("rotator", "Lever", "button"))
            footA, _ = centroid(("legA3",))
            gun, _ = centroid(("pulsegun",))
            # orient: seat above the feet (+Z), gun ahead (-Y)
            up = (seat - footA).normalized()
            o.data.transform(up.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4())
            gun, _ = centroid(("pulsegun",))
            seat, _ = centroid(("rotator", "Lever", "button"))
            d = gun - seat
            o.data.transform(Matrix.Rotation(math.atan2(d.x, -d.y), 4, "Z"))
            co = [v.co for v in o.data.vertices]
            lo = Vector([min(c[i] for c in co) for i in range(3)])
            hi = Vector([max(c[i] for c in co) for i in range(3)])
            k = s["height"] / (hi.z - lo.z)
            o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))))
            import bmesh  # type: ignore
            bm = bmesh.new()                                # degenerate source faces make collapse decimation explode
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.002)
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
            rider_ids = []
            if s.get("rider"):     # seated trooper (make_rider.py glb, pelvis at origin) on the saddle, rides the root bone
                seat_at, _ = centroid(("rotator", "Lever", "button"))
                parts = add_rider(name, s["rider"], seat_at)
                n0 = len(o.data.vertices)
                select(parts + [o], o)
                bpy.ops.object.join()
                rider_ids = list(range(n0, len(o.data.vertices)))
                for x in [x for x in bpy.context.scene.objects if x is not o]:
                    bpy.data.objects.remove(x, do_unlink=True)
            gun_at, gun_pts = centroid(("pulsegun",))      # before the skin groups are renamed for the new rig
            gun_tip = min(gun_pts, key=lambda c: c.y)
            def joint(g1, g2):
                """centre of the vertices two skin groups share, else the top of the second group"""
                i1 = {g.index for g in o.vertex_groups if g.name.startswith(g1)}
                i2 = {g.index for g in o.vertex_groups if g.name.startswith(g2)}
                both = [v.co.copy() for v in o.data.vertices if {g.group for g in v.groups} & i1 and {g.group for g in v.groups} & i2]
                if both:
                    return sum(both, Vector()) / len(both)
                top = sorted((v.co.copy() for v in o.data.vertices if {g.group for g in v.groups} & i2), key=lambda c: -c.z)[:20]
                return sum(top, Vector()) / len(top)
            J = {}
            for L in ("A", "B"):
                J[f"hip{L}"] = joint(("root", "rotator"), (f"leg{L}1",))
                J[f"knee{L}"] = joint((f"leg{L}1",), (f"leg{L}2",))
                J[f"ankle{L}"] = joint((f"leg{L}2",), (f"leg{L}3",))
            rig_data = bpy.data.armatures.new("rig")
            rig = bpy.data.objects.new("rig", rig_data)
            bpy.context.scene.collection.objects.link(rig)
            select([rig], rig)
            bpy.ops.object.mode_set(mode="EDIT")
            root = rig_data.edit_bones.new("root")
            root.head, root.tail = Vector((0, 0, J["hipA"].z)), Vector((0, 0, J["hipA"].z + 0.5))
            for L in ("A", "B"):
                th = rig_data.edit_bones.new(f"thigh{L}"); th.head, th.tail, th.parent = J[f"hip{L}"], J[f"knee{L}"], root
                sh = rig_data.edit_bones.new(f"shin{L}"); sh.head, sh.tail, sh.parent = J[f"knee{L}"], J[f"ankle{L}"], th
                ft = rig_data.edit_bones.new(f"foot{L}"); ft.head, ft.parent = J[f"ankle{L}"], sh
                ft.tail = J[f"ankle{L}"] + Vector((0, -0.4, -0.2))
            bpy.ops.object.mode_set(mode="OBJECT")
            remap = {"legA1": "thighA", "legA2": "shinA", "legA3": "footA", "legB1": "thighB", "legB2": "shinB", "legB3": "footB"}
            new = {n: o.vertex_groups.new(name=n) for n in ("root", "thighA", "shinA", "footA", "thighB", "shinB", "footB")}
            old = {g.index: g.name for g in o.vertex_groups if g.name not in new}
            for v in o.data.vertices:
                for g in list(v.groups):
                    if g.group in old:
                        n = next((t for p, t in remap.items() if old[g.group].startswith(p)), "root")
                        new[n].add([v.index], g.weight, "ADD")
            for g in [o.vertex_groups[i] for i in sorted(old, reverse=True)]:
                o.vertex_groups.remove(g)
            if rider_ids:
                new["root"].add(rider_ids, 1.0, "REPLACE")
            mod = o.modifiers.new("rig", "ARMATURE")
            mod.object = rig
            # walk: 48-frame loop, legs half a cycle apart, a slight body bob; feet kept level
            select([rig], rig)
            bpy.ops.object.mode_set(mode="POSE")
            rig.animation_data_create()
            walk = bpy.data.actions.new("walk")
            rig.animation_data.action = walk
            rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
            rot_at = lambda p, ang: Matrix.Translation(p) @ Matrix.Rotation(ang, 4, "X") @ Matrix.Translation(-p)
            for f in range(0, 49):
                ph = 2 * math.pi * f / 48
                bob = Matrix.Translation((0, 0, 0.04 * s["height"] * math.cos(2 * ph)))
                rig.pose.bones["root"].matrix = bob @ rest["root"]
                for L, off in (("A", 0.0), ("B", math.pi)):
                    a = -math.radians(28) * math.sin(ph + off)               # forward swing = toward -Y
                    b = math.radians(30) * max(0.0, math.sin(ph + off + math.pi / 2))
                    hip, knee, ank = J[f"hip{L}"], J[f"knee{L}"], J[f"ankle{L}"]
                    m_th = bob @ rot_at(hip, a)
                    knee_n = m_th @ knee
                    m_sh = Matrix.Translation(knee_n) @ Matrix.Rotation(a + b, 4, "X") @ Matrix.Translation(-knee) @ bob.inverted() @ bob
                    ank_n = m_sh @ ank
                    m_ft = Matrix.Translation(ank_n - ank)
                    for bn, m in ((f"thigh{L}", m_th), (f"shin{L}", m_sh), (f"foot{L}", m_ft)):
                        rig.pose.bones[bn].matrix = m @ rest[bn]
                        bpy.context.view_layer.update()
                for pb in rig.pose.bones:
                    pb.keyframe_insert("location", frame=f)
                    pb.keyframe_insert("rotation_quaternion", frame=f)
            bpy.ops.object.mode_set(mode="OBJECT")
            locs = [add_locator("barrel", rig, "root", gun_tip),
                    add_locator("smoke", rig, "root", Vector((0, 0.5, J["hipA"].z)))]
            finish(name, [o], rig, locs, {"idle": ("walk", 0, 48), "move": ("walk", 0, 48), "attack": ("walk", 0, 48)})

    os.makedirs(os.path.dirname(SIDE), exist_ok=True)
    json.dump(side, open(SIDE, "w"), indent=1)


# ─────────────────────────────── textures ───────────────────────────────
def camo(base, seed=7):
    """Repaint an RGB texture (float 0-255) in weathered olive / dark green / brown camo with rust in the dark
    creases, keeping the original's light and panel detail (Imperial AAT, user ref tanks-encyclopedia 2026-11-09)."""
    import numpy as np
    from PIL import Image, ImageFilter
    h, w = base.shape[:2]
    rng = np.random.default_rng(seed)
    lum = base.mean(axis=2, keepdims=True) / 255
    detail = np.clip(lum / max(float(lum.mean()), 1e-3), 0.6, 1.35)          # panel lines, dirt, highlights
    def blobs(cells, blur):   # smooth random field 0..1
        n = Image.fromarray((rng.random((cells, cells)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        return np.asarray(n.filter(ImageFilter.GaussianBlur(blur)), np.float32)[..., None] / 255
    a, b = blobs(10, w / 60), blobs(14, w / 70)
    col = np.where(a > 0.58, (96, 116, 62), (138, 150, 86))                   # dark green patches on olive (< ~100 RGB renders black)
    col = np.where((b > 0.66) & (a <= 0.58), (132, 112, 76), col).astype(np.float32)   # brown patches
    out = col * detail
    rust = np.clip((0.45 - lum) * 2.5, 0, 1) * blobs(40, 2) * 0.7            # rust in the dark creases
    out = out * (1 - rust) + np.array((150, 96, 56), np.float32) * detail * rust
    wear = (blobs(90, 1) > 0.8) * np.clip(lum - 0.45, 0, 1) * 1.6            # chipped paint on raised edges
    out = out * (1 - wear) + np.array((150, 150, 140), np.float32) * wear
    assert out.shape == base.shape
    return np.clip(out, 0, 255)


def textures(*only):
    import numpy as np
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from flora_props import save_dxt5_mips
    sys.path.insert(0, os.path.join(os.environ["LOCALAPPDATA"], "universal-modder/tools/blender-4.2.3-windows-x64/4.2/scripts/addons"))
    from io_pdx_mesh.pdx_data import read_meshfile, write_meshfile
    side = json.load(open(SIDE))
    for name, mats in side.items():
        if only and name not in only:
            continue
        px = SPECS.get(name, {}).get("tex_px", TEX_PX)
        full = lambda v, n=px: np.full((n, n), v, np.float32)
        for m in mats:
            base = (np.asarray(Image.open(m["base"]).convert("RGB").resize((px, px), Image.LANCZOS)).astype(np.float32)
                    if m.get("base") else np.dstack([full(150)] * 3))     # untextured part: plain grey
            if SPECS.get(name, {}).get("camo"):
                base = camo(base)
            if SPECS.get(name, {}).get("gain"):   # dark sources: atlas colours < ~100 RGB render black in game
                base = np.clip(base * SPECS[name]["gain"], 0, 255)
            if SPECS.get(name, {}).get("tint"):   # one-colour repaint that keeps the light / panel detail
                lum = base.mean(axis=2, keepdims=True)
                base = np.clip(np.array(SPECS[name]["tint"], np.float32) * np.clip(lum / max(float(lum.mean()), 1e-3), 0.6, 1.35), 0, 255)
                if SPECS[name].get("tint_dark"):   # two-tone: the darkest areas (panels, plating) take the second colour
                    rel = lum / max(float(lum.mean()), 1e-3)
                    cut = SPECS[name].get("tint_cut", 0.75)
                    dark = np.array(SPECS[name]["tint_dark"], np.float32) * np.clip(rel / cut, 0.85, 1.2)
                    base = np.where(rel < cut, dark, base)
            if SPECS.get(name, {}).get("decal"):   # logo painted in UV space (uv_decal.py), laid over after the tint
                ov = np.asarray(Image.open(SPECS[name]["decal"]).convert("RGBA").resize(base.shape[1::-1], Image.LANCZOS), np.float32) / 255.0
                base = base * (1 - ov[..., 3:]) + ov[..., :3] * 255.0 * ov[..., 3:]
            save_dxt5_mips(np.dstack([base, full(255)]), f"{OUT}/{m['stem']}_diffuse.dds")
            # normal: flat (the walker mod's layout); spec: R 0, G specular, B metal, A gloss from glTF metallic-roughness
            save_dxt5_mips(np.dstack([full(132, 64), full(130, 64), full(0, 64), full(128, 64)]), f"{OUT}/{m['stem']}_normal.dds")   # flat: tiny
            if m.get("mr"):
                mr = np.asarray(Image.open(m["mr"]).convert("RGB").resize((px, px), Image.LANCZOS)).astype(np.float32)
                rough, metal = mr[..., 1] / 255, mr[..., 2] / 255
            else:
                rough, metal = full(0.6, 64), full(0.4, 64)
            save_dxt5_mips(np.dstack([full(0, metal.shape[0]), 30 + 50 * metal, 60 * metal, 30 + 180 * (1 - rough)]), f"{OUT}/{m['stem']}_spec.dds")
        mesh = f"{OUT}/{name}.mesh"
        root = read_meshfile(mesh)
        for mat, m in zip(root.iter("material"), mats):
            mat.set("diff", [f"{m['stem']}_diffuse.dds"])
            mat.set("n", [f"{m['stem']}_normal.dds"])
            mat.set("spec", [f"{m['stem']}_spec.dds"])
        write_meshfile(mesh, root)
        print("textures", name, len(mats))


# ─────────────────────────────── entities ───────────────────────────────
STATES = """	state = {{ name = "idle"				animation = "idle"   animation_blend_time = 0.3 }}
	state = {{ name = "move"				animation = "move"   animation_blend_time = 0.3
		event = {{ time = 0 node="smoke" particle = "tank_exhaust_particle"  keep_particle = no trigger_once = yes }}
		event = {{ trigger_once = yes sound = {{ soundeffect = "{move_sound}" }} }}
	}}
	state = {{ name = "retreat"			animation = "move"   animation_blend_time = 0.3
		event = {{ trigger_once = yes sound = {{ soundeffect = "{move_sound}" }} }}
	}}
	state = {{ name = "attack"			animation = "attack" animation_blend_time = 0.3
		event = {{ time = 0 node="barrel" particle = "hosw_muzzle{bolt}_vehicle"  keep_particle = yes light = "mg_muzzle_flash" sound = {{ soundeffect = infantry_blaster_attack }} }}
		event = {{ time = 0 node="barrel" particle = "hosw_{bolt}_blastershot_vehicle"  keep_particle = yes }}
		event = {{ time = 0.6 node="barrel" particle = "hosw_muzzle{bolt}_vehicle"  keep_particle = yes sound = {{ soundeffect = infantry_blaster_attack }} }}
		event = {{ time = 0.6 node="barrel" particle = "hosw_{bolt}_blastershot_vehicle"  keep_particle = yes }}
	}}
	state = {{ name = "defend"			animation = "attack" animation_blend_time = 0.3
		event = {{ time = 0 node="barrel" particle = "hosw_muzzle{bolt}_vehicle"  keep_particle = yes light = "mg_muzzle_flash" sound = {{ soundeffect = infantry_blaster_attack }} }}
		event = {{ time = 0 node="barrel" particle = "hosw_{bolt}_blastershot_vehicle"  keep_particle = yes }}
		event = {{ time = 0.6 node="barrel" particle = "hosw_muzzle{bolt}_vehicle"  keep_particle = yes sound = {{ soundeffect = infantry_blaster_attack }} }}
		event = {{ time = 0.6 node="barrel" particle = "hosw_{bolt}_blastershot_vehicle"  keep_particle = yes }}
	}}
	state = {{ name = "support_attack"	animation = "attack" animation_blend_time = 0.3
		event = {{ time = 0 node="barrel" particle = "hosw_muzzle{bolt}_vehicle"  keep_particle = yes light = "mg_muzzle_flash" sound = {{ soundeffect = infantry_blaster_attack }} }}
		event = {{ time = 0 node="barrel" particle = "hosw_{bolt}_blastershot_vehicle"  keep_particle = yes }}
		event = {{ time = 0.6 node="barrel" particle = "hosw_muzzle{bolt}_vehicle"  keep_particle = yes sound = {{ soundeffect = infantry_blaster_attack }} }}
		event = {{ time = 0.6 node="barrel" particle = "hosw_{bolt}_blastershot_vehicle"  keep_particle = yes }}
	}}
	state = {{ name = "training"			animation = "idle"   animation_blend_time = 0.3 }}
"""
# bolt colour: Clone Wars Republic guns blue; droid (CIS) and Imperial-era (AT-ST, AT-AT) guns red
BOLT = lambda name: "red" if re.search(r"cis_|aat|imp_", name) else "blue"
PLANE_STATES = """	state = { name = "idle"		animation = "idle" }
	state = { name = "fire"		animation = "idle"
		event = { time = 0 node = "barrel" particle = "plane_mg_muzzle_particle" keep_particle = yes sound = { soundeffect = "airplane_ger_jet_fire" } }
	}
	state = { name = "bomb"		animation = "idle"
		event = { time = 0 node = "barrel" particle = "bomb_particle" keep_particle = yes sound = { soundeffect = "airplane_bomb" } }
	}
	state = { name = "crash"	animation = "idle"
		event = { time = 0 node = "smoke" particle = "explosion_particle" keep_particle = yes sound = { soundeffect = "airplane_crash" } }
	}
	state = { name = "explode"	animation = "idle"
		event = { time = 0 particle = "vehicle_explode_effect" keep_particle = yes }
	}
"""
# walker battalion sprite -> (model, scale) for the Republic and for the Separatist members
# scale: the clone trooper stands ~6 units tall in game and a vanilla tank ~2 high / 4.5 long; walkers tower over both
REP_MAP = {"walker_light": ("hod_atrt", 1.1), "walker_iron_strider": ("hod_atte", 1.0), "walker_mech211": ("hod_atte", 1.1),
           "walker_sturmlaufer": ("hod_atte", 1.2), "walker_super_heavy": ("hod_atte", 1.5)}
CIS_MAP = {   # Separatist tanks (vanilla tank units, Droid Armour tab): all AATs, bigger by class
    "light_armor": ("hod_aat", 0.45), "medium_armor": ("hod_aat", 0.55), "heavy_armor": ("hod_aat", 0.65)}
CIS_TAGS = ("CIS", "TDF", "TCU", "CMG", "IBC")


def wire():
    gfx = ["objectTypes = {", "\t# HOD: Star Wars walker / tank unit models (unit_models.py)"]
    asset = ["# HOD: Star Wars walker / tank unit entities (unit_models.py). Republic: AT-RT / AT-TE; Separatists: AAT"]
    anims = ["# HOD: animations of the Star Wars unit models (unit_models.py wire)"]
    for name in SPECS:
        gfx.append(f'\tpdxmesh = {{\n\t\tname = "{name}_mesh"\n\t\tfile = "{OUT}/{name}.mesh"\n'
                   + "".join(f'\t\tanimation = {{ id = "{a}" type = "{name}_{a}_animation" }}\n' for a in ("idle", "move", "attack"))
                   + "\t}")
        # animation files resolve against their .asset's own folder: declared next to the models, like the walker mod
        anims += [f'animation = {{ name = "{name}_{a}_animation" file = "{name}_{a}.anim" }}' for a in ("idle", "move", "attack")]
        sound = "tank_engine_light_move" if name == "hod_aat" else "tank_engine_medium_move"
        if SPECS[name].get("infantry"):          # droid infantry: footsteps, no exhaust smoke
            sound = "infantry_move_animation"
        states = PLANE_STATES if SPECS[name].get("plane") else STATES.format(move_sound=sound, bolt=BOLT(name))
        if SPECS[name].get("infantry"):
            states = "".join(l for l in states.splitlines(True) if 'node="smoke"' not in l)
        asset.append(f'entity = {{\n\tname = "{name}_entity"\n\tpdxmesh = "{name}_mesh"\n' + states + "\tscale = 1.0\n}")
    for tags, table in ((("REP",), REP_MAP), (CIS_TAGS, CIS_MAP)):
        for tag in tags:
            for sprite, (model, scale) in table.items():
                asset.append(f'entity = {{ name = "{tag}_{sprite}_entity" clone = "{model}_entity" scale = {scale} }}')
    open("gfx/entities/hod_sw_walkers.gfx", "w", encoding="utf-8", newline="\n").write("\n".join(gfx + ["}", ""]))
    open("gfx/entities/hod_sw_walkers.asset", "w", encoding="utf-8", newline="\n").write("\n".join(asset) + "\n")
    open(f"{OUT}/hod_walkers_anims.asset", "w", encoding="utf-8", newline="\n").write("\n".join(anims) + "\n")
    print("wired", len(asset), "entries")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"convert": convert, "textures": textures, "wire": wire}[args[0]](*args[1:])
