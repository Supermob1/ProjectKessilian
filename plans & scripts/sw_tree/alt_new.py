"""Models the user kept on the alt_review page (2026-11-11), from FotR / Republic at War / Thrawn's Revenge.
Pure data, read by unit_models.py (SPECS hod_m_<key>, glb from _glb/alt_cand) and alt_models.py (picker pools).

KEEP: picker kind -> [(candidate key "<source>__<alo stem>", side)]; side r = Republic, c = Separatist, "" = any.
"""
import os, re

GLB = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../ProjectKessilianWIPGFX/ProjectKessilianWIP/3d/_glb/alt_cand"))

KEEP = {
    "imp_bomber_equipment": [("fotr__2warpod", "c"), ("fotr__z95_bomber", "r"), ("fotr__sabaoth_defender", "c"), ("fotr__scurrg_h-6_bomber", ""),
                             ("fotr__rv_ywing", "r"), ("raw__rev_ntb_630", "r"), ("raw__nv_sabaoth_bomber", "c"), ("tr__bwing_e", ""),
                             ("tr__rv_hwing", ""), ("tr__rv_kwing", ""), ("tr__scimitar", ""), ("tr__ev_xg1_starwing", ""), ("tr__ev_tiebomber", ""),
                             ("tr__gm_tieheavybomber", ""), ("tr__ev_tie_oppressor", ""), ("tr__ea_tiepunisher", ""), ("tr__tie_terror", "")],
    "imp_fighter_equipment": [("fotr__naboo_n1_starfighter", "r"), ("fotr__nv_r22", "r"), ("fotr__cis_scarab", "c"), ("fotr__ev_tiefighter", "r"),
                              ("raw__rev_z95", "r"), ("raw__csv_t-62_convor", "c"), ("raw__rev_delta7b_anakin", "r"), ("raw__sev_p38", "c"),
                              ("raw__rev_vwing", "r"), ("raw__sev_scarab", "c"), ("raw__nv_umbaran_fighter", "c"), ("raw__nv_z95_i3", ""),
                              ("tr__rv_chirdaki", ""), ("tr__gm_clutch", ""), ("tr__diewing", ""), ("tr__generic_drexl ii_starfighter", ""),
                              ("tr__clawcraft", ""), ("tr__ev_tie_droid", "c"), ("tr__ev_tietargetter", ""), ("tr__pv_tiehunter", ""),
                              ("tr__ev_tie_sentinel", ""), ("tr__x-tie", ""), ("tr__y-tie", ""), ("tr__z-tie", "")],
    "imp_interceptor_equipment": [("tr__rv_awing", ""), ("tr__t-wing_interceptor", ""), ("tr__tie_interceptor", ""), ("tr__ev_tieraptor", ""),
                                  ("tr__ev_181st_interceptor_new", ""), ("tr__x-ceptor", ""), ("tr__tie_x2", ""), ("tr__tie_avenger", ""),
                                  ("fotr__rep_aurek_mk2", "r")],
    "imp_defender_equipment": [("raw__rev_arc170_razor", "r"), ("tr__rv_ewing", ""), ("tr__ev_tie_aggressor", ""), ("tr__ev_tie_defender", "")],
    "imp_gunship_equipment": [("raw__rev_laat_1", "r"), ("tr__vt-49_decimator", "")],
    "dd": [("tr__surveyor-class_frigate", "")],
    "cl": [("fotr__gladiator_i-class_star_destroyer", "r"), ("fotr__spacearc", "r"), ("raw__sev_commerce_guild_light_cruiser", "c"),
           ("raw__rev_gladiator", "r"), ("raw__rev_arquitens_cruiser", "r"), ("tr__rv_assaultfrigate", ""), ("tr__pa_gladiator_ii", ""),
           ("tr__imperial_ii_frigate", ""), ("tr__ev_immobilizer418", ""), ("tr__ev_imperial_cargo_ship", ""), ("tr__rv_liberator", ""),
           ("tr__hap_olanji", ""), ("tr__eoth_ormos", "")],
    "ca": [("fotr__secutor_star_destroyer", "r"), ("fotr__tector_i-class_star_destroyer", "r"), ("raw__rev_rothana_destroyer", "r"),
           ("tr__eoth_ascendancy", ""), ("tr__interdictor-class_star_destroyer", ""), ("tr__rv_mc80b_star_cruiser", ""), ("tr__mc_baby_viscount", ""),
           ("tr__rv_mothma_star_destroyer", ""), ("tr__nebula-class_star_destroyer", ""), ("tr__republic_sd", ""), ("tr__mc90_star_cruiser", "")],
    "cv": [("fotr__venator_hero", "r"), ("tr__ton-falk-class_escort_carrier", ""), ("tr__endurance-class_fleet_carrier", ""), ("tr__hap_mist", ""),
           ("tr__praetor_carrier", "")],
    "bb": [("fotr__procurator-class_battlecruiser", "r"), ("fotr__recusant-class_dreadnaught", "c"), ("fotr__maelstrom-class_battlecruiser", "c"),
           ("tr__ev_tarlandia", ""), ("tr__allegiance-class_battlecruiser", ""), ("fotr__rep_praetorone", "r"), ("fotr__taggeco_battlecruiser", "r"),
           ("tr__nr_lusankya", ""), ("tr__assertor", ""), ("tr__ev_eclipse", ""), ("tr__ex-f", ""), ("tr__ev_bellator-class_star_destroyer", ""),
           ("tr__mandatoriii", ""), ("tr__praetor_ii", ""), ("tr__sorannan", ""), ("tr__fs_impellor", ""), ("tr__rv_mediator", ""),
           ("tr__ev_knighthammer", ""), ("tr__ev_sovereign", ""), ("tr__c-type_thrustship", ""), ("tr__ev_generic_vengeance", ""),
           ("tr__ev_hero_vengeance", ""), ("tr__mc_viscount", "")],
    "extra_light_equipment": [("fotr__ev_at-dp", "r"), ("tr__ev_at-st_a", ""), ("raw__nv_lance_walker", "r"), ("raw__rev_cpw", "r")],
    "light_equipment": [("fotr__rep_at-xt", "r"), ("tr__ev_atmp", ""), ("raw__nv_cll_m2", "c"), ("tr__swift_assault_5_hoverscout", ""),
                        ("tr__rv_t1a_hovertank", ""), ("tr__rv_t1b_hovertank", ""), ("tr__rv_t2b_hovertank", ""), ("raw__rev_stuntank", "r"),
                        ("tr__eoth_rfcat", "")],
    "speeder_equipment": [("fotr__rep_barc_speeder", "r"), ("tr__ev_barc_speeder", ""), ("tr__ev_64-y_swift_3_repulsorsled", ""),
                          ("tr__repulsor_scout", ""), ("fotr__rv_skyhopper", ""), ("tr__v-wing_airspeeder", ""), ("fotr__wook_fluttercraft", ""),
                          ("tr__eoth_airstraeker", "")],
    "assault_equipment": [("tr__century_tank", ""), ("tr__s-1_firehawke_heavy_repulsortank", ""), ("tr__rv_t3a_heavy_tank", ""),
                          ("tr__rv_t3b_heavy_tank", ""), ("tr__rv_t4b_heavy_tank", ""), ("fotr__hutt_wlo5", ""), ("fotr__rep_vaate", "r")],
    "heavy_equipment": [("tr__ev_tat-at", ""), ("tr__ev_c10_siegetower", "")],
    "mobile_art_equipment": [("tr__ev_spmag", "")],
    "mobile_aa_equipment": [("tr__ev_maat", "")],
    "troop_transport_equipment": [("raw__nv_a_a3_truck_m56_jan", "c")],
    "heavy_troop_transport_equipment": [("tr__b5_juggernaut", "")],
}
FOLDER = {"fotr": "fotr", "raw": "raw", "tr": "tr"}   # _glb/alt_cand/<source>/<alo stem>.glb
SIZE = {"imp_bomber_equipment": dict(length=3.6, plane=True), "imp_fighter_equipment": dict(length=3.2, plane=True),
        "imp_interceptor_equipment": dict(length=3.0, plane=True), "imp_defender_equipment": dict(length=3.4, plane=True),
        "imp_gunship_equipment": dict(length=4.5, plane=True), "dd": dict(length=6, plane=True), "cl": dict(length=7.5, plane=True),
        "ca": dict(length=10, plane=True), "cv": dict(length=11, plane=True), "bb": dict(length=13, plane=True),
        "extra_light_equipment": dict(height=5.5), "light_equipment": dict(length=5.5), "speeder_equipment": dict(length=3.0, hover=True),
        "assault_equipment": dict(length=6.5), "heavy_equipment": dict(height=9.5), "mobile_art_equipment": dict(length=7.0),
        "mobile_aa_equipment": dict(length=6.0, hover=True), "troop_transport_equipment": dict(length=6.0),
        "heavy_troop_transport_equipment": dict(length=8.0)}
HOVER = re.compile(r"hover|repulsor|speeder|skyhopper|airspeeder|flutter|airstraeker|swift|firehawke", re.I)


def model(key):
    """game model name for a candidate key"""
    return "hod_m_" + re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def specs(wip=None):
    """{model: unit_models.py SPECS entry}"""
    out = {}
    for kind, lst in KEEP.items():
        for key, _ in lst:
            src, stem = key.split("__", 1)
            spec = dict(src="%s/%s/%s.glb" % (GLB, FOLDER[src], stem), mode="glb_static",
                        tris=8000 if kind in ("dd", "cl", "ca", "cv", "bb") else 5000, tex_px=1024, **SIZE[kind])
            if HOVER.search(stem) and "plane" not in spec:
                spec["hover"] = True
            out[model(key)] = spec
    return out


assert len({k for lst in KEEP.values() for k, _ in lst}) == 143, "user kept 143 models"
