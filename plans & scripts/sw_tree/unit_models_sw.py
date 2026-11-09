"""Executor-tree units -> our 3D models, per country, per equipment generation.

    python -B "plans & scripts/sw_tree/unit_models_sw.py"

Land units: the engine looks up <TAG>_<subunit>_<visual_level>_entity (then without the level, then the graphical
culture instead of the tag); visual_level comes from the equipment, so the model follows the researched gear
(DC-15 -> DC-17m -> E-11 = old trooper / phase I -> phase II -> stormtrooper). VISUAL below rewrites the equipment's
visual_level so every generation of walkers / tanks has its own number.
Planes: <TAG>_<equipment>_entity (one model per fighter tech), plus archetype / subunit / sprite names as fallbacks.
Writes gfx/entities/zz_hod_sw_unit_models.asset (zz_: clones need their parents loaded first, files load alphabetically).
"""
import re

# ── equipment visual levels (common/units/equipment/hod_sw_zz_imperial_land_vehicle.txt) ──
VISUAL = {   # 2026-11-08: fo_atst/crawler/utat/advanced_*/atap/av7/hovercraft/rtt equipment gone in the purge
         "atrt_equipment": 0, "atrct_equipment": 0, "atrt2_equipment": 1, "atpt_equipment": 2, "atdp_equipment": 3, "atst_equipment": 4,
          "republictank": 0, "repulsor_equipment": 2, "h_repulsor_equipment": 3,
          "px_equipment": 5, "ihrt_equipment": 4, "imperialtank": 7,
          "atte_equipment": 0, "atat_equipment": 2, "elite_atat_equipment": 3, "fo_atat_equipment": 4,
          "spha_equipment": 0, "spma_equipment": 1, "atpt_art_equipment": 3, "utat_art_equipment": 4, "rx_equipment": 0, "ataa_equipment": 1, "atot_equipment": 1, "itt_equipment": 3, "itc_equipment": 4}

OLD, P1, P2, STORM = "REP_old_trooper_entity", "REP_infantry_entity", "REP_PHASE_II_infantry_entity", "REP_GLE_infantry_entity"
DROID, FELU = "CIS_infantry_entity", "FLT_infantry_entity"
AAT, ATTE, ATRT, LANCE = "hod_aat_entity", "hod_atte_entity", "hod_atrt_entity", "hod_lance_walker_entity"
B = lambda n: f"hod_{n}_entity"    # Battlefront II conversions (unit_models.py glb_static)
TX130, SABER, NR99, HAIL = B("rep_hover_fightertank"), B("imp_hover_fightertank"), B("cis_tread_tank"), B("cis_tread_hailfire")
SPIDER, DEKA, ATST, ATAT, ATRT2 = B("cis_walk_spider"), B("cis_walk_droideka"), B("imp_walk_atst"), B("imp_walk_atat"), B("rep_walk_oneman_atst")
BARC, BIKE, STAP = B("rep_hover_barcspeeder"), B("rep_hover_speederbike"), B("cis_hover_stap")
ATOT, ITT, JUGG, ATAP = B("atot"), B("itt"), B("juggernaut"), B("atap")
TX130S, SABER2M, ORPBIKE = B("tx130s"), B("saber2m"), B("orp_hover_speederbike")   # BF2 fighter tank + Phase II / stormtrooper gunner (unit_models.py)
# 2026-11-08 (user): AT-AT prototype (SWBF3 Clone Wars AT-AT), AAC-1 speeder tank (BF3 hover tank, replaces the PX-10),
# 74-Z = BF2 Imperial speeder bike + stormtrooper rider, Republic BTL-B Y-wing
CWATAT, AAC1, IMPBIKE, REPYWING = B("cw_atat"), B("all_bf3_hover_tank"), B("imp_hover_speederbike"), B("rep_fly_ywing")
CISFT = B("cis_hover_fightertank")
T4B, T16 = B("t4b"), B("t16")
# Thrawn's Revenge 3.3 (permission needed before release): late-war AT-RT, K79-S80, Imperial drop transport, Theta shuttle
TR_ATRT, TR_ITT, TR_IDT, TR_THETA = B("tr_atrt"), B("tr_itt"), B("tr_idt"), B("tr_theta")
ATACT, ATTC, IHRT, RM09 = B("atact"), B("attc"), B("ihrt"), B("rm09")
FOTR_ATOT = B("fotr_atot")   # Fall of the Republic 1.4 AT-OT, animated
# Fall of the Republic 1.4 batch (2026-11-08, user: convert them all except the heavy transports)
F_AV7, F_UTAA, F_SPHA, F_SPHAT, F_J1 = B("fotr_av7"), B("fotr_utaa"), B("fotr_spha"), B("fotr_sphat"), B("fotr_j1")
F_UTAT, TR_ATAA, TR_SPMAT = B("fotr_utat"), B("tr_ataa"), B("tr_spmat")   # 2026-11-08: UT-AT artillery (FotR), AT-AA walker (TR / vanilla EaW)
F_AAT, F_PERS, F_HAGM, F_SUPER, F_GAT, F_CRAB = B("fotr_aat"), B("fotr_persuader"), B("fotr_hagm"), B("fotr_supertank"), B("fotr_gat"), B("fotr_crab")
F_OG9, F_HAIL, F_MTT = B("fotr_og9"), B("fotr_hailfire"), B("fotr_mtt")   # 2026-11-08 EaW mod assets (WIP/3d/b)   # New Order Mod EaW assets: T4-B heavy tank (heavy repulsor slot), T-16 Skyhopper   # BF2 Classic LGD Separatist fighter tank
# Conversion Pack (BF2 Classic DATA/_LVL_PC/SIDE, swbf-unmunge) 2026-11-08
ATXT, SPHAT, MTT, GAT, HAG = B("rep_walk_atxt"), B("rep_walk_sphat"), B("cis_hover_mtt"), B("cis_hover_gat"), B("cis_hover_hag")
DWARF, SWAMP = B("cis_walk_dwarfspider"), B("rep_hover_swampspeeder")   # Sketchfab downloads (credits in unit_models.py)
# Republic at War (EaW .alo + .ala, alo_to_glb.py --anim, unit_models.py bake) 2026-11-08: animated
R_ATTE, R_ATRT, R_TX130, R_UTAT, R_JUGG, R_BARC = (B("rev_" + n) for n in ("atte", "atrt", "sabertank", "utat", "juggernaut", "barc"))

# subunit -> {visual level: (model, scale)}; level None = the plain entity (no level found)
def lv(*pairs):
    return dict(pairs)

REP = {
    # rifles: republic_equipment_1 (DC-15A) 3, imperial_equipment_1 (DC-15S) 4, _2 (DC-17m) 5, _3 (E-11) 6
    "blaster_infantry": lv((None, (OLD, None)), (3, (OLD, None)), (4, (P1, None)), (5, (P2, None)), (6, (STORM, None))),
    "stormtrooper": lv((None, (P1, None)), (3, (P1, None)), (4, (P1, None)), (5, (P2, None)), (6, (STORM, None))),
    # Lance walker, (1 = AT-RT, now the extra light walker), AT-XT, AT-AP, AT-ST, heavy AT-ST (2026-11-08)
    "light_vehicle": lv((None, (LANCE, 0.9)), (0, (LANCE, 0.9)), (2, (ATXT, 1.0)), (3, (ATAP, 0.75)),
                        (4, (ATST, 1.0)), (5, (ATST, 1.15))),
    "scoutwalker": lv((None, (R_ATRT, 1.0)), (0, (R_ATRT, 1.0)), (1, (TR_ATRT, 1.0))),   # extra light walker: AT-RT, late-war AT-RT (979)
    # TX-130 Saber, TX-130S (repulsor tech), T4-B heavy tank (heavy repulsor tech), AAC-1 (px tech), 2-M Saber (crawler
    # tech since 2026-11-08; the TIE crawler is gone)
    "assault_vehicle": lv((None, (R_TX130, 1.0)), (0, (R_TX130, 1.0)), (2, (TX130S, 1.15)), (3, (T4B, 1.0)),
                          (4, (B("x_mow_clone_hovertank"), 1.0)), (5, (AAC1, 1.0)), (7, (SABER2M, 1.3))),   # 4 = heavy repulsortank: clone hover tank (Men of War mod, user 2026-11-09)
    # AT-TE, UT-AT, AT-AT prototype, AT-AT, AT-ACT
    "heavy_vehicle": lv((None, (R_ATTE, 1.0)), (0, (R_ATTE, 1.0)), (1, (R_UTAT, 1.0)), (2, (CWATAT, 1.0)), (3, (ATAT, 1.0)), (4, (ATACT, 1.0))),   # 2 = AT-AT prototype (BF3 CW AT-AT, gunmetal repaint 2026-11-09)   # 4 = AT-ACT
    "super_heavy_vehicle": lv((None, (ATAT, 1.25))),
    # hovercraft, AT-OT, Republic troop transport, K79-S80, Imperial troop carrier (no RTT / hovercraft model yet: AT-OT)
    "armored_troop_transport": lv((None, (FOTR_ATOT, 1.0)), (0, (SWAMP, 1.0)), (1, (FOTR_ATOT, 1.0)), (2, (FOTR_ATOT, 1.1)),   # AT-OT: Fall of the Republic (2026-11-08)
                                (3, (ATTC, 1.0)), (4, (TR_ITT, 1.0))),   # 2026-11-08: AT-TC (itt tech), K79-S80 (itc tech)   # K79-S80 (Thrawn's Revenge), Imperial troop carrier (Andor)
    "heavy_armored_troop_transport": lv((None, (R_JUGG, 1.0))),
    # SPHA walker, SPMA-T (SPHA-T turbolaser), J-1 proton cannon; AT-AP, AV-7, AV-7; UT-AA (FotR 2026-11-08)
    "mobile_artillery": lv((None, (F_SPHA, 1.0)), (0, (F_SPHA, 1.0)), (1, (TR_SPMAT, 1.0)), (2, (F_J1, 1.1)), (3, (ATAP, 0.75)), (4, (F_UTAT, 1.0))),   # 1 = SPMA-T, 3 = AT-AP artillery variant, 4 = UT-AT artillery
    "mobile_anti_tank": lv((None, (F_AV7, 1.0)), (0, (ATAP, 0.7)), (1, (F_AV7, 1.0)), (2, (F_AV7, 1.15))),
    "mobile_anti_air": lv((None, (F_UTAA, 1.0)), (0, (F_UTAA, 1.0)), (1, (TR_ATAA, 1.0)), (2, (F_UTAA, 1.1))),   # 1 = AT-AA
    # support platform (Old Republic speeder bike), BARC, 614-AvA (BF2 Republic bike, Phase II rider), 74-Z (BF2 Imperial bike)
    "speeder": lv((None, (R_BARC, 1.5)), (0, (ORPBIKE, 1.5)), (1, (R_BARC, 1.5)), (2, (BIKE, 1.5)), (3, (IMPBIKE, 1.5))),   # x1.5: user 2026-11-08, speeders too small next to the tanks
}
# 2026-11-08 (user: "the CIS are a mess"): Separatist set rebuilt on Fall of the Republic 1.4 (unit_models.py hod_fotr_cis_*)
F_B1, F_B2, F_BX = B("fotr_cis_b1"), B("fotr_cis_b2"), B("fotr_cis_bx")
F_DSD, F_LR57, F_TRI, F_PROTO = B("fotr_cis_dsd"), B("fotr_cis_lr57"), B("fotr_cis_tridroid"), B("fotr_cis_protodeka")
F_HAGM2, F_HAML, F_CAART, F_CONFED = B("fotr_cis_hagm"), B("fotr_cis_haml"), B("fotr_cis_ca_artillery"), B("fotr_cis_supertank2")
F_STAP, F_ADVSTAP, F_CISMTT, F_DTRANS = B("fotr_cis_stap"), B("fotr_cis_advestap"), B("fotr_cis_mtt"), B("fotr_cis_transport")
X = lambda n: B("x_" + n)   # 2026-11-08 second pass (unit_models.py hod_x_*: FotR + Republic at War extras)
DEKA2, RAW_DWARF, RAW_CRAB, CSA_C1, HAIL_RIOT = X("droideka"), X("raw_dwarf"), X("raw_crab"), X("csa_c1"), X("hailfire_riot")
# Republic-only elite battalions (common/units/hod_rep_special_troopers.txt, 2026-11-09): RaW ARC / commando, BF2 clone shock trooper / black JKA Katarn commando
REP.update({"rep_arc_trooper": lv((None, (X("raw_arc"), None))), "rep_clone_commando": lv((None, (X("raw_commando"), None))),
            "rep_shock_trooper": lv((None, (X("imp_shock"), None))), "rep_imperial_commando": lv((None, (X("imp_commando"), None)))})
# one model per CIS equipment (user 2026-11-08: "you reuse a bit too much of the same ones"); names = the CIS localisation
CIS = {
    # E-5 / E-5C / E-5s: B1 battle droids; E-5 Mk II: BX commando droids (user 2026-11-08)
    # E-5: old-pattern B1 (RaW), E-5C: Clone Wars B1, E-5s: Republic Commando B1, E-5 Mk II: BX commando (user 2026-11-08)
    "blaster_infantry": lv((None, (X("raw_b1"), None)), (3, (X("raw_b1"), None)), (4, (F_B1, None)), (5, (X("repcom_b1"), None)), (6, (F_BX, None))),
    "stormtrooper": lv((None, (X("raw_b1"), None)), (3, (X("raw_b1"), None)), (4, (F_B1, None)), (5, (X("repcom_b1"), None)), (6, (F_BX, None))),
    # CIS-only special battalions (common/units/hod_cis_special_droids.txt, techs in the infantry folder)
    "cis_b2_droid": lv((None, (F_B2, None))), "cis_droideka": lv((None, (X("raw_deka"), 1.0)), (0, (X("raw_deka"), 1.0)), (2, (X("foc_deka2"), 1.0))),
    "cis_b3_droid": lv((None, (X("mow_b3"), None))),   # 2026-11-09: Men of War mod B3   # droideka: Mk I (RaW), Mk II (Forces of Corruption UI_DROIDEKA)
    "cis_hailfire_droid": lv((None, (F_HAIL, 1.0))),
    "scoutwalker": lv((None, (F_LR57, 1.0)), (0, (F_LR57, 1.0)), (1, (X("espo"), 1.0))),   # user 2026-11-09: LR-57, Espo walker (swapped with the light walkers)
    # user 2026-11-09: LR-57, Espo walker, dwarf spider (BF2), A-DSD (RaW dwarf repainted); the hailfire is a CIS special unit
    "light_vehicle": lv((None, (F_CRAB, 0.9)), (0, (F_CRAB, 0.9)), (2, (RAW_CRAB, 1.0)), (3, (X("umbaran_hmc"), 1.0)), (4, (X("mow_scorpenek"), 1.0))),   # 2026-11-09: LM-432, LM-432 Mk II, Umbaran MHC, Scorpenek (both Men of War mod)
    # user 2026-11-09: AAT, CIS-colour AAT (RaW), Confederate super tank, TF super tank, NR-N99 Persuader, Imperial-service AAT (green camo repaint)
    "assault_vehicle": lv((None, (F_AAT, 1.0)), (0, (F_AAT, 1.0)), (2, (X("raw_aat_cis"), 1.0)), (3, (F_SUPER, 1.0)),
                          (4, (F_CONFED, 1.0)), (5, (F_PERS, 1.0)), (7, (X("mow_umbaran_hovertank"), 1.0))),   # user 2026-11-09: blue-grey RaW AAT, Super Tank Mk I (TF) / Mk II (Confederate), Umbaran hover tank (MoW)
    # user 2026-11-09: DSD1 dwarf spider first, OG-9 last; Class I moved to 3 (the Protodeka went to the speeder line)
    "heavy_vehicle": lv((None, (F_DSD, 1.3)), (0, (F_DSD, 1.3)), (2, (X("rc_adsd"), 1.3)), (3, (X("raw_octuptarra"), 1.7)), (4, (F_OG9, 1.0))),   # 2026-11-09: DSD1, A-DSD (Republic Commando), Octuptarra, OG-9
    "super_heavy_vehicle": lv((None, (F_PROTO, 1.4))),
    # MTT, heavy MTT, droid troop carrier Mk II; Corporate Alliance troop hauler = BF2 MTT
    "armored_troop_transport": lv((None, (F_MTT, 1.0)), (1, (F_MTT, 1.0)), (3, (F_CISMTT, 1.0)), (4, (F_DTRANS, 1.0))),
    "heavy_armored_troop_transport": lv((None, (MTT, 1.15))),
    # HAG (BF2), Octuptarra artillery (C/A artillery), HAG-M, HAML
    "mobile_artillery": lv((None, (HAG, 1.0)), (0, (HAG, 1.0)), (1, (F_CAART, 1.0)), (3, (F_HAGM2, 1.0)), (4, (F_HAML, 1.0))),
    "mobile_anti_air": lv((None, (CISFT, 1.0)), (0, (CISFT, 1.0)), (1, (F_GAT, 1.0))),   # user 2026-11-09: GAT Mk I (camo), GAT Mk II (blue)
    # user 2026-11-09: STAP, advanced (blue) STAP, armed STAP (AdvESTAP), Protodeka
    "speeder": lv((None, (F_STAP, 1.5)), (0, (F_STAP, 1.5)), (1, (X("blue_stap"), 1.5)), (2, (F_ADVSTAP, 1.2)), (3, (F_PROTO, 1.0))),
}
IND = dict(REP, blaster_infantry=lv((None, (OLD, None))), stormtrooper=lv((None, (OLD, None))),
           light_vehicle=lv((None, (LANCE, 0.9)), (0, (LANCE, 0.9)), (1, (LANCE, 1.0)), (2, (LANCE, 1.05)), (3, (LANCE, 1.1)),
                            (4, (ATST, 1.0)), (5, (ATST, 1.15))),
           assault_vehicle=lv((None, (SABER, 1.0)), (0, (SABER, 1.0)), (2, (SABER, 1.15)), (4, (SABER, 1.2)), (7, (SABER, 1.3))),
           speeder=lv((None, (BIKE, 1.5))))   # x1.5: user 2026-11-08, speeders too small next to the tanks
FLT = dict(IND, blaster_infantry=lv((None, (FELU, None))), stormtrooper=lv((None, (FELU, None))), speeder=lv((None, (FELU, None))))

# ── planes: equipment -> model (Republic / Separatist); independents fly the Republic set ──
P = lambda n: B(n)
ARC, VWING, ETA, LAAT, YWING = P("rep_fly_arc170fighter"), P("rep_fly_vwing"), P("rep_fly_anakinstarfighter"), P("all_la_at_gunship"), P("all_fly_ywing")
VULT, TRI, HMP, MAF, BELB = P("cis_fly_droidfighter"), P("cis_fly_tridroidfighter"), P("cis_fly_droidgunship"), P("cis_fly_maf"), P("cis_fly_greviousfighter")
TIE, TIEB, TIEI, SHUT = P("imp_fly_tiefighter"), P("imp_fly_tiebomber"), P("imp_fly_tieinterceptor"), P("imp_fly_trooptrans")
V19, DELTA, THETA, ARCG = P("rep_fly_v19"), P("rep_fly_jedifighter"), P("imp_fly_shuttleproto"), P("arc_la_at_gunship")
NANTEX, SCARAB = P("cis_fly_geofighter"), P("cis_fly_scarab")
# FotR 2026-11-08: better LAAT/i, HMP, ARC-170, V-19 Torrent, BTL-B Y-wing
LAAT, HMP, ARC, V19, REPYWING = B("fotr_laat"), B("fotr_hmp"), B("fotr_arc170"), B("fotr_v19"), B("fotr_btlb")
# 2026-11-08 (user): the LAAT gunship companies (helicopter_brigade sprite, helicopter_equipment) fly the gunships
for _d, _m in ((REP, LAAT), (IND, LAAT), (FLT, LAAT), (CIS, HMP)):
    _d["helicopter_brigade"] = lv((None, (_m, 1.0)))
PLANES = {   # 2026-11-09 user, CIS: Sheathipede, Droch, HMP, C-9979 (+ heavy lander); I-Beam, Vulture, Vulture Mk II (RaW); Sabaoth, Hyena, strike bomber
    # equipment: (Republic, Separatist). Republic side unchanged; Separatist side one model per plane (2026-11-08, CIS names)
    "laat_equipment": (RM09, X("sheathipede")), "laati_equipment": (LAAT, X("sheathipede")),                         # CIS: HMP dropship / HMP gunship
    "maat_equipment": (LAAT, X("cis_maf")), "maat_gunship_equipment": (LAAT, X("cis_maf")),   # user 2026-11-09: heavy droid lander <-> Droch             # C-9979
    "idt_equipment": (TR_IDT, HMP), "idt_gunship_equipment": (TR_IDT, X("raw_hmp")),
    "tie-rp_equipment": (TR_THETA, X("c9979")), "tie-rp_gunship_equipment": (TR_THETA, X("c9979")),   # Droch-class: no model, TF lander
    "aal_equipment": (SHUT, X("droch")), "aal_gunship_equipment": (SHUT, X("droch")),               # heavy droid lander
    "torrent_equipment": (X("clone_z95"), X("ibeam")), "z-95_equipment": (V19, X("vulture")), "tie-rb_equipment": (ETA, X("trifighter")),   # clone Z-95 (2026-11-09, was the T-16), then the V-19
    "tie_fighter_equipment": (TIE, X("raw_vulture")), "tie-sf_equipment": (TIE, BELB), "v_wing_equipment": (DELTA, X("nantex")),
    "tie-in_equipment": (VWING, X("vulture_interceptor")), "tie-sk_equipment": (DELTA, SCARAB), "tie-vn_equipment": (TIEI, X("tie_droid")), "tie-ba_equipment": (TIE, SCARAB),
    "arc-170_equipment": (ARC, X("belb24")), "tie_defender_equipment": (TIEI, BELB),
    "y-wing_equipment": (REPYWING, X("sabaoth_bomber")), "skipray_equipment": (X("ntb630"), X("hyena")), "tie_bomber_equipment": (YWING, X("raw_hyena")),   # BTL-B, then the NTB-630 (2026-11-09, was the BTL-A4)
    "scimitar_equipment": (TIEB, X("raw_droidbomber")),
}
# fallbacks the engine may ask for: archetypes, subunits, sprites
PLANE_FALLBACK = {   # name: (Republic, Separatist)
    "imp_fighter_equipment": (VWING, VULT), "imp_defender_equipment": (ARC, BELB), "imp_interceptor_equipment": (ETA, TRI),
    "imp_bomber_equipment": (YWING, MAF), "imperial_transport_plane_equipment": (LAAT, HMP), "imp_gunship_equipment": (LAAT, HMP),
    "tie_fighter": (VWING, VULT), "tie_heavy_fighter": (ARC, BELB), "tie_interceptor": (ETA, TRI), "tie_bomber": (YWING, MAF),
    "space_transport": (LAAT, HMP), "tie_gunship": (LAAT, HMP),
    "light_plane": (VWING, VULT), "jet_plane": (ARC, BELB), "medium_plane": (YWING, MAF), "heavy_plane": (LAAT, HMP),
}

REP_TAGS, CIS_TAGS = ("REP", "ALD"), ("CIS", "CMG", "IBC", "TCU", "TDF", "XUC", "ZAL")
LAND = {**{t: REP for t in REP_TAGS}, **{t: CIS for t in CIS_TAGS}, "FLT": FLT, "western_european_gfx": IND, "african_gfx": IND}
AIR_SIDE = {**{t: 0 for t in REP_TAGS}, **{t: 1 for t in CIS_TAGS}, "FLT": 0, "western_european_gfx": 0, "african_gfx": 0}


# rifle in the trooper's hands per rifle visual level (attach names of units_infantry_REP / _old_republic): the clones
# otherwise all inherit the DC-15S. DC-15x stands in for the DC-17 (no DC-17m model). plans & scripts/weapon_models.py
RIFLES = {3: "DC15A", 4: "DC15", 5: "DC15X", 6: "E11"}
RIFLE_UNITS = {(t, u) for t in REP_TAGS for u in ("blaster_infantry", "stormtrooper")}
RIFLE_NODES = (("rifle1", "Right_Hand_node"), ("rifle2", "Left_Hand_node"), ("rifle3", "mid_back_node"), ("rifle4", "Root_node_2"))


def ent(name, model, scale=None, rifle=None):
    att = "".join(f' attach = {{ name = "{a}" {node} = "REP_infantry_weapon_{rifle}_entity" }}' for a, node in RIFLE_NODES) if rifle else ""
    return f'entity = {{ name = "{name}" clone = "{model}"' + (f" scale = {scale}" if scale else "") + att + " }"


def entities():
    out = ["# HOD: Executor-tree units -> our unit models (plans & scripts/sw_tree/unit_models_sw.py)"]
    for tag, table in LAND.items():
        for unit, levels in table.items():
            for level, (model, scale) in levels.items():
                if level is None and 1 in levels:
                    continue
                rifle = RIFLES.get(level) if (tag, unit) in RIFLE_UNITS else None
                # visual level 1 has no number: the game looks for TAG_unit_entity (vanilla: _0, plain, _2, _3 ...)
                out.append(ent(f"{tag}_{unit}_entity" if level in (None, 1) else f"{tag}_{unit}_{level}_entity", model, scale, rifle))
    for tag, side in AIR_SIDE.items():
        for name, models in {**PLANES, **PLANE_FALLBACK}.items():
            out.append(ent(f"{tag}_{name}_entity", models[side]))
    return out


def set_visual_levels():
    p = "common/units/equipment/hod_sw_zz_imperial_land_vehicle.txt"
    raw = open(p, "rb").read()
    s = raw.decode("utf-8-sig")
    for eq, level in VISUAL.items():
        s, n = re.subn(r"(\n\t%s\s*=\s*\{.*?visual_level\s*=\s*)\d+" % re.escape(eq), lambda m: m.group(1) + str(level), s, count=1, flags=re.S)
        assert n == 1, eq
    open(p, "wb").write((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + s.encode("utf-8"))


if __name__ == "__main__":
    set_visual_levels()
    lines = entities()
    assert len({re.search(r'name = "([^"]+)"', l).group(1) for l in lines[1:]}) == len(lines) - 1, "duplicate entity"
    open("gfx/entities/zz_hod_sw_unit_models.asset", "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(len(lines) - 1, "entities")
