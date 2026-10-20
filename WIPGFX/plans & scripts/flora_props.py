"""Poly Haven (CC0) trees, shrubs and rocks as HOI4 map trees: each asset becomes `mapobject_<index>` in
gfx/entities/trees.gfx, drawn wherever map/trees.bmp holds that palette index (planet_terrain_gen.py paints them).
The tree renderer (gfx/FX/tree.shader) adds random heading, 0.75-1.25 height and terrain slope; it alpha-tests
the diffuse (clip at 0.5), so leaf cards keep their cut-out.

  python "WIPGFX/plans & scripts/flora_props.py" download     glTF 1k + leaf alpha maps -> WIPGFX/3d/polyhaven/<id>/
  python "WIPGFX/plans & scripts/flora_props.py" textures     DDS textures -> gfx/models/mapitems/hod_flora/
  blender -b --factory-startup --python "WIPGFX/plans & scripts/flora_props.py" -- meshes
  blender -b --factory-startup --python "WIPGFX/plans & scripts/flora_props.py" -- procedural
  python "WIPGFX/plans & scripts/flora_props.py" wire         gfx/entities/trees.gfx = vanilla entries + ours
  python "WIPGFX/plans & scripts/flora_props.py" planet_textures   only the PLANET_FOLIAGE textures + their atlases
  blender ... flora_props.py -- procedural 81 82 ...           only these PROCEDURAL indices (or kinds)
"""
import collections, glob, io, json, os, struct, sys

SRC = "WIPGFX/3d/polyhaven"
OUT = "gfx/models/mapitems/hod_flora"
VANILLA_TREES = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/entities/trees.gfx"
TEX_SIZE = 512          # trees are a few pixels tall on screen
LEAF_SHARE = 0.7        # share of the triangle budget for leaf cards
# trees.bmp index: (Poly Haven id, object name prefix to keep (None = all), triangle budget, largest extent in map units)
# (vanilla tree meshes: ~400-1300 tris, ~2.6 wide x 2 tall)
ASSETS = {
    42: ("quiver_tree_01", None, 1200, 2.4),                       # alien succulent tree: deserts, steppe
    43: ("quiver_tree_02", None, 900, 1.6),
    44: ("searsia_lucida", "searsia_lucida_a", 1200, 2.2),        # bushy shrub-tree: savanna, grassland
    45: ("othonna_cerarioides", "othonna_cerarioides_a", 1000, 1.6),  # desert succulent shrub
    46: ("fern_02", None, 600, 1.0),                               # jungle / swamp understory
    47: ("dead_tree_trunk_02", None, 500, 2.4),                    # fallen trunk: swamps, dead worlds
    48: ("moon_rock_01", "moon_rock_01_LOD0", 500, 1.8),           # bare rock: barren, lava, ice
    49: ("moon_rock_03", None, 500, 1.4),
    50: ("namaqualand_boulder_02", None, 600, 2.2),                # desert boulder
    51: ("rock_moss_set_01", "rock_moss_set_01_rock01", 500, 1.8), # mossy rock: forests, alpine
    52: ("boulder_01", None, 600, 1.6),                            # grey boulder: alpine, steppe
}
# built in Blender by procedural(): photo-scanned giants don't survive a 2k-triangle budget (trunks shred, canopies
# turn to confetti), so these are modelled the game way: simple trunk + canopy clumps of leaf cards.
PROCEDURAL = {
    40: "wroshyr",        # Kashyyyk giant: tall straight trunk, buttress roots, layered canopy platforms
    41: "jungle_giant",   # umbrella canopy on a short thick trunk
    55: "homestead",      # desert homestead: adobe domes + a small vaporator
    # Felucia: a fungal jungle in saturated colours (Star Wars Databank: "immense primitive plants", "enormous pitcher
    # plants and leafy growths", "colour-saturated"; Wookieepedia: giant purple mushrooms form the upper canopy, many
    # life-forms are translucent and colour the sunlight). Bigger than any tree: they tower over the jungle
    58: "fel_mushroom",   # giant purple mushroom: tall pale stalk, broad violet cap, small ones at its foot
    59: "fel_bulbs",      # translucent orange / yellow stalks with bulbous heads (Revenge of the Sith)
    60: "fel_pitcher",    # giant teal pitcher plant with a magenta lip
    61: "fel_fronds",     # giant curling crimson fronds
    # Raxus Secundus (The Clone Wars: Raxulon's parks and avenues): tall straight red-brown trunks branching high
    # into dense rounded crowns of golden-orange leaves, smaller ones with their leaves in stacked puffs, and
    # crimson shrubs beneath
    62: "rax_tree",       # tall tree, broad golden crown
    63: "rax_tiered",     # slimmer tree, stacked orange puffs
    64: "rax_shrubs",     # crimson shrubs
    # Raxus Prime, the galaxy's dump: heaps of junk wider than a trees.bmp cell, so neighbouring heaps run together
    # into one carpet of scrap: a mound of packed junk (the terrain's junk tile) bristling with hull plates, girders,
    # pipes and drums
    73: "rp_heap_a",      # broad low mound
    74: "rp_heap_b",      # tall cone
    75: "rp_heap_c",      # mound with a big hull plate and a drum stack
    76: "rp_heap_ridge",  # long ridge of junk (walls of the dump's maze)
    77: "rp_heap_tangle", # tangle of girders and pipes over a low spread
    78: "rp_heap_slabs",  # hull slabs leaning on each other
    # Korriban (korriban_research.md): the mountains a field of razor-sharp red spires (Moraband, The Clone Wars),
    # the valley floors strewn with the ruins of the Sith (broken columns, fallen statues, rubble)
    79: "kor_spires",     # a cluster of needle spires
    80: "kor_ruins",      # broken columns and a fallen statue
    # Dromund Kaas (Legends; TOR stills "Jungle Valley", "Dark Temple pass", concept art): "massive, dark-wooded
    # trees grew in the swampy water, forming canyon-like groupings of foliage covered in vines"; gnarled trunks,
    # crooked sprawling limbs, dense rounded dark crowns; dead snags and root tangles in the marsh
    81: "dk_swamp_tree",  # massive gnarled tree, flared roots, sprawling crooked limbs, broad dark crown
    82: "dk_jungle_tree", # tall broadleaf tree, dense rounded crown (the northern storm jungle)
    83: "dk_dead_snag",   # dead broken-topped trunk with bare crooked limbs and a few moss clumps
    84: "dk_root_tangle", # arching roots over the water, ferns between them
    85: "dk_reeds",       # low clumps of marsh growth at the water's edge
    # Zygerria (The Clone Wars "Slaves of the Republic": olive grass on the airy plains; forests are a design
    # choice of the user's): small copses of dry-country trees and shrubs in dusty olive
    86: "zyg_tree",       # spreading flat-crowned tree
    87: "zyg_shrubs",     # low shrub clumps
    # Cantonica (canon: Cantonican cactus, Chinar tree (Rules of the Game; the Databank still shows chinars as
    # cloud-pruned trees: a crooked trunk, flat dark pads of foliage on the branch ends); green scrub on the shore
    # (comic still); the ancient ruins are Sith (the user's design choice, 2026-10-14)
    88: "canto_chinar",   # cloud-pruned tree: crooked trunk, flat dark-green pads
    89: "canto_cactus",   # a stand of ribbed column cacti, some with arms, and barrel cacti
    90: "canto_scrub",    # low grey-green scrub of the sea shore
    91: "canto_rubble",   # Sith ruins in the sand: a broken obelisk, tilted pylon blocks, scattered blocks
    # Bonadan (Legends: a polluted industrial world, its topsoil destroyed by "constant drilling and construction",
    # plant life killed by "careless mining operations"): no flora, the wastes strewn with industry instead
    92: "bon_derrick",    # a drilling rig: a tapering lattice tower over a pump house, pipes running off
    93: "bon_tanks",      # a cluster of storage tanks joined by pipework
    94: "bon_slag",       # spoil and slag heaps dumped by the mines
    95: "bon_stacks",     # a pair of smokestacks over a small works
    # Etti IV (canon: forests, burnt by Cybot Galactica to expand the Arcoplex; Legends: hot, stormy plains and
    # shallow seas)
    96: "etti_tree",      # tall broadleaf forest tree, a broad layered crown
    97: "etti_burnt",     # charred snags and stumps of the burnt forest
    98: "etti_grass",     # tall dry grass and shrub clumps of the hot plains
    99: "etti_reeds",     # reed beds in the shallow seas
    # Ruuria (Legends: a warm and humid jungle world; canon: pink rivers): jungle giants, tree ferns, the wild cocoon
    # clusters of the Ruurians' metamorphosis (design choice), pinkish reeds along the rivers
    100: "ruu_tree",      # jungle giant: tall trunk, umbrella canopy
    101: "ruu_fern",      # tree ferns
    102: "ruu_cocoons",   # silk cocoons hung in a low thicket
    103: "ruu_reeds",     # reeds at the pink rivers' edges
    # Ossus (canon flora: bamboo, the Uneti tree; Legends: the wodobo bush; ruins everywhere since the Cron Supernova)
    104: "oss_bamboo",    # a stand of tall bamboo culms with leafy tops
    105: "oss_uneti",     # an uneti tree: thick gnarled trunk, broad spreading crown
    106: "oss_wodobo",    # wodobo bushes
    107: "oss_rubble",    # ruin rubble in the grass: a broken column, a dome shard, blocks
    # Lola Sayu (canon: volcanic, caves, crevasses, no plant or animal life): vents and basalt shards, nothing alive
    108: "lola_vent",     # volcanic vent cones, cratered tops
    109: "lola_shards",   # jagged basalt shards thrust up from the cracked crust
    # Ringo Vinda (the surface after the Cato Neimoidia concept art: banded rock pillars and arches; temperate design)
    110: "rv_pillars",    # a cluster of banded rock pillars
    111: "rv_arch",       # a small natural rock arch
    112: "rv_tree",       # a temperate broadleaf tree, a tall rounded crown
    # Rhen Var (Legends: once "a fertile paradise", now frozen tundra, glaciers and snowy mountains over the ruins)
    113: "rh_ice",        # ice spikes and shards pushed up by the frost
    114: "rh_ruin",       # a snow-buried fragment of the old civilization: a column stump, a wall corner
    115: "rh_deadtree",   # a dead tree from the fertile age, frozen standing
    # Mon Cala (canon: coral reefs in the light of the twin suns, island chains of rocky cliffs, beaches and dense jungle)
    116: "mcl_coral",     # coral heads breaking the surface of the reefs: staghorn branches round brain-coral domes
    117: "mcl_palm",      # island palms: leaning ringed trunks, frond crowns
    118: "mcl_seastack",  # sea stacks: wave-cut rock pillars standing out of the water
    # Iego (canon: basaltic spires and canyons where the reeksa grow; Legends: the bone piles of the Boneyard)
    119: "ieg_reeksa",    # reeksa: thick thorned stalks curling up into toothed maws
    120: "ieg_basalt",    # a cluster of hexagonal basalt columns
    121: "ieg_bones",     # a giant's bones half sunk in the sand: rib arches and a skull
    # Lianna (Legends: temperate and dry, urban and plains; Sienar's industrial world)
    122: "lia_tree",      # a dry-country umbrella tree: a leaning trunk, a flat spreading crown
    123: "lia_grass",     # dry grass tussocks
    124: "lia_pylon",     # power pylons and comm masts round Sienar's plants
    # Jabiim (Legends: a rain-soaked world of mud plains; grasses, trees and bamboo)
    125: "jab_tree",      # a rain-soaked broadleaf: a dark trunk, a heavy drooping crown
    126: "jab_marsh",     # tall wet marsh grass
    127: "jab_bamboo",    # a dense stand of dark bamboo
    # Saleucami (canon: greater cake trees, towering bith; wetlands; Legends: oases of plant growth on an arid world)
    128: "sal_caketree",  # a greater cake tree: a tall bare trunk carrying stacked flat round tiers of foliage
    129: "sal_bith",      # towering bith: giant ribbed fungal spires in a cluster
    130: "sal_reeds",     # wetland reeds
    # Telos (canon: the Ithorians "planted the short, thorny blba trees and the exotic bachani flowering plant";
    # "fields of blue and lavender flowers")
    131: "tel_blba",      # a short thorny blba tree: a squat twisted trunk, thorny limbs, a low broad crown
    132: "tel_bachani",   # bachani flowers: a bed of blue and lavender blooms on short stems
    # Serenno: old forests in autumn gold (Tales of the Jedi), dark pines on the heights
    133: "ser_tree",      # a tall broadleaf, a high rounded golden crown
    134: "ser_pine",      # a dark conifer: a straight trunk, tiers narrowing to a point
    # Yavin IV: jungle of purple-barked Massassi trees, ferns, overgrown temple rubble
    135: "yav_massassi",  # a Massassi tree: a tall purple trunk on buttress roots, a high spreading canopy
    136: "yav_fern",      # climbing ferns and undergrowth
    137: "yav_ruin",      # Massassi rubble overgrown with vines: stepped blocks, a toppled pillar
    # Celanon: temperate forests and plains round the trade cities
    138: "cel_tree",      # a tall columnar tree, a narrow crown along most of the trunk
    139: "cel_grass",     # tall plains grass in golden tussocks
    # Botajef: the industrial world
    140: "bot_tanks",     # a tank farm: squat storage tanks, a tall one, a pipe run between them
    # Axxila: the ore world
    141: "axx_spoil",     # ore spoil heaps round a drill rig
    # Ciutric IV: industry among forests
    142: "cit_tree",      # a broad dark-crowned forest tree on a thick trunk
    # Ord Cestus: red desert; the fungus farms (Legends: it exported fungi)
    143: "ces_fungus",    # cultivated fungus stalks with broad caps
    144: "ces_spike",     # a cluster of red rock spikes
    # Dathomir: dark swamp forests under a red sky, rock spires
    145: "dat_tree",      # a gnarled dark tree, crooked limbs, sparse blood-red crowns
    146: "dat_fern",      # swamp ferns and undergrowth
    147: "dat_rock",      # crooked rock spires
    # Mandalore: veshok forests in the north (Legends), the white glassy wastes (canon)
    148: "man_veshok",    # a veshok tree: a tall straight trunk, a high oval crown
    149: "man_crystal",   # white glassy shards of the wastes
    # Concordia (canon: the torrent wisp tree), Taris (canon: three-fingered vines and slime-slick fungus in Talinn),
    # Wayland (forests and jungles)
    150: "con_wisp",      # a torrent wisp tree: a tall slim trunk, wispy foliage hanging in long streamers
    151: "tar_vines",     # vine tangles and fungus over rubble and walls
    152: "way_tree",      # a big old temperate tree, a broad high crown
    153: "way_fern",      # jungle undergrowth and ferns
    # Bracca (canon: rocky plains and junkyards, "kinda like raxus prime"), Trandosha (Legends: jungles, savannahs, deserts)
    154: "bra_scrap",     # a scrap heap: hull plates, girders and a broken engine cone piled together
    155: "bra_rock",      # weathered boulders of the rocky plains
    156: "tra_jungle",    # a jungle giant: a tall trunk on buttress roots, a broad dark canopy
    157: "tra_thorn",     # a savannah thorn tree: a crooked trunk, a flat wide crown, grass round it
    158: "tra_spine",     # desert spine plants: tall ribbed columns with thorny crowns
    # Nyriaan (Legends: tropical plains and boggy valleys; Meadlin's tree, mire nettle), Corsin (tropical islands)
    159: "nyr_meadlin",   # a Meadlin's tree: a pale trunk forking into spreading limbs, round tufted crowns
    160: "nyr_nettle",    # mire nettles: spiky clumps standing in the wet
    161: "crs_palm",      # a tropical palm: a curved ringed trunk, a crown of long fronds
    162: "crs_shrub",     # flowering tropical shrubs
    # Kashyyyk (canon: wroshyr forests - flora 40 is the wroshyr giant -, kshyy-vines, the cursed Black Forest)
    163: "kas_vine",      # kshyy-vine tangles and ferns of the forest floor
    164: "kas_black",     # a twisted black tree of the Black Forest, hung with web
    # Onderon (canon: a temperate jungle; palm trees, skeleton weed, Hutt's tongue)
    165: "ond_broadleaf", # a jungle giant: a pale trunk, a broad high canopy, hanging fronds
    166: "ond_weed",      # skeleton weed and blue Hutt's-tongue undergrowth
    # Umbara (canon: bioluminescent carnivorous plants; the user's references 2026-10-19: SWTOR's Umbara, the
    # Galactic Contention Umbara art): near-black growths lit by bright magenta and red (the map is always day:
    # the glow is painted into the textures, not emitted)
    167: "umb_flamestalk",  # tall thin black stalks tipped with red flame-blade leaves
    168: "umb_pod",       # undergrowth: black pods studded with red glowing spots, curled pink-glowing tendrils, blue grass
    169: "umb_mushroom",  # a mushroom tree: a black trunk and bulbous cap studded with red-orange glowing spots
    # Colla IV (Legends: the tropical Colicoid spawnworld)
    170: "col_tree",      # a broad tropical tree
    171: "col_mound",     # a Colicoid hive mound: a ribbed earthen spire
    172: "col_eggs",      # egg clusters in the spawning swamps
    173: "umb_tentacle",  # tentacle trees: huge black tentacles arching over, a ribbed magenta glow strip inside
    # Ruusan (Legends: once temperate with rivers and forests, burnt to desert in the New Sith Wars; low scented bushes;
    # the user, 2026-10-19: the scarred valley inside a healed green planet)
    174: "rus_tree",      # a healed broadleaf: a straight pale trunk, a round golden-green crown
    175: "rus_scrub",     # the low scented bushes, flowering lilac
    176: "rus_scorched",  # the valley's scorched snags and stumps among pale fallen stones
    177: "boz_headstone", # Boz Pity: a cluster of elaborate Gargantelle headstones, stelae and grave markers
    178: "boz_bones",     # half-buried giant bones: ribs arching out of the sand, a long thigh bone
    179: "boz_grass",     # dry grass tufts of the grassy fields
    180: "boz_rock",      # weathered boulders of the rocky fields
    # Mandalore (Legends): tall galek trees with silver leaves, golden amber ferns in their groves, the tropics' varos
    181: "man_galek",     # a tall slender galek: a pale trunk, tiers of silver-leaved crown
    182: "man_amberfern", # golden amber ferns, low and spreading
    183: "man_varos",     # a varos tree of the southern jungle: a leaning trunk, a broad dark umbrella crown
    # Ithor (the user: herdships over a sea of clouds; Legends: the Mother Jungle below; canon: n'lor trees, blue and
    # pink fungi)
    184: "ith_cloud",     # a billowing cloud bank: soft white lumps heaped together
    185: "ith_nlor",      # a dense n'lor jungle tree: a tall trunk, stacked dark crowns
    186: "ith_barge",     # a small Ithorian herd barge floating over the clouds: a garden-topped lens hull
    187: "ith_fungus",    # a carpet of blue and pink fungus caps
    # Ord Mantell (Legends: forests in the temperate and tropical regions, fjords at the poles; arid equatorial plains)
    188: "om_pine",       # a conifer of the foothills and western forests
    189: "om_scrub",      # dry scrub of the arid plains
    # Garqi (Legends: "natural elements in Garqi's crust gave the native plant life a purple coloration"; bimiza trees;
    # canon: caf)
    190: "gar_bimiza",    # a bimiza tree: a straight trunk, a broad purple crown
    191: "gar_shrub",     # purple native shrubs
    192: "gar_caf",       # caf bushes planted in rows
    # Agamar (Legends: binka trees "grew regularly spaced"; natural bridges; mugruebe ranches)
    193: "aga_binka",     # a stand of binka trees in regular rows: straight trunks, round crowns
    194: "aga_arch",      # a natural stone bridge: a weathered arch between two rock piers
    195: "aga_grass",     # dry golden ranch grass
    # Ord Trasi (Legends: cool and arid, mountains and plains)
    196: "ot_scrub",      # grey cold-desert scrub
    # Dantooine (canon and Legends: grasslands dotted with blba trees; KOTOR's pastel plains)
    197: "dan_blba",      # a Dantooine blba: a tall slender trunk, a broad flat crown
    198: "dan_grass",     # tall pastel grass in tufts
    199: "dub_tree",      # Dubrillion: a lush broadleaf of its green continents
    200: "kal_moss",      # Kalee: moss-covered rock spires of the canyon country
    201: "kal_jungle",    # Kalee: a rainforest tree of the Kunbal, dark broad crown
    202: "muun_tree",     # Muunilinst: a tall slender tree, blue-green crown
    203: "muun_smoker",   # Muunilinst: a "smoker", a conical vent volcano in the shallows, glowing at its mouth
    204: "bas_tree",      # Bastion: a temperate broadleaf of the hills
    205: "myg_spur",      # Mygeeto: crystal spurs breaking out of the ice, glowing at their points
    206: "yag_tree",      # Yaga Minor: a tall temperate tree of the Yagai forests
    207: "yag_rock",      # Yaga Minor: mossy boulders round cave mouths
    208: "ans_sanwi",     # Ansion: a sanwiwood tree of the Niruu Plateau, a broad spreading crown
    209: "ans_grass",     # Ansion: tall plains grass in tufts with chawix flowers
    210: "ilu_shard",     # Ilum: ice and crystal shards breaking out of the snow
    211: "ilu_pine",      # Ilum: a frosted conifer of its rare forests, tiered and snow-laden
    212: "dor_kand",      # Dorin: a kand tree, a fruit tree of the orchards with a dense round crown
    213: "dor_stone",     # Dorin: dark standing stone pillars
    214: "yin_spire",     # Yinchorr: weathered rock needles of the rocky deserts, banded ochre
    215: "yin_thorn",     # Yinchorr: a low thorn tree of the oases and the coast, flat dusty crown
    216: "cha_sienta",    # Chandrila: a sienta tree of the Hanna Wild Game Reserve, tall and full-crowned
    217: "cha_balm",      # Chandrila: balmgrass tufts of the rolling plains
    218: "cor_bamboo",    # Corulag: a stand of tall Corulag bamboo
    219: "ark_ice",       # Arkania: ice and diamond-bright crags breaking out of the tundra
    220: "anx_red",       # Anaxes: a giant red flower (canon: tall red plant-like life), ribbed stalk, wide-open bloom
    221: "anx_bloom",     # Anaxes: a clump of lesser red flowers, cupped blooms nodding on curved stalks
    222: "ess_palm",      # Esseles: a tropical palm of Nurrale's coast
}
PROC_MATS = {40: ["hod_dead_tree_trunk_02", "hod_foliage_wroshyr"], 41: ["hod_dead_tree_trunk_02", "hod_foliage_jungle"],
             55: ["hod_adobe"], 58: ["hod_fel_stalk", "hod_fel_cap"], 59: ["hod_fel_bulb"], 60: ["hod_fel_pitcher"],
             61: ["hod_fel_frond"], 62: ["hod_rax_trunk", "hod_foliage_raxus"], 63: ["hod_rax_trunk", "hod_foliage_raxus"],
             64: ["hod_foliage_crimson"], 73: ["hod_scrap_tile", "hod_scrap_metal"],
             74: ["hod_scrap_tile", "hod_scrap_metal"], 75: ["hod_scrap_tile", "hod_scrap_metal"]}
# the heaps are built like the trees: a body plus clumps of cut-out cards (junk pieces on transparent ground)
PROC_MATS.update({i: ["hod_scrap_tile", "hod_scrap_metal", "hod_junk_clump"] for i in range(73, 79)})
PROC_MATS.update({79: ["hod_kor_rock"], 80: ["hod_kor_rock", "hod_kor_stone"]})
PROC_MATS.update({81: ["hod_dead_tree_trunk_02", "hod_foliage_dk"], 82: ["hod_dead_tree_trunk_02", "hod_foliage_dk"],
                  83: ["hod_dead_tree_trunk_02", "hod_foliage_dk"], 84: ["hod_dead_tree_trunk_02", "hod_foliage_dk"],
                  85: ["hod_foliage_dk"], 86: ["hod_dead_tree_trunk_02", "hod_foliage_zyg"], 87: ["hod_foliage_zyg"]})
PROC_MATS.update({88: ["hod_dead_tree_trunk_02", "hod_foliage_canto"], 89: ["hod_canto_cactus"],
                  90: ["hod_foliage_canto_scrub"], 91: ["hod_canto_sandstone"]})
PROC_MATS.update({92: ["hod_bon_metal"], 93: ["hod_bon_metal"], 94: ["hod_bon_slag"], 95: ["hod_bon_metal"]})
PROC_MATS.update({96: ["hod_dead_tree_trunk_02", "hod_foliage_etti"], 97: ["hod_etti_char"],
                  98: ["hod_foliage_etti_dry"], 99: ["hod_foliage_etti_reed"]})
PROC_MATS.update({100: ["hod_dead_tree_trunk_02", "hod_foliage_ruu"], 101: ["hod_dead_tree_trunk_02", "hod_foliage_ruu_fern"],
                  102: ["hod_ruu_silk", "hod_foliage_ruu"], 103: ["hod_foliage_ruu_reed"]})
PROC_MATS.update({104: ["hod_oss_bamboo", "hod_foliage_oss_bamboo"], 105: ["hod_dead_tree_trunk_02", "hod_foliage_oss_uneti"],
                  106: ["hod_foliage_oss_wodobo"], 107: ["hod_oss_stone"]})
PROC_MATS.update({108: ["hod_lola_basalt"], 109: ["hod_lola_basalt"]})
PROC_MATS.update({110: ["hod_rv_rock"], 111: ["hod_rv_rock"], 112: ["hod_dead_tree_trunk_02", "hod_foliage_rv"]})
PROC_MATS.update({113: ["hod_rh_ice"], 114: ["hod_rh_stone"], 115: ["hod_dead_tree_trunk_02"]})
PROC_MATS.update({128: ["hod_dead_tree_trunk_02", "hod_foliage_sal"], 129: ["hod_sal_bith"], 130: ["hod_foliage_sal_reed"]})
PROC_MATS.update({131: ["hod_dead_tree_trunk_02", "hod_foliage_tel"], 132: ["hod_foliage_tel_bachani"]})
PROC_MATS.update({133: ["hod_dead_tree_trunk_02", "hod_foliage_ser"], 134: ["hod_dead_tree_trunk_02", "hod_foliage_ser_pine"],
                  135: ["hod_yav_bark", "hod_foliage_yav"], 136: ["hod_dead_tree_trunk_02", "hod_foliage_yav_fern"],
                  137: ["hod_yav_stone", "hod_foliage_yav"]})
PROC_MATS.update({138: ["hod_dead_tree_trunk_02", "hod_foliage_cel"], 139: ["hod_foliage_cel_grass"],
                  140: ["hod_bot_steel"]})
PROC_MATS.update({141: ["hod_axx_ore", "hod_bot_steel"], 142: ["hod_dead_tree_trunk_02", "hod_foliage_cit"]})
PROC_MATS.update({163: ["hod_foliage_kas_vine"], 164: ["hod_kas_blackbark", "hod_foliage_kas_web"],
                  165: ["hod_dead_tree_trunk_02", "hod_foliage_ond"], 166: ["hod_foliage_ond_weed"],
                  167: ["hod_umb_black", "hod_umb_red"],
                  168: ["hod_umb_black", "hod_umb_red", "hod_umb_pink", "hod_foliage_umb_grass"],
                  169: ["hod_umb_black", "hod_umb_red"], 170: ["hod_dead_tree_trunk_02", "hod_foliage_col"],
                  171: ["hod_col_mound"], 172: ["hod_col_egg", "hod_foliage_col"],
                  173: ["hod_umb_black", "hod_umb_pink"],
                  174: ["hod_dead_tree_trunk_02", "hod_foliage_rus"], 175: ["hod_foliage_rus_scrub"],
                  176: ["hod_etti_char", "hod_rus_stone"],
                  177: ["hod_boz_stone", "hod_boz_bone"], 178: ["hod_boz_bone"], 179: ["hod_foliage_boz_grass"],
                  180: ["hod_boz_rock"], 181: ["hod_dead_tree_trunk_02", "hod_foliage_man_galek"],
                  182: ["hod_foliage_man_fern"], 183: ["hod_dead_tree_trunk_02", "hod_foliage_man_varos"],
                  184: ["hod_ith_cloud"], 185: ["hod_dead_tree_trunk_02", "hod_foliage_ith"],
                  186: ["hod_ith_hull", "hod_foliage_ith"], 187: ["hod_ith_fungus_blue", "hod_ith_fungus_pink"],
                  188: ["hod_dead_tree_trunk_02", "hod_foliage_om_pine"], 189: ["hod_foliage_om_scrub"],
                  190: ["hod_dead_tree_trunk_02", "hod_foliage_gar"], 191: ["hod_foliage_gar_shrub"],
                  192: ["hod_foliage_gar_caf"],
                  193: ["hod_dead_tree_trunk_02", "hod_foliage_aga_binka"], 194: ["hod_aga_stone"],
                  195: ["hod_foliage_aga_grass"], 196: ["hod_foliage_ot_scrub"],
                  197: ["hod_dead_tree_trunk_02", "hod_foliage_dan"], 198: ["hod_foliage_dan_grass"],
                  199: ["hod_dead_tree_trunk_02", "hod_foliage_dub"], 200: ["hod_kal_rock", "hod_kal_moss"],
                  201: ["hod_dead_tree_trunk_02", "hod_foliage_kal"], 202: ["hod_dead_tree_trunk_02", "hod_foliage_muun"],
                  203: ["hod_muun_rock", "hod_muun_lava"], 204: ["hod_dead_tree_trunk_02", "hod_foliage_bas"],
                  205: ["hod_myg_ice", "hod_myg_glow"], 206: ["hod_dead_tree_trunk_02", "hod_foliage_yag"],
                  207: ["hod_yag_rock", "hod_yag_moss"], 208: ["hod_dead_tree_trunk_02", "hod_foliage_ans"], 209: ["hod_foliage_ans_grass"],
                  210: ["hod_ilu_ice", "hod_ilu_glow"], 211: ["hod_dead_tree_trunk_02", "hod_foliage_ilu"],
                  212: ["hod_dead_tree_trunk_02", "hod_foliage_dor"], 213: ["hod_dor_stone", "hod_dor_moss"],
                  214: ["hod_yin_rock", "hod_yin_ochre"], 215: ["hod_dead_tree_trunk_02", "hod_foliage_yin"],
                  216: ["hod_dead_tree_trunk_02", "hod_foliage_cha"], 217: ["hod_foliage_cha_balm"],
                  218: ["hod_cor_cane", "hod_foliage_cor"], 219: ["hod_ark_ice", "hod_ark_glint"],
                  220: ["hod_anx_stalk", "hod_anx_crown"], 221: ["hod_anx_stalk", "hod_anx_crown"],
                  222: ["hod_dead_tree_trunk_02", "hod_foliage_ess"]})
PROC_MATS.update({159: ["hod_dead_tree_trunk_02", "hod_foliage_nyr"], 160: ["hod_foliage_nyr_nettle"],
                  161: ["hod_crs_palm", "hod_foliage_crs_palm"], 162: ["hod_foliage_crs_shrub"]})
PROC_MATS.update({154: ["hod_bra_scrap", "hod_bra_rust"], 155: ["hod_bra_rock"],
                  156: ["hod_dead_tree_trunk_02", "hod_foliage_tra"], 157: ["hod_dead_tree_trunk_02", "hod_foliage_tra_dry"],
                  158: ["hod_tra_spine"]})
PROC_MATS.update({150: ["hod_dead_tree_trunk_02", "hod_foliage_con"], 151: ["hod_tar_rubble", "hod_foliage_tar"],
                  152: ["hod_dead_tree_trunk_02", "hod_foliage_way"], 153: ["hod_foliage_way_fern"]})
PROC_MATS.update({143: ["hod_ces_stalk", "hod_ces_cap"], 144: ["hod_ces_rock"],
                  145: ["hod_dead_tree_trunk_02", "hod_foliage_dat"], 146: ["hod_foliage_dat_fern"], 147: ["hod_dat_rock"],
                  148: ["hod_dead_tree_trunk_02", "hod_foliage_man"], 149: ["hod_man_glass"]})
PROC_MATS.update({125: ["hod_dead_tree_trunk_02", "hod_foliage_jab"], 126: ["hod_foliage_jab_marsh"],
                  127: ["hod_jab_bamboo", "hod_foliage_jab_bamboo"]})
PROC_MATS.update({122: ["hod_dead_tree_trunk_02", "hod_foliage_lia"], 123: ["hod_foliage_lia_dry"], 124: ["hod_lia_metal"]})
PROC_MATS.update({119: ["hod_ieg_reeksa"], 120: ["hod_ieg_basalt"], 121: ["hod_ieg_bone"]})
PROC_MATS.update({116: ["hod_mcl_coral"], 117: ["hod_dead_tree_trunk_02", "hod_foliage_mcl_palm"], 118: ["hod_mcl_rock"]})
# Sketchfab models converted by sketchfab_props.py (meshes land in OUT as hod_flora_<index>_<name>.mesh)
EXTERNAL = {53: "sandcrawler", 54: "vaporators", 56: "wreck_harrower", 57: "wreck_foray"}
# Raxus Prime junk (sketchfab_props.py SPECS rp_*: Battlefront II / Empire at War models)
EXTERNAL.update({65: "rp_wreck_bloodmark", 66: "rp_wreck_chela", 67: "rp_wreck_b28", 68: "rp_wreck_ebonhawk",
                 69: "rp_junk_heap", 70: "rp_barrels", 71: "rp_hull_chunk", 72: "rp_wing_chunk"})
LEAF_SRC = "island_tree_01"  # Poly Haven leaf sheet the foliage clumps are composed from


# foliage for the planet floras below (made by planet_textures, not textures: the other textures stay untouched)
PLANET_FOLIAGE = {"hod_foliage_dk": ((70, 120, 100), (40, 80, 75)),      # Dromund Kaas: dark teal-green (TOR stills)
                  "hod_foliage_zyg": ((165, 160, 85), (125, 125, 65)),   # Zygerria: dusty olive (TCW plains)
                  "hod_foliage_canto": ((70, 105, 70), (45, 80, 55)),    # Cantonica: the chinar pads, dark green
                  "hod_foliage_canto_scrub": ((130, 150, 95), (100, 125, 80))}   # the shore scrub, grey-green
# solid (no alpha cut) textures of the planet floras: name -> (base rgb, pattern), painted by planet_textures
PLANET_SOLID = {"hod_canto_cactus": ((92, 128, 84), "ribs"), "hod_canto_sandstone": ((196, 164, 118), "blocks"),
                "hod_bon_metal": ((150, 128, 98), "plates"), "hod_bon_slag": ((96, 70, 52), "slag"),
                "hod_etti_char": ((44, 38, 34), "slag"), "hod_ruu_silk": ((226, 220, 200), "slag"),
                "hod_oss_bamboo": ((150, 158, 82), "ribs"), "hod_oss_stone": ((200, 190, 166), "blocks"),
                "hod_lola_basalt": ((58, 52, 54), "slag"), "hod_rv_rock": ((190, 162, 128), "blocks"),
                "hod_rh_ice": ((176, 214, 236), "slag"), "hod_rh_stone": ((150, 158, 168), "blocks"),
                "hod_mcl_coral": ((226, 122, 104), "slag"), "hod_mcl_rock": ((128, 122, 112), "blocks"),
                "hod_ieg_reeksa": ((92, 120, 62), "ribs"), "hod_ieg_basalt": ((62, 60, 62), "blocks"),
                "hod_ieg_bone": ((222, 212, 186), "slag"), "hod_lia_metal": ((168, 170, 176), "plates"),
                "hod_jab_bamboo": ((92, 104, 62), "ribs"), "hod_sal_bith": ((196, 150, 118), "ribs"),
                "hod_yav_bark": ((112, 72, 120), "ribs"), "hod_yav_stone": ((120, 116, 108), "blocks"),
                "hod_bot_steel": ((150, 140, 124), "plates"), "hod_axx_ore": ((132, 92, 62), "slag"),
                "hod_ces_stalk": ((212, 196, 170), "ribs"), "hod_ces_cap": ((150, 96, 132), "slag"),
                "hod_ces_rock": ((150, 74, 52), "blocks"), "hod_dat_rock": ((74, 62, 64), "blocks"),
                "hod_man_glass": ((226, 226, 218), "slag"), "hod_tar_rubble": ((128, 124, 118), "blocks"),
                "hod_bra_scrap": ((132, 126, 118), "plates"), "hod_bra_rust": ((128, 72, 40), "slag"),
                "hod_bra_rock": ((126, 112, 98), "blocks"), "hod_tra_spine": ((110, 130, 80), "ribs"),
                "hod_crs_palm": ((150, 124, 92), "ribs"), "hod_kas_blackbark": ((40, 36, 34), "ribs"),
                "hod_umb_black": ((40, 36, 62), "ribs"), "hod_umb_pink": ((255, 120, 240), "rings"),
                "hod_umb_red": ((255, 74, 46), "slag"), "hod_col_mound": ((150, 112, 72), "ribs"),
                "hod_col_egg": ((214, 206, 160), "slag"), "hod_rus_stone": ((206, 196, 172), "blocks"),
                "hod_boz_stone": ((150, 138, 120), "blocks"), "hod_boz_bone": ((224, 214, 188), "slag"),
                "hod_boz_rock": ((132, 112, 92), "blocks"), "hod_ith_cloud": ((242, 242, 248), "slag"),
                "hod_ith_hull": ((158, 166, 140), "plates"), "hod_ith_fungus_blue": ((104, 136, 232), "slag"),
                "hod_ith_fungus_pink": ((232, 128, 192), "slag"), "hod_aga_stone": ((180, 136, 98), "blocks"),
                "hod_kal_rock": ((112, 106, 92), "blocks"), "hod_kal_moss": ((82, 122, 60), "slag"),
                "hod_muun_rock": ((72, 66, 62), "slag"), "hod_muun_lava": ((255, 124, 44), "slag"),
                "hod_myg_ice": ((170, 214, 236), "slag"), "hod_myg_glow": ((170, 240, 255), "slag"),
                "hod_yag_rock": ((116, 112, 100), "blocks"), "hod_yag_moss": ((76, 110, 56), "slag"),
                "hod_ilu_ice": ((200, 228, 246), "slag"), "hod_ilu_glow": ((150, 215, 255), "slag"),
                "hod_dor_stone": ((70, 64, 60), "blocks"), "hod_dor_moss": ((110, 100, 60), "slag"),
                "hod_yin_rock": ((150, 112, 78), "blocks"), "hod_yin_ochre": ((190, 140, 84), "slag"),
                "hod_cor_cane": ((120, 140, 70), "ribs"), "hod_ark_ice": ((206, 226, 240), "slag"),
                "hod_ark_glint": ((235, 245, 255), "slag"), "hod_anx_stalk": ((150, 48, 40), "ribs"),
                "hod_anx_crown": ((196, 60, 50), "slag")}
# planet foliage from Etti IV on: each texture its own random seed (from its name), so adding one leaves the others'
# textures unchanged (PLANET_FOLIAGE above shares one random stream: never append to it)
PLANET_FOLIAGE_OWN = {"hod_foliage_etti": ((70, 120, 60), (45, 92, 48)),          # Etti IV: deep forest green
                      "hod_foliage_etti_dry": ((178, 160, 92), (140, 128, 70)),   # the hot plains' dry grass
                      "hod_foliage_etti_reed": ((96, 140, 84), (70, 112, 66)),    # reed beds in the shallows
                      "hod_foliage_ruu": ((56, 118, 64), (36, 88, 52)),            # Ruuria: humid jungle green
                      "hod_foliage_ruu_fern": ((84, 140, 70), (60, 112, 56)),      # its tree ferns
                      "hod_foliage_ruu_reed": ((150, 130, 110), (120, 110, 90)),   # pink-river reeds, washed out
                      "hod_foliage_oss_bamboo": ((120, 160, 70), (90, 130, 56)),   # Ossus: bamboo leaves
                      "hod_foliage_oss_uneti": ((66, 112, 72), (48, 90, 60)),      # the uneti's dark crown
                      "hod_foliage_oss_wodobo": ((112, 128, 70), (88, 104, 58)),   # wodobo bushes
                      "hod_foliage_rv": ((80, 124, 66), (58, 100, 56)),            # Ringo Vinda: temperate green
                      "hod_foliage_mcl_palm": ((92, 150, 72), (64, 120, 58)),      # Mon Cala: island palm fronds
                      "hod_foliage_lia": ((112, 132, 72), (86, 108, 58)),          # Lianna: dry olive-green crowns
                      "hod_foliage_lia_dry": ((180, 162, 104), (146, 132, 86)),    # Lianna: dry grass
                      "hod_foliage_jab": ((52, 88, 56), (36, 68, 46)),             # Jabiim: dark wet green
                      "hod_foliage_jab_marsh": ((96, 118, 70), (72, 96, 58)),      # Jabiim: marsh grass
                      "hod_foliage_jab_bamboo": ((70, 104, 60), (52, 84, 48)),     # Jabiim: bamboo leaves
                      "hod_foliage_sal": ((110, 132, 76), (84, 108, 62)),          # Saleucami: cake-tree tiers
                      "hod_foliage_sal_reed": ((118, 130, 78), (94, 108, 64)),     # Saleucami: wetland reeds
                      "hod_foliage_tel": ((78, 118, 70), (58, 96, 58)),            # Telos: blba, dark Ithorian green
                      "hod_foliage_tel_bachani": ((112, 128, 220), (150, 112, 200)),   # Telos: blue and lavender blooms
                      "hod_foliage_ser": ((206, 156, 62), (184, 102, 46)),         # Serenno: autumn gold and amber
                      "hod_foliage_ser_pine": ((52, 86, 62), (40, 70, 54)),        # Serenno: dark pine
                      "hod_foliage_yav": ((50, 112, 58), (36, 88, 48)),            # Yavin IV: deep jungle green
                      "hod_foliage_yav_fern": ((84, 144, 66), (60, 120, 54)),      # Yavin IV: ferns, brighter
                      "hod_foliage_cel": ((86, 126, 64), (66, 106, 54)),           # Celanon: temperate green
                      "hod_foliage_cel_grass": ((190, 170, 96), (160, 146, 82)),   # Celanon: golden plains grass
                      "hod_foliage_cit": ((54, 92, 58), (44, 78, 50)),
                      "hod_foliage_dat": ((128, 46, 44), (92, 34, 38)),            # Dathomir: blood-red crowns
                      "hod_foliage_dat_fern": ((84, 76, 58), (62, 56, 46)),        # its swamp undergrowth, dark olive
                      "hod_foliage_man": ((90, 122, 70), (68, 98, 58)),            # Mandalore: veshok green
                      "hod_foliage_con": ((78, 128, 82), (56, 104, 66)),           # Concordia: wisp green
                      "hod_foliage_tar": ((92, 120, 60), (110, 120, 70)),          # Taris: vines, sickly fungus
                      "hod_foliage_way": ((64, 110, 56), (48, 90, 46)),            # Wayland: old forest green
                      "hod_foliage_way_fern": ((82, 130, 64), (62, 108, 52)),      # its undergrowth
                      "hod_foliage_tra": ((48, 96, 44), (36, 76, 38)),             # Trandosha: dark jungle green
                      "hod_foliage_tra_dry": ((150, 140, 74), (120, 116, 62)),     # its savannah, dry olive
                      "hod_foliage_nyr": ((82, 138, 60), (60, 116, 52)),           # Nyriaan: bright tropical green
                      "hod_foliage_nyr_nettle": ((104, 120, 64), (84, 100, 56)),   # its mire nettles
                      "hod_foliage_crs_palm": ((76, 146, 66), (56, 122, 56)),      # Corsin: palm fronds
                      "hod_foliage_crs_shrub": ((182, 96, 120), (72, 132, 64)),    # its flowering shrubs
                      "hod_foliage_kas_vine": ((70, 112, 54), (52, 92, 46)),       # Kashyyyk: forest floor
                      "hod_foliage_kas_web": ((150, 150, 140), (60, 66, 56)),      # Black Forest: web and dead leaf
                      "hod_foliage_ond": ((70, 124, 58), (52, 102, 50)),           # Onderon: jungle green
                      "hod_foliage_ond_weed": ((92, 120, 150), (70, 110, 70)),     # skeleton weed, blue Hutt's tongue
                      "hod_foliage_umb_grass": ((46, 54, 124), (176, 42, 66)),     # Umbara: dark blue grass, red tips
                      "hod_foliage_col": ((84, 136, 52), (64, 112, 44)),
                      "hod_foliage_rus": ((108, 150, 62), (150, 158, 70)),        # Ruusan: healed green, golden
                      "hod_foliage_rus_scrub": ((96, 120, 70), (160, 130, 190)),
                      "hod_foliage_boz_grass": ((156, 150, 88), (126, 124, 72)),  # Boz Pity: dry yellowed grass
                      "hod_foliage_man_galek": ((190, 196, 198), (150, 160, 166)),  # Mandalore: galek, silver leaves
                      "hod_foliage_man_fern": ((214, 172, 72), (180, 140, 58)),     # amber ferns, golden
                      "hod_foliage_man_varos": ((50, 104, 48), (38, 84, 42)),       # varos jungle, dark green
                      "hod_foliage_ith": ((52, 116, 56), (38, 94, 48)),             # Ithor: the Mother Jungle
                      "hod_foliage_om_pine": ((54, 92, 64), (40, 76, 54)),          # Ord Mantell: conifers
                      "hod_foliage_om_scrub": ((132, 128, 80), (110, 104, 66)),     # its dry scrub
                      "hod_foliage_gar": ((136, 72, 150), (104, 56, 124)),          # Garqi: purple crowns
                      "hod_foliage_gar_shrub": ((166, 92, 176), (124, 70, 142)),    # purple shrubs
                      "hod_foliage_gar_caf": ((56, 112, 52), (44, 92, 44)),         # caf, a planted green
                      "hod_foliage_aga_binka": ((100, 126, 62), (80, 106, 52)),     # Agamar: binka, dry green
                      "hod_foliage_aga_grass": ((182, 162, 92), (154, 138, 78)),    # golden ranch grass
                      "hod_foliage_ot_scrub": ((130, 126, 106), (106, 102, 88)),    # Ord Trasi: grey scrub
                      "hod_foliage_dan": ((104, 140, 82), (86, 122, 70)),           # Dantooine: blba crowns
                      "hod_foliage_dan_grass": ((180, 188, 134), (160, 176, 128)),  # pastel grass
                      "hod_foliage_dub": ((62, 140, 62), (46, 118, 52)),            # Dubrillion: lush green
                      "hod_foliage_kal": ((44, 96, 46), (70, 92, 42)),              # Kalee: dark rainforest
                      "hod_foliage_muun": ((70, 122, 110), (56, 102, 92)),          # Muunilinst: blue-green
                      "hod_foliage_bas": ((64, 102, 58), (50, 86, 48)),             # Bastion: temperate green
                      "hod_foliage_yag": ((58, 98, 52), (82, 104, 44)),
                      "hod_foliage_ans": ((96, 128, 56), (120, 136, 60)),           # Ansion: sanwiwood, olive green
                      "hod_foliage_ans_grass": ((150, 156, 74), (186, 170, 90)),
                      "hod_foliage_ilu": ((196, 214, 220), (80, 104, 96)),          # Ilum: snow-laden needles
                      "hod_foliage_dor": ((92, 108, 50), (150, 110, 50)),
                      "hod_foliage_yin": ((112, 110, 62), (140, 120, 70)),
                      "hod_foliage_cha": ((70, 124, 58), (96, 140, 70)),            # Chandrila: lush blue-green
                      "hod_foliage_cha_balm": ((112, 150, 70), (150, 170, 96)),
                      "hod_foliage_cor": ((96, 140, 60), (120, 156, 70)),           # Corulag: bamboo leaves
                      "hod_foliage_anx": ((150, 70, 60), (120, 90, 60)),            # Anaxes: Sirpar, rust-red
                      "hod_foliage_ess": ((70, 130, 56), (100, 150, 60))}           # Esseles: palm fronds           # Dorin: kand, olive and amber fruit    # Ansion: plains grass, gold tips             # Bastion: temperate green  # scented bushes, lilac flowers           # Colla IV: tropical green             # Ciutric IV: dark forest green


def planet_textures():
    """the PLANET_FOLIAGE textures and the atlases of the PROCEDURAL models that use them; merges atlas.json and
    leaf_materials.json (own random seed: textures() output is unchanged)"""
    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(81)
    leaves = _leaves()
    tex = {}
    flat_n = np.dstack([np.full((TEX_SIZE, TEX_SIZE), v, np.float32) for v in (128, 128, 255, 255)])
    for name, tint in PLANET_FOLIAGE.items():
        col, alp = _foliage(tint, rng, leaves)
        tex[name] = (np.dstack([np.clip(col, 0, 255), alp]), flat_n)
        save_dxt5_mips(tex[name][0], f"{OUT}/{name}_diffuse.dds")
        save_dxt5_mips(flat_n, f"{OUT}/{name}_normal.dds")
    from scipy import ndimage as ndi
    yy, xx = np.mgrid[0:TEX_SIZE, 0:TEX_SIZE].astype(np.float32)
    for name, (base, kind) in PLANET_SOLID.items():
        g = ndi.gaussian_filter(rng.random((TEX_SIZE, TEX_SIZE)), 3)
        g = ((g - g.min()) / np.ptp(g))[..., None]
        if kind == "ribs":                                                   # u runs round the cactus: ribs + spines
            pat = (0.75 + 0.35 * np.abs(np.sin(xx * np.pi * 12 / TEX_SIZE)))[..., None]
            pat = pat * (1 + 0.25 * (rng.random((TEX_SIZE, TEX_SIZE)) > 0.985)[..., None])
        elif kind == "rings":                                                # glowing segments along a tube (v)
            pat = (0.5 + 0.6 * np.abs(np.sin(yy * np.pi * 10 / TEX_SIZE)) ** 0.5)[..., None]
        elif kind == "plates":                                               # rust-streaked steel plates
            b = ndi.gaussian_filter(rng.random((TEX_SIZE, TEX_SIZE)), (40, 2))
            pat = (1 - 0.3 * (((yy % 48) < 3) | ((xx % 64) < 3)))[..., None]
            pat = pat * (0.75 + 0.4 * ((b - b.min()) / np.ptp(b)))[..., None]
        elif kind == "slag":                                                 # lumpy dark spoil with rust and ochre
            b = ndi.gaussian_filter(rng.random((TEX_SIZE, TEX_SIZE)), 6)
            pat = (0.7 + 0.6 * ((b - b.min()) / np.ptp(b)))[..., None] * np.array([1.0, 0.95, 0.85])
        else:                                                                # weathered courses of big blocks
            b = ndi.gaussian_filter(rng.random((TEX_SIZE, TEX_SIZE)), 18)
            pat = (1 - 0.3 * (((yy % 64) < 3) | (((xx + 48 * ((yy // 64) % 2)) % 96) < 3)))[..., None]
            pat = pat * (0.8 + 0.3 * ((b - b.min()) / np.ptp(b)))[..., None]
        col = np.clip(np.array(base, np.float32) * (0.8 + 0.3 * g) * pat, 0, 255)
        tex[name] = (np.dstack([col, np.full((TEX_SIZE, TEX_SIZE), 255, np.float32)]), flat_n)
        save_dxt5_mips(tex[name][0], f"{OUT}/{name}_diffuse.dds")
        save_dxt5_mips(flat_n, f"{OUT}/{name}_normal.dds")
    import zlib
    for name, tint in PLANET_FOLIAGE_OWN.items():
        col, alp = _foliage(tint, np.random.default_rng(zlib.crc32(name.encode())), leaves)
        tex[name] = (np.dstack([np.clip(col, 0, 255), alp]), flat_n)
        save_dxt5_mips(tex[name][0], f"{OUT}/{name}_diffuse.dds")
        save_dxt5_mips(flat_n, f"{OUT}/{name}_normal.dds")
    rgb = lambda q: np.asarray(Image.open(q).convert("RGB").resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float32)
    for mname, diff, nrm, _alpha in materials("dead_tree_trunk_02"):  # the bark, as textures() makes it
        n = rgb(nrm) if nrm else np.dstack([np.full((TEX_SIZE, TEX_SIZE), v, np.float32) for v in (128, 128, 255)])
        tex[f"hod_{mname}"] = (np.dstack([rgb(diff), np.full((TEX_SIZE, TEX_SIZE), 255, np.float32)]),
                               np.dstack([n, np.full(n.shape[:2], 255, np.float32)]))
    atlas = json.load(open(f"{OUT}/atlas.json"))
    leaf = json.load(open(f"{OUT}/leaf_materials.json"))
    for idx, stems in PROC_MATS.items():
        if any(st in PLANET_FOLIAGE or st in PLANET_FOLIAGE_OWN or st in PLANET_SOLID for st in stems):
            if len(stems) > 1:
                _atlas(idx, stems, tex)
                atlas[str(idx)] = stems
    leaf.update({name: True for name in list(PLANET_FOLIAGE) + list(PLANET_FOLIAGE_OWN)})
    json.dump(atlas, open(f"{OUT}/atlas.json", "w"), indent=1)
    json.dump(leaf, open(f"{OUT}/leaf_materials.json", "w"), indent=1)
    print("planet foliage:", list(PLANET_FOLIAGE), "atlases:", [i for i, st in PROC_MATS.items() if any(x in PLANET_FOLIAGE for x in st)])


def save_dxt5_mips(rgba, path):
    """DXT5 DDS with a full mip chain (Pillow writes one level; concatenate levels and patch the header)."""
    import numpy as np
    from PIL import Image
    levels, im = [], Image.fromarray(np.asarray(rgba, np.uint8), "RGBA")
    while True:
        buf = io.BytesIO()
        im.save(buf, format="DDS", pixel_format="DXT5")
        levels.append(buf.getvalue())
        if im.size == (1, 1):
            break
        im = im.resize((max(1, im.size[0] // 2), max(1, im.size[1] // 2)), Image.BOX)
    hdr = bytearray(levels[0][:128])
    struct.pack_into("<I", hdr, 8, struct.unpack_from("<I", hdr, 8)[0] | 0x20000)
    struct.pack_into("<I", hdr, 28, len(levels))
    struct.pack_into("<I", hdr, 108, struct.unpack_from("<I", hdr, 108)[0] | 0x400008)
    with open(path, "wb") as f:
        f.write(bytes(hdr) + b"".join(l[128:] for l in levels))


def download():
    import urllib.request
    hdr = {"User-Agent": "HoD-mod/1.0"}
    for pid in [a[0] for a in ASSETS.values()] + [LEAF_SRC]:
        d = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.polyhaven.com/files/{pid}", headers=hdr)))
        g = d["gltf"]["1k"]["gltf"]
        files = [(f"{pid}.gltf", g["url"])] + [(rel, v["url"]) for rel, v in g.get("include", {}).items()]
        files += [(f"textures/{os.path.basename(v['1k']['png']['url'])}", v["1k"]["png"]["url"])
                  for k, v in d.items() if "alpha" in k.lower()]
        for rel, url in files:
            path = f"{SRC}/{pid}/{rel}"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not os.path.exists(path):
                urllib.request.urlretrieve(url, path)
        print(pid, len(files), "files")


def materials(pid):
    """[(material name, diffuse path, normal path, alpha path or None)] from the asset's glTF."""
    g = json.load(open(f"{SRC}/{pid}/{pid}.gltf", encoding="utf-8"))
    uri = lambda t: f"{SRC}/{pid}/" + g["images"][g["textures"][t["index"]]["source"]]["uri"]
    out = []
    for m in g["materials"]:
        diff = uri(m["pbrMetallicRoughness"]["baseColorTexture"])
        nrm = uri(m["normalTexture"]) if "normalTexture" in m else None
        alpha = None
        if m.get("alphaMode") in ("BLEND", "MASK"):
            alpha = next((p for p in (f"{SRC}/{pid}/textures/{m['name']}_alpha_1k.png",
                                      f"{SRC}/{pid}/textures/{pid}_alpha_1k.png") if os.path.exists(p)), None)
        out.append((m["name"], diff, nrm, alpha))
    return out


def _leaves():
    """the Poly Haven leaf sheet cut into single leaves: [(rgb, mask)]"""
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    sheet = np.asarray(Image.open(f"{SRC}/{LEAF_SRC}/textures/{LEAF_SRC}_leaves_diff_1k.jpg").convert("RGB")).astype(np.float32)
    mask = np.asarray(Image.open(f"{SRC}/{LEAF_SRC}/textures/{LEAF_SRC}_leaves_alpha_1k.png").convert("L")) > 128
    lab, n = ndi.label(mask)
    return [(sheet[sl], mask[sl] & (lab[sl] == i + 1)) for i, sl in enumerate(ndi.find_objects(lab))
            if (lab[sl] == i + 1).sum() > 4000]


def _foliage(tint, rng, leaves):
    """one foliage-clump texture: hundreds of small leaves packed into a soft disc (one leaf card = one clump of
    foliage, the way game trees are built). tint: rgb multiplier, or (rgb, rgb) to recolour each leaf by brightness"""
    import numpy as np
    from PIL import Image
    S = TEX_SIZE
    col = np.zeros((S, S, 3), np.float32)
    alp = np.zeros((S, S), np.float32)
    for _ in range(420):
        c, m = leaves[rng.integers(len(leaves))]
        sc = rng.uniform(0.07, 0.13) * S / max(c.shape[:2])
        ang = rng.uniform(0, 360)
        ci = Image.fromarray(c.astype(np.uint8)).resize((max(2, int(c.shape[1] * sc)), max(2, int(c.shape[0] * sc))))
        mi = Image.fromarray((m * 255).astype(np.uint8)).resize(ci.size)
        ci, mi = np.asarray(ci.rotate(ang, expand=True)).astype(np.float32), np.asarray(mi.rotate(ang, expand=True)) > 128
        r = S * 0.42 * np.sqrt(rng.random())
        a = rng.uniform(0, 6.283)
        y0, x0 = int(S / 2 + r * np.sin(a) - mi.shape[0] / 2), int(S / 2 + r * np.cos(a) - mi.shape[1] / 2)
        ys, xs = np.nonzero(mi)
        ys, xs = ys + y0, xs + x0
        ok = (ys >= 0) & (ys < S) & (xs >= 0) & (xs < S)
        shade = 0.55 + 0.45 * (1 - r / (S * 0.42)) * rng.uniform(0.8, 1.1)    # darker toward the rim, like depth
        src = ci[ys[ok] - y0, xs[ok] - x0]
        if isinstance(tint[0], tuple):                                       # recolour by leaf brightness
            hue = np.array(tint[0], np.float32) + (np.array(tint[1], np.float32) - tint[0]) * rng.random()
            src = (src.mean(-1, keepdims=True) / 70) * hue                   # bright: map trees render dark
        else:
            src = src * np.array(tint)
        col[ys[ok], xs[ok]] = src * shade
        alp[ys[ok], xs[ok]] = 255
    return col, alp


def _atlas(idx, stems, tex):
    """one atlas per multi-material model: the tree renderer draws only a mesh's first material (vanilla trees all
    have one), so trunk + leaves share one texture, one vertical slot each (bottom-up = Blender's v)"""
    import numpy as np
    k = 1 << (len(stems) - 1).bit_length()
    for ch, suffix in ((0, "diffuse"), (1, "normal")):
        img = np.zeros((TEX_SIZE * k, TEX_SIZE, 4), np.float32)
        img[...] = tex[stems[0]][ch][0, 0]
        for slot, stem in enumerate(stems):
            img[(k - 1 - slot) * TEX_SIZE:(k - slot) * TEX_SIZE] = tex[stem][ch]
        save_dxt5_mips(img, f"{OUT}/hod_flora_{idx}_atlas_{suffix}.dds")


def textures():
    import numpy as np
    from PIL import Image
    os.makedirs(OUT, exist_ok=True)
    rgb = lambda p: np.asarray(Image.open(p).convert("RGB").resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float32)
    leaf, tex = {}, {}

    def save(stem, diff, nrm):
        tex[stem] = (diff, nrm)
        save_dxt5_mips(diff, f"{OUT}/{stem}_diffuse.dds")
        save_dxt5_mips(nrm, f"{OUT}/{stem}_normal.dds")

    for pid, *_ in ASSETS.values():
        for name, diff, nrm, alpha in materials(pid):
            a = (np.asarray(Image.open(alpha).convert("L").resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float32)
                 if alpha else np.full((TEX_SIZE, TEX_SIZE), 255, np.float32))
            n = rgb(nrm) if nrm else np.dstack([np.full((TEX_SIZE, TEX_SIZE), v, np.float32) for v in (128, 128, 255)])
            save(f"hod_{name}", np.dstack([rgb(diff), a]), np.dstack([n, np.full(n.shape[:2], 255, np.float32)]))
            leaf[name] = alpha is not None
    flat = np.zeros((16, 16, 4), np.float32)
    save_dxt5_mips(flat, f"{OUT}/hod_flora_spec.dds")
    flat_n = np.dstack([np.full((TEX_SIZE, TEX_SIZE), v, np.float32) for v in (128, 128, 255, 255)])
    rng = np.random.default_rng(66)
    # foliage clumps: hundreds of small copies of the Poly Haven leaves packed into a soft disc (one leaf card
    # = one clump of foliage, the way game trees are built)
    from scipy import ndimage as ndi
    leaves = _leaves()
    for name, tint in (("hod_foliage_wroshyr", (0.55, 0.75, 0.5)), ("hod_foliage_jungle", (0.8, 1.0, 0.6)),
                       ("hod_foliage_raxus", ((250, 190, 70), (235, 125, 35))),       # gold .. orange, per leaf
                       ("hod_foliage_crimson", ((200, 45, 60), (150, 25, 50)))):
        col, alp = _foliage(tint, rng, leaves)
        save(name, np.dstack([np.clip(col, 0, 255), alp]), flat_n)
        leaf[name] = True
    # homestead adobe (panelled-surface generator, panels off)
    S = TEX_SIZE
    yy, xx = np.mgrid[0:S, 0:S]

    def surface(stem, colour, panels, streaks):
        grime = ndi.gaussian_filter(rng.random((S, S)), 6)
        grime = (grime - grime.min()) / np.ptp(grime)
        streak = ndi.gaussian_filter(rng.random((S, S)), (24, 1.5))
        streak = (streak - streak.min()) / np.ptp(streak)
        panel = ((xx % 128 < 2) | (yy % 96 < 2)).astype(np.float32) * panels
        base = np.array(colour, np.float32) * (0.75 + 0.35 * grime[..., None]) * (0.85 + 0.25 * streak[..., None])
        base = base * (1 - 0.25 * panel[..., None]) * (1 - streaks * (streak[..., None] > 0.7))
        lum = ndi.gaussian_filter(base.mean(-1) / 255, 1)
        gx, gy = ndi.sobel(lum, 1) * 2, ndi.sobel(lum, 0) * 2
        nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        save(stem, np.dstack([np.clip(base, 0, 255), np.full((S, S), 255, np.float32)]),
             np.dstack([nrm * 127.5 + 127.5, np.full((S, S), 255, np.float32)]))

    surface("hod_adobe", (176, 156, 122), 0, 0.08)

    def organic(stem, stops, spots=None, veins=0.0):
        """Felucian flora: colour by the texture's v (bottom-up = along the lathe profile), soft mottling, optional
        pale spots and vertical veins. stops: [(v, (r, g, b))]"""
        v = 1 - yy / (S - 1)                       # image row 0 = top = Blender v 1
        vs, cs = zip(*stops)
        base = np.stack([np.interp(v, vs, [c[i] for c in cs]) for i in range(3)], -1)
        mott = ndi.gaussian_filter(rng.random((S, S)), 5)
        mott = (mott - mott.min()) / np.ptp(mott)
        base = base * (0.8 + 0.35 * mott[..., None])
        if veins:
            vein = ndi.gaussian_filter(rng.random((S, S)), (30, 1.2))
            vein = (vein - vein.min()) / np.ptp(vein)
            base = base * (1 - veins * (vein[..., None] > 0.72))
        if spots:
            col, n, r = spots
            for _ in range(n):
                cy, cx, rr = rng.integers(0, S), rng.integers(0, S), rng.uniform(0.4, 1.0) * r
                d = np.hypot(np.minimum(abs(yy - cy), S - abs(yy - cy)), np.minimum(abs(xx - cx), S - abs(xx - cx)))
                m = np.clip((rr - d) / 2, 0, 1)[..., None] * (v[..., None] > 0.45)
                base = base * (1 - m) + np.array(col, np.float32) * m
        lum = ndi.gaussian_filter(base.mean(-1) / 255, 1.5)
        gx, gy = ndi.sobel(lum, 1) * 1.5, ndi.sobel(lum, 0) * 1.5
        nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        save(stem, np.dstack([np.clip(base, 0, 255), np.full((S, S), 255, np.float32)]),
             np.dstack([nrm * 127.5 + 127.5, np.full((S, S), 255, np.float32)]))

    # stalk: pale cream foot -> lilac top; cap profile runs underside (gills) -> rim -> crown
    organic("hod_fel_stalk", [(0, (150, 135, 120)), (0.6, (205, 190, 200)), (1, (185, 150, 210))], veins=0.15)
    organic("hod_fel_cap", [(0, (95, 45, 95)), (0.3, (150, 80, 150)), (0.42, (235, 190, 240)), (0.55, (150, 55, 190)),
                            (1, (95, 30, 150))], spots=((240, 215, 120), 26, 14))
    organic("hod_fel_bulb", [(0, (120, 60, 30)), (0.35, (235, 120, 25)), (0.8, (255, 205, 60)), (1, (255, 240, 150))], veins=0.2)
    organic("hod_fel_pitcher", [(0, (25, 70, 65)), (0.55, (40, 165, 160)), (0.82, (90, 210, 200)), (0.9, (225, 45, 140)),
                                (1, (250, 110, 190))], veins=0.25)
    organic("hod_fel_frond", [(0, (70, 15, 30)), (0.5, (200, 30, 60)), (1, (255, 120, 70))], veins=0.3)
    organic("hod_rax_trunk", [(0, (78, 40, 26)), (0.5, (128, 66, 38)), (1, (150, 84, 48))], veins=0.35)
    for stem in ("hod_fel_stalk", "hod_fel_cap", "hod_fel_bulb", "hod_fel_pitcher", "hod_fel_frond", "hod_rax_trunk"):
        leaf[stem] = False
    # last, so the random stream of every texture above stays the same
    surface("hod_scrap_metal", (150, 96, 64), 1, 0.25)                    # rusty plating for the junk pieces
    from terrain_atlas import scrap_tile                                    # the junk heaps' packed surface
    junk, _h = scrap_tile(512, seed=73)
    save("hod_scrap_tile", np.dstack([np.clip(junk * 1.25, 0, 255), np.full((S, S), 255, np.float32)]), flat_n)
    leaf["hod_scrap_metal"] = leaf["hod_scrap_tile"] = False
    # junk clump cards: hundreds of plates, girders and drums packed in a soft disc on transparent ground, the way
    # foliage clumps are made from leaves
    from PIL import ImageDraw
    rj = np.random.default_rng(74)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for _ in range(520):
        rr, a = S * 0.43 * np.sqrt(rj.random()), rj.uniform(0, 6.283)
        cx, cy = S / 2 + rr * np.cos(a), S / 2 + rr * np.sin(a)
        rust = rj.random()
        c = (np.array([160, 88, 48]) * rust + np.array([128, 126, 122]) * (1 - rust)) * rj.uniform(0.6, 1.2)
        if rj.random() < 0.07:
            c = np.array([(150, 60, 45), (60, 85, 125), (170, 150, 70)][rj.integers(3)])
        c = tuple(int(v) for v in np.clip(c * (1.1 - 0.4 * rr / (S * 0.43)), 0, 255)) + (255,)
        k = rj.random()
        if k < 0.6:
            w, h, t = rj.uniform(6, 26), rj.uniform(4, 14), rj.uniform(0, np.pi)
            pts = [(cx + dx * np.cos(t) - dy * np.sin(t), cy + dx * np.sin(t) + dy * np.cos(t))
                   for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]
            d.polygon(pts, fill=c, outline=(28, 22, 18, 255))
        elif k < 0.85:
            L, t = rj.uniform(12, 40), rj.uniform(0, np.pi)
            d.line([(cx - L * np.cos(t), cy - L * np.sin(t)), (cx + L * np.cos(t), cy + L * np.sin(t))], fill=c,
                   width=int(rj.integers(2, 6)))
        else:
            r_ = rj.uniform(4, 10)
            d.ellipse([cx - r_, cy - r_, cx + r_, cy + r_], fill=c, outline=(28, 22, 18, 255))
    save("hod_junk_clump", np.asarray(im).astype(np.float32), flat_n)
    leaf["hod_junk_clump"] = True
    surface("hod_kor_rock", (156, 64, 44), 0, 0.2)                      # Korriban: red rock, streaked
    surface("hod_kor_stone", (176, 132, 112), 0, 0.05)                  # pale carved stone of the ruins
    leaf["hod_kor_rock"] = leaf["hod_kor_stone"] = False
    # one atlas per multi-material model: the tree renderer draws only a mesh's first material (vanilla trees
    # all have one), so trunk + leaves share one texture, one vertical slot each (bottom-up = Blender's v)
    atlas = {idx: [f"hod_{m[0]}" for m in materials(pid)] for idx, (pid, *_r) in ASSETS.items()}
    atlas.update(PROC_MATS)
    atlas = {idx: stems for idx, stems in atlas.items() if len(stems) > 1}
    for idx, stems in atlas.items():
        _atlas(idx, stems, tex)
    json.dump(atlas, open(f"{OUT}/atlas.json", "w"), indent=1)
    leaf["hod_adobe"] = False
    json.dump(leaf, open(f"{OUT}/leaf_materials.json", "w"), indent=1)
    print("textures:", len(leaf), "materials,", sum(leaf.values()), "with leaf alpha")


def single_material(obj, idx, stems, bie, PDX_SHADER, out_dir):
    """Blender: give the mesh one PDX material. With several, move each face's UVs into its material's slot of
    the atlas written by textures() (atlas.json) and point every face at slot 0."""
    import bpy  # type: ignore

    class Mat:
        def __init__(self, tex):
            self.shader = ["PdxMeshAdvancedSnow"]
            self.diff, self.n, self.spec = [f"{tex}_diffuse.dds"], [f"{tex}_normal.dds"], ["hod_flora_spec.dds"]

    me = obj.data
    used = sorted({p.material_index for p in me.polygons})
    tex = stems[used[0]]
    if len({stems[i] for i in used}) > 1:
        order = json.load(open(f"{OUT}/atlas.json"))[str(idx)]
        k = 1 << (len(order) - 1).bit_length()
        uv = me.uv_layers[0].data
        for p in me.polygons:
            slot = order.index(stems[p.material_index])
            for li in p.loop_indices:
                u, v = uv[li].uv
                uv[li].uv = (u, (slot + min(max(v, 0.0), 1.0)) / k)
            p.material_index = 0
        tex = f"hod_flora_{idx}_atlas"
    else:
        for p in me.polygons:
            p.material_index = 0
    mat = bie.create_shader(Mat(tex), tex, out_dir)
    mat[PDX_SHADER] = "PdxMeshAdvancedSnow"
    me.materials[0] = mat
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.material_slot_remove_unused()


def meshes():
    import random
    import bmesh  # type: ignore
    import bpy  # type: ignore
    import numpy as np
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    leaf = json.load(open(f"{OUT}/leaf_materials.json"))
    out_dir = os.path.abspath(OUT)
    rng = random.Random(1977)

    class Mat:   # minimal stand-in for io_pdx_mesh's parsed PDX material
        def __init__(self, name):
            self.shader = ["PdxMeshAdvancedSnow"]
            self.diff = [f"hod_{name}_diffuse.dds"]
            self.n = [f"hod_{name}_normal.dds"]
            self.spec = ["hod_flora_spec.dds"]

    def tri_count(o):
        return sum(len(p.vertices) - 2 for p in o.data.polygons)

    def apply(o, mod_type, **kw):
        bpy.context.view_layer.objects.active = o
        m = o.modifiers.new("m", mod_type)
        for k, v in kw.items():
            setattr(m, k, v)
        bpy.ops.object.modifier_apply(modifier=m.name)

    def islands(me):
        """(triangles, island label per vertex, island ids, island index per face, triangles per island)."""
        nv, nf = len(me.vertices), len(me.polygons)
        tri = np.empty(nf * 3, np.int64)
        me.polygons.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3)
        lab = np.arange(nv)
        e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]]])
        while True:                                   # label propagation + pointer jumping = connected islands
            old = lab.copy()
            m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
            np.minimum.at(lab, e[:, 0], m)
            np.minimum.at(lab, e[:, 1], m)
            lab = lab[lab]
            if np.array_equal(lab, old):
                break
        isl, inv, cnt = np.unique(lab[tri[:, 0]], return_inverse=True, return_counts=True)
        return tri, lab, isl, inv, cnt

    def thin_leaves(o, budget, grow_cap=4.0, largest_first=False):
        """Keep leaf cards (connected islands) up to the budget, enlarged so the canopy keeps its cover.
        Cards are first collapsed to a few triangles each so many more of them fit. With largest_first (solid
        parts that decimation can't reduce, e.g. loose twigs and pebbles) the biggest pieces survive, unscaled."""
        apply(o, "TRIANGULATE")
        me = o.data
        nf0 = len(me.polygons)
        n_isl = len(islands(me)[2])
        if nf0 > 6 * n_isl and not largest_first:
            apply(o, "DECIMATE", ratio=6 * n_isl / nf0)
            apply(o, "TRIANGULATE")
        nv, nf = len(me.vertices), len(me.polygons)
        tri, lab, isl, inv, cnt = islands(me)
        order = list(np.argsort(-cnt)) if largest_first else list(range(len(isl)))
        if not largest_first:
            rng.shuffle(order)
        keep = np.zeros(len(isl), bool)
        total = 0
        for i in order:
            if total + cnt[i] > budget:
                continue
            keep[i] = True
            total += cnt[i]
        grow = float(np.clip(np.sqrt(nf / max(total, 1)), 1.0, grow_cap))
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        vi = np.searchsorted(isl, lab)                # island index per vertex
        cen = np.stack([np.bincount(vi, co[:, k], len(isl)) for k in range(3)], -1) / np.bincount(vi, minlength=len(isl))[:, None]
        co = cen[vi] + (co - cen[vi]) * grow
        me.vertices.foreach_set("co", co.ravel())
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(~keep[inv])[0]], context="FACES")
        bm.to_mesh(me)
        bm.free()
        return len(isl), int(keep.sum()), grow

    report = []
    only = os.environ.get("HOD_ONLY")
    for idx, (pid, prefix, budget, extent) in ASSETS.items():
        if only and str(idx) not in only.split(","):
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(f"{SRC}/{pid}/{pid}.gltf"))
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and (prefix is None or o.name.startswith(prefix))]
        for o in list(bpy.context.scene.objects):
            if o not in objs:
                bpy.data.objects.remove(o, do_unlink=True)
        for o in bpy.context.scene.objects:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        if len(objs) > 1:
            bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        src_tris = tri_count(obj)
        # split per material: leaf cards are thinned, solid parts decimated, each with its own share of the budget
        # (by sqrt of its size, so a small trunk isn't decimated away next to a huge twig mesh)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.separate(type="MATERIAL")
        bpy.ops.object.mode_set(mode="OBJECT")
        parts = [o for o in bpy.context.scene.objects if o.type == "MESH" and len(o.data.polygons)]
        is_leaf = lambda o: leaf.get(o.data.materials[o.data.polygons[0].material_index].name.split(".")[0], False)
        leaves = [o for o in parts if is_leaf(o)]
        solids = [o for o in parts if not is_leaf(o)]
        solid_budget = budget * (1 - LEAF_SHARE) if leaves else budget
        weight = {o: tri_count(o) ** 0.5 for o in solids}
        note = ""
        for o in solids:
            b = solid_budget * weight[o] / sum(weight.values())
            if tri_count(o) > b:
                apply(o, "DECIMATE", ratio=b / tri_count(o))
            if tri_count(o) > b * 1.3:      # many loose pieces: keep the biggest
                thin_leaves(o, b, grow_cap=1.0, largest_first=True)
        for o in leaves:
            n_isl, kept, grow = thin_leaves(o, budget * LEAF_SHARE / len(leaves))
            note += f", leaf cards {kept}/{n_isl} x{grow:.1f}"
        obj = (solids + leaves)[0]
        # join back, triangulate, PDX materials, second UV set (tree.shader reads uv1 as a per-tree random offset)
        for o in bpy.context.scene.objects:
            o.select_set(o.type == "MESH")
        bpy.context.view_layer.objects.active = obj
        if len(parts) > 1:
            bpy.ops.object.join()
        apply(obj, "TRIANGULATE")
        single_material(obj, idx, [f"hod_{m.name.split('.')[0]}" for m in obj.data.materials], bie, PDX_SHADER, out_dir)
        while len(obj.data.uv_layers) < 2:
            uv = obj.data.uv_layers.new()
            for d in uv.data:
                d.uv = (0.0, 0.0)
        # base on the origin, largest extent scaled to the target
        co = np.empty(len(obj.data.vertices) * 3, np.float32)
        obj.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        lo, hi = co.min(0), co.max(0)
        s = extent / float((hi - lo).max())
        co = (co - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])) * s
        obj.data.vertices.foreach_set("co", co.ravel())
        obj.data.update()
        name = f"hod_flora_{idx}_{pid}"
        obj.name = obj.data.name = name
        bie.export_meshfile(os.path.join(out_dir, name + ".mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
        d = (hi - lo) * s
        per = collections.Counter(obj.data.materials[p.material_index].name for p in obj.data.polygons)
        note += f", {dict(per)}"
        report.append(f"{idx} {pid}: {src_tris} -> {tri_count(obj)} tris, size {d[0]:.2f} x {d[1]:.2f} x {d[2]:.2f}{note}")
    print("\n".join(report))


def procedural(*only):
    """Blender: the PROCEDURAL models from primitives (textures from textures() / planet_textures()). only: indices or
    kinds to build (default all); the planet floras (dk_, zyg_) reseed per model, so they come out the same alone or
    with the rest."""
    import math
    import random
    import bmesh  # type: ignore
    import bpy  # type: ignore
    from mathutils import Matrix, Vector  # type: ignore
    sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), "4.2", "scripts", "addons"))
    import io_pdx_mesh  # noqa: F401
    from io_pdx_mesh.library import PDX_SHADER
    from io_pdx_mesh.pdx_blender import blender_import_export as bie
    out_dir = os.path.abspath(OUT)
    rng = random.Random(4)

    class Mat:
        def __init__(self, tex):
            self.shader = ["PdxMeshAdvancedSnow"]
            self.diff, self.n, self.spec = [f"{tex}_diffuse.dds"], [f"{tex}_normal.dds"], ["hod_flora_spec.dds"]

    def tube(bm, uv, pts, sides, mat, vrep=1.0):
        """Rings of (centre Vector, radius) joined into a tapered tube, cylindrical UVs."""
        rings = []
        for c, r in pts:
            rings.append([bm.verts.new(c + Vector((math.cos(a) * r, math.sin(a) * r, 0)))
                          for a in (2 * math.pi * i / sides for i in range(sides))])
        for k in range(len(rings) - 1):
            for i in range(sides):
                j = (i + 1) % sides
                f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
                f.material_index = mat
                for loop, (u, v) in zip(f.loops, ((i / sides, k / len(rings)), ((i + 1) / sides, k / len(rings)),
                                                  ((i + 1) / sides, (k + 1) / len(rings)), (i / sides, (k + 1) / len(rings)))):
                    loop[uv].uv = (u, v * vrep)

    def limb(bm, uv, a, b, r0, r1, mat, sides=5, segs=3):
        """Tube from a to b (rings oriented along the limb)."""
        d = (b - a)
        rot = d.to_track_quat("Z", "Y").to_matrix()
        rings = []
        for k in range(segs + 1):
            t = k / segs
            c, r = a + d * t, r0 + (r1 - r0) * t
            rings.append([bm.verts.new(c + rot @ Vector((math.cos(x) * r, math.sin(x) * r, 0)))
                          for x in (2 * math.pi * i / sides for i in range(sides))])
        for k in range(segs):
            for i in range(sides):
                j = (i + 1) % sides
                f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
                f.material_index = mat
                for loop, (u, v) in zip(f.loops, ((i / sides, k / segs), ((i + 1) / sides, k / segs),
                                                  ((i + 1) / sides, (k + 1) / segs), (i / sides, (k + 1) / segs))):
                    loop[uv].uv = (u, v)

    def card(bm, uv, c, size, mat):
        """Foliage card facing mostly up (the HOI4 camera looks down), random tilt and spin."""
        n = Vector((rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7), 1.0)).normalized()
        rot = n.to_track_quat("Z", "Y").to_matrix() @ Matrix.Rotation(rng.uniform(0, 6.283), 3, "Z")
        h = size / 2
        vs = [bm.verts.new(c + rot @ Vector(p)) for p in ((-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0))]
        f = bm.faces.new(vs)
        f.material_index = mat
        for loop, q in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[uv].uv = q

    def clump(bm, uv, centre, rx, rz, n, mat, size=(0.9, 1.3)):
        for _ in range(n):
            while True:
                p = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
                if p.length <= 1:
                    break
            card(bm, uv, centre + Vector((p.x * rx, p.y * rx, p.z * rz)), rng.uniform(*size), mat)

    def giant(bm, uv, height, trunk_r, roots, tiers, top, cards):
        """Trunk with buttress roots, branches to canopy clumps. tiers: [(z, count, ring radius, clump radius)]."""
        segs = 7
        tube(bm, uv, [(Vector((rng.uniform(-.04, .04), rng.uniform(-.04, .04), height * k / segs)),
                       trunk_r * (1 - 0.55 * k / segs)) for k in range(segs + 1)], 8, 0)
        for i in range(roots):
            a = 2 * math.pi * (i + rng.uniform(-.2, .2)) / roots
            out = Vector((math.cos(a), math.sin(a), 0))
            limb(bm, uv, out * trunk_r * 0.6 + Vector((0, 0, trunk_r * 2.2)), out * trunk_r * 3 + Vector((0, 0, -0.05)),
                 trunk_r * 0.35, trunk_r * 0.12, 0, sides=4, segs=2)
        clumps = []
        for z, count, ring, cr in tiers:
            for i in range(count):
                a = 2 * math.pi * (i + rng.uniform(-.25, .25)) / count + z
                c = Vector((math.cos(a) * ring, math.sin(a) * ring, z + rng.uniform(-.15, .15)))
                limb(bm, uv, Vector((0, 0, z - 0.45)), c, trunk_r * 0.35, trunk_r * 0.15, 0)
                clumps.append((c, cr))
        clumps.append((Vector((0, 0, top)), tiers[-1][3]))
        per = cards // len(clumps)
        for c, cr in clumps:
            clump(bm, uv, c, cr, cr * 0.35, per, 1)

    def box(bm, uv, lo, hi, mat):
        g = bmesh.ops.create_cube(bm, size=1.0)
        for v in g["verts"]:
            v.co = Vector(lo) + Vector((v.co.x + .5, v.co.y + .5, v.co.z + .5)) * (Vector(hi) - Vector(lo))
        for f in {f for v in g["verts"] for f in v.link_faces}:
            f.material_index = mat

    def dome(bm, uv, centre, r, mat=0):
        g = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=r, calc_uvs=True)
        bmesh.ops.delete(bm, geom=[w for w in g["verts"] if w.co.z < -1e-4], context="VERTS")
        for w in g["verts"]:
            if w.is_valid:
                w.co += Vector(centre)

    def lathe(bm, uv, base, profile, sides, mat, lean=(0, 0)):
        """Surface of revolution: profile [(z, r)] from bottom to top, leaning by (dx, dy) per unit height."""
        tube(bm, uv, [(Vector((base[0] + lean[0] * z, base[1] + lean[1] * z, z)), max(r, 0.01)) for z, r in profile], sides, mat)

    def mushroom(bm, uv, x, y, h, cap):
        lean = (rng.uniform(-.04, .04), rng.uniform(-.04, .04))
        s = cap * 0.16
        lathe(bm, uv, (x, y), [(0, s * 1.6), (0.15 * h, s * 1.1), (0.6 * h, s), (h, s * 0.9)], 9, 0, lean)
        top = (x + lean[0] * h, y + lean[1] * h)
        # cap: underside from the stalk out to the rim, then over the crown (texture v follows the profile)
        lathe(bm, uv, top, [(h - 0.02, s * 0.9), (h + 0.05 * cap, cap * 0.6), (h + 0.02 * cap, cap * 0.97),
                            (h + 0.12 * cap, cap), (h + 0.3 * cap, cap * 0.8), (h + 0.42 * cap, cap * 0.45),
                            (h + 0.47 * cap, 0.02)], 14, 1)

    def bulb_stalk(bm, uv, x, y, h, r):
        lean = (rng.uniform(-.08, .08), rng.uniform(-.08, .08))
        lathe(bm, uv, (x, y), [(0, r * 0.9), (0.1 * h, r * 0.55), (0.55 * h, r * 0.45), (0.72 * h, r * 1.4),
                               (0.84 * h, r * 1.9), (0.95 * h, r * 1.1), (h, 0.02)], 8, 0, lean)

    def frond(bm, uv, a, length, width, curl):
        """Ribbon rising from the ground, arching outward and curling at the tip; built twice with opposite winding
        so both sides render (the map renderer culls back faces)."""
        for back in (False, True):
            ribbon(bm, uv, a, length, width, curl, back)

    def ribbon(bm, uv, a, length, width, curl, back):
        out = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-math.sin(a), math.cos(a), 0))
        segs = 10
        bend = lambda t: (0.15 + curl * t ** 1.6) * math.pi       # 0 = straight up, 1 = curled right over
        c, prev = Vector((0, 0, 0)), None
        for k in range(segs + 1):
            t = k / segs
            if k:
                aj = bend((k - 1) / segs)
                c = c + (out * math.sin(aj) + Vector((0, 0, math.cos(aj)))) * length / segs
            w = width * (1 - 0.85 * t) * (0.6 + 0.4 * math.sin(math.pi * min(t * 1.3, 1)))
            row = [bm.verts.new(c - side * w), bm.verts.new(c + side * w)]
            if back:
                row.reverse()
            if prev:
                f = bm.faces.new((prev[0], prev[1], row[1], row[0]))
                f.material_index = 0
                for loop, q in zip(f.loops, ((0, (k - 1) / segs), (1, (k - 1) / segs), (1, t), (0, t))):
                    loop[uv].uv = q
            prev = row

    def felucia(bm, uv, kind):
        if kind == "fel_mushroom":
            # ~1.7x a vanilla tree: giant, but units (about 2 tall) must stay visible between them
            mushroom(bm, uv, 0, 0, 3.4, 1.6)
            for _ in range(3):
                a, d = rng.uniform(0, 6.283), rng.uniform(0.9, 1.4)
                mushroom(bm, uv, math.cos(a) * d, math.sin(a) * d, rng.uniform(0.8, 1.4), rng.uniform(0.35, 0.6))
        elif kind == "fel_bulbs":
            for i in range(7):
                a, d = rng.uniform(0, 6.283), (0 if i == 0 else rng.uniform(0.35, 1.0))
                bulb_stalk(bm, uv, math.cos(a) * d, math.sin(a) * d, rng.uniform(1.8, 3.4) * (1.2 if i == 0 else 1),
                           rng.uniform(0.12, 0.2))
        elif kind == "fel_pitcher":
            # outside up to the lip, then down the inner wall to the liquid: an open lathe shows nothing from above
            k = 0.6
            lathe(bm, uv, (0, 0), [(z * k, r * k) for z, r in ((0, 0.35), (0.4, 0.9), (1.4, 1.25), (2.4, 0.8), (3.1, 0.55),
                                   (3.6, 0.9), (3.75, 1.25), (3.62, 1.12), (3.4, 0.8), (3.15, 0.5), (3.05, 0.01))], 14, 0)
            for i in range(5):                              # leaves around the foot
                frond(bm, uv, 2 * math.pi * i / 5, 1.0, 0.22, 0.35)
        else:
            for i in range(9):
                frond(bm, uv, 2 * math.pi * (i + rng.uniform(-.3, .3)) / 9, rng.uniform(2.6, 3.6), rng.uniform(0.3, 0.45),
                      rng.uniform(0.35, 0.6))

    def raxus_flora(bm, uv, kind):
        if kind == "rax_tree":
            # ~1.4x a vanilla tree: tall bare trunk, the crown high up (units stay visible underneath)
            giant(bm, uv, 2.9, 0.13, 3, [(2.5, 4, 0.75, 0.75), (3.1, 3, 0.55, 0.7)], 3.6, 460)
        elif kind == "rax_tiered":
            for i in range(2):
                x, y = (0, 0) if i == 0 else (rng.uniform(0.8, 1.1), rng.uniform(-0.6, 0.6))
                h = 3.2 if i == 0 else 2.2
                tube(bm, uv, [(Vector((x, y, h * k / 5)), 0.09 * (1 - 0.6 * k / 5)) for k in range(6)], 6, 0)
                for z, rr in ((0.45, 0.42), (0.62, 0.5), (0.8, 0.42), (0.95, 0.3)):
                    a = rng.uniform(0, 6.283)
                    c = Vector((x + math.cos(a) * 0.18, y + math.sin(a) * 0.18, h * z))
                    limb(bm, uv, Vector((x, y, h * z - 0.25)), c, 0.04, 0.02, 0, sides=4, segs=1)
                    clump(bm, uv, c, rr * (h / 3.2), rr * 0.45, 42, 1, size=(0.45, 0.7))
        else:
            for _ in range(6):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.9)
                r = rng.uniform(0.3, 0.5)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.7)), r, r * 0.6, 26, 0, size=(0.35, 0.6))

    def junk_heap(bm, uv, kind):
        """Raxus Prime junk heap: a mound body (material 0: packed junk), clumps of cut-out junk cards over it like a
        tree's foliage (material 2) and plates, girders and drums sticking out (material 1). Six kinds, so the dump
        varies: (radius x, radius y, height, cards, pieces)."""
        RX, RY, H, cards, n = {"rp_heap_a": (2.1, 2.1, 0.8, 110, 14), "rp_heap_b": (1.6, 1.6, 1.9, 120, 16),
                               "rp_heap_c": (2.0, 1.8, 1.0, 100, 12), "rp_heap_ridge": (3.0, 1.1, 1.3, 150, 18),
                               "rp_heap_tangle": (1.9, 1.9, 0.5, 70, 34), "rp_heap_slabs": (2.0, 1.7, 0.7, 70, 6)}[kind]
        segs, sides = 5, 12
        rings = []
        for k in range(segs + 1):
            t = k / segs
            sh = math.cos(t * math.pi / 2) ** (0.6 if kind == "rp_heap_b" else 1.0)
            z = H * math.sin(t * math.pi / 2) - 0.15
            rings.append([bm.verts.new((math.cos(a) * (RX * sh + 0.02) * rng.uniform(0.8, 1.2),
                                        math.sin(a) * (RY * sh + 0.02) * rng.uniform(0.8, 1.2), z + rng.uniform(-0.1, 0.15) * (k > 0)))
                          for a in (2 * math.pi * i / sides for i in range(sides))])
        for k in range(segs):
            for i in range(sides):
                j = (i + 1) % sides
                f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
                f.material_index = 0
                for loop, (u, v) in zip(f.loops, ((i / sides, k / segs), ((i + 1) / sides, k / segs),
                                                  ((i + 1) / sides, (k + 1) / segs), (i / sides, (k + 1) / segs))):
                    loop[uv].uv = (u, v)

        def on_heap(spread=1.0):
            a, t = rng.uniform(0, 6.283), rng.uniform(0.0, 0.95)
            sh = math.cos(t * math.pi / 2) * spread
            return Vector((math.cos(a) * RX * sh, math.sin(a) * RY * sh, H * math.sin(t * math.pi / 2) - 0.1)), a

        for _ in range(cards):                           # junk clumps: the heap's ragged, organic silhouette
            c, _a = on_heap(1.05)
            card(bm, uv, c + Vector((0, 0, rng.uniform(0.0, 0.25))), rng.uniform(0.5, 1.1), 2)

        def plate(c, w, d, th, tilt, spin):
            g = bmesh.ops.create_cube(bm, size=1.0)
            m = Matrix.Translation(c) @ Matrix.Rotation(spin, 4, "Z") @ Matrix.Rotation(tilt, 4, "X") @ \
                Matrix.Diagonal((w, d, th, 1.0))
            bmesh.ops.transform(bm, matrix=m, verts=g["verts"])
            for f in {f for v in g["verts"] for f in v.link_faces}:
                f.material_index = 1
                for loop, q in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                    loop[uv].uv = q

        girders = 0.85 if kind == "rp_heap_tangle" else 0.35
        for _ in range(n):
            c, a = on_heap()
            p = rng.random()
            if p < 1 - girders - 0.15:
                plate(c, rng.uniform(0.4, 1.0), rng.uniform(0.3, 0.7), 0.05, rng.uniform(0.3, 1.3), rng.uniform(0, 6.283))
            elif p < 0.85:
                d = Vector((math.cos(a) * rng.uniform(0.2, 1.0), math.sin(a) * rng.uniform(0.2, 1.0), rng.uniform(0.2, 1.0)))
                limb(bm, uv, c - d * 0.3, c + d.normalized() * rng.uniform(0.6, 1.6), rng.uniform(0.04, 0.08),
                     rng.uniform(0.03, 0.06), 1, sides=4, segs=1)
            else:
                r = rng.uniform(0.15, 0.25)
                tube(bm, uv, [(c + Vector((0, 0, -0.1)), r), (c + Vector((0, 0, rng.uniform(0.3, 0.55))), r)], 8, 1)
        if kind == "rp_heap_c":                          # a big hull plate and a stack of drums at its foot
            plate(Vector((0.5, -0.3, 0.6)), 2.0, 1.2, 0.08, 0.9, 0.4)
            for k in range(3):
                tube(bm, uv, [(Vector((-1.6 + 0.4 * k, 1.0, 0.0)), 0.2), (Vector((-1.6 + 0.4 * k, 1.0, 0.5)), 0.2)], 8, 1)
        if kind == "rp_heap_slabs":                      # big hull slabs leaning on each other
            for k in range(5):
                a = rng.uniform(0, 6.283)
                plate(Vector((math.cos(a) * 0.8, math.sin(a) * 0.8, 0.5)), rng.uniform(1.2, 2.0), rng.uniform(0.8, 1.3),
                      0.08, rng.uniform(0.7, 1.2), a + math.pi / 2)

    def korriban_flora(bm, uv, kind):
        if kind == "kor_spires":                        # needle spires: tall thin cones, leaning a little
            for i in range(rng.randint(4, 7)):
                a, d = rng.uniform(0, 6.283), (0 if i == 0 else rng.uniform(0.4, 1.3))
                h, r = rng.uniform(2.4, 4.8) * (1.15 if i == 0 else 0.8), rng.uniform(0.3, 0.55)
                lean = (rng.uniform(-.06, .06), rng.uniform(-.06, .06))
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.3, r * 1.2), (0.3 * h, r * 0.75), (0.65 * h, r * 0.4),
                                                                    (h, 0.01)], 6, 0, lean)
        else:                                           # broken columns, a toppled statue, rubble
            for i in range(3):
                a, d = rng.uniform(0, 6.283), rng.uniform(0.3, 1.0)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, 0.2), (rng.uniform(0.4, 1.6), 0.18)], 8, 1)
            limb(bm, uv, Vector((-1.0, 0.3, 0.15)), Vector((0.6, -0.4, 0.35)), 0.28, 0.2, 1, sides=8, segs=2)
            for _ in range(5):
                c = Vector((rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), 0.0))
                lathe(bm, uv, (c.x, c.y), [(-0.1, rng.uniform(0.12, 0.25)), (0.18, 0.12), (0.25, 0.01)], 5, 0)

    def planet_flora(bm, uv, kind):
        """Dromund Kaas, Zygerria and Cantonica floras (PROCEDURAL 81-91). Mat 0 = bark, 1 = foliage (one-material kinds: 0)."""
        def crooked(base, direction, length, r0, parts=3, kink=0.35):
            """a crooked limb: `parts` straight pieces, each turned a little; returns the tip"""
            p, d = base, direction.normalized()
            for i in range(parts):
                d = (d + Vector((rng.uniform(-kink, kink), rng.uniform(-kink, kink), rng.uniform(-kink * 0.5, kink * 0.7)))).normalized()
                q = p + d * (length / parts)
                limb(bm, uv, p, q, r0 * (1 - 0.6 * i / parts), r0 * (1 - 0.6 * (i + 1) / parts), 0, sides=5, segs=1)
                p = q
            return p
        if kind == "dk_swamp_tree":
            h = 2.0                                                         # short massive trunk, flared into the water
            tube(bm, uv, [(Vector((0, 0, -0.3)), 0.62), (Vector((0, 0, 0.25)), 0.4), (Vector((0.05, 0, h * 0.6)), 0.3),
                          (Vector((0.1, 0.05, h)), 0.24)], 9, 0)
            for i in range(6):                                              # buttress roots arching into the water
                a = 2 * math.pi * (i + rng.uniform(-.2, .2)) / 6
                out = Vector((math.cos(a), math.sin(a), 0))
                limb(bm, uv, out * 0.2 + Vector((0, 0, 0.7)), out * rng.uniform(1.0, 1.4) + Vector((0, 0, -0.3)), 0.16, 0.06, 0, sides=4, segs=2)
            for i in range(6):                                              # long, near-level crooked limbs: a wide tree
                a = 2 * math.pi * (i + rng.uniform(-.3, .3)) / 6
                tip = crooked(Vector((0.1, 0.05, h * rng.uniform(0.7, 0.95))), Vector((math.cos(a), math.sin(a), rng.uniform(0.05, 0.3))),
                              rng.uniform(2.0, 2.8), 0.18, parts=4, kink=0.3)
                clump(bm, uv, tip + Vector((0, 0, 0.2)), rng.uniform(0.7, 0.95), 0.22, 30, 1, size=(0.7, 1.0))   # flat lobe
            clump(bm, uv, Vector((0.1, 0.05, h + 0.5)), 0.6, 0.25, 18, 1, size=(0.7, 1.0))   # small lobe over the trunk
        elif kind == "dk_jungle_tree":
            giant(bm, uv, 3.0, 0.2, 4, [(2.4, 5, 0.9, 0.95), (3.0, 4, 0.6, 0.85)], 3.7, 520)
        elif kind == "dk_dead_snag":
            top = crooked(Vector((0, 0, -0.2)), Vector((0, 0, 1)), 2.6, 0.2, parts=4, kink=0.18)
            for z in (1.2, 1.7, 2.1):
                a = rng.uniform(0, 6.283)
                crooked(Vector((0, 0, z)), Vector((math.cos(a), math.sin(a), 0.4)), rng.uniform(0.6, 1.0), 0.07, parts=2)
            for _ in range(3):                                              # moss on the broken top and a fork
                clump(bm, uv, top + Vector((rng.uniform(-.3, .3), rng.uniform(-.3, .3), -rng.uniform(0, 0.8))), 0.25, 0.15, 6, 1, size=(0.3, 0.5))
        elif kind == "dk_root_tangle":
            for i in range(9):                                              # arching roots from a low stump
                a = 2 * math.pi * (i + rng.uniform(-.3, .3)) / 9
                out = Vector((math.cos(a), math.sin(a), 0))
                mid = out * rng.uniform(0.5, 0.8) + Vector((0, 0, rng.uniform(0.45, 0.75)))
                limb(bm, uv, Vector((0, 0, 0.5)), mid, 0.11, 0.08, 0, sides=4, segs=1)
                limb(bm, uv, mid, out * rng.uniform(1.1, 1.5) + Vector((0, 0, -0.25)), 0.08, 0.04, 0, sides=4, segs=1)
            tube(bm, uv, [(Vector((0, 0, -0.2)), 0.3), (Vector((0, 0, 0.6)), 0.18)], 7, 0)
            for _ in range(4):                                              # ferns between the roots
                a, d = rng.uniform(0, 6.283), rng.uniform(0.6, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.2)), 0.35, 0.15, 10, 1, size=(0.35, 0.55))
        elif kind == "dk_reeds":
            for _ in range(7):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.0)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.25)), 0.3, 0.25, 14, 0, size=(0.3, 0.5))
        elif kind == "canto_chinar":
            top = crooked(Vector((0, 0, -0.2)), Vector((0.2, 0, 1)), 2.4, 0.16, parts=4, kink=0.3)
            clump(bm, uv, top + Vector((0, 0, 0.1)), 0.55, 0.12, 22, 1, size=(0.45, 0.7))     # the crown pad
            for i in range(7):                                              # branches stepping up, a flat pad on each:
                a = 2.4 * i + rng.uniform(-.3, .3)                         # long low ones, short high ones (bonsai)
                tip = crooked(Vector((0.1, 0, 0.6 + 0.25 * i)), Vector((math.cos(a), math.sin(a), 0.12)),
                              (1.5 - 0.15 * i) * rng.uniform(0.85, 1.1), 0.07, parts=2, kink=0.15)
                clump(bm, uv, tip + Vector((0, 0, 0.06)), 0.5 - 0.03 * i, 0.08, 16, 1, size=(0.35, 0.55))
        elif kind == "canto_cactus":
            def column(x, y, h, r, arms):
                tube(bm, uv, [(Vector((x, y, -0.2)), r), (Vector((x, y, h - r)), r), (Vector((x, y, h - r * 0.3)), r * 0.7),
                              (Vector((x, y, h)), r * 0.15)], 8, 0, vrep=2.0)
                for _ in range(arms):                                        # arms: out, then up
                    a, z = rng.uniform(0, 6.283), rng.uniform(0.35, 0.6) * h
                    out = Vector((math.cos(a), math.sin(a), 0))
                    p0 = Vector((x, y, z)) + out * r * 0.5
                    p1 = p0 + out * rng.uniform(0.25, 0.4) + Vector((0, 0, 0.08))
                    limb(bm, uv, p0, p1, r * 0.6, r * 0.6, 0, sides=6, segs=1)
                    up = rng.uniform(0.3, 0.55)
                    tube(bm, uv, [(p1 - Vector((0, 0, r * 0.4)), r * 0.62), (p1 + Vector((0, 0, up)), r * 0.6),
                                  (p1 + Vector((0, 0, up + r * 0.4)), r * 0.12)], 7, 0)
            for i in range(rng.randint(3, 5)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0.3, 0.9) * (i > 0)
                column(math.cos(a) * d, math.sin(a) * d, rng.uniform(1.6, 2.0) if i == 0 else rng.uniform(0.8, 1.6),
                       rng.uniform(0.13, 0.18), 2 if i == 0 else rng.randint(0, 1))
            for _ in range(rng.randint(2, 4)):                               # barrel cacti
                a, d, r = rng.uniform(0, 6.283), rng.uniform(0.6, 1.3), rng.uniform(0.15, 0.24)
                x, y = math.cos(a) * d, math.sin(a) * d
                tube(bm, uv, [(Vector((x, y, -0.1)), r), (Vector((x, y, r * 0.9)), r * 1.05), (Vector((x, y, r * 1.5)), r * 0.15)], 8, 0)
        elif kind == "canto_scrub":
            for _ in range(8):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                r = rng.uniform(0.25, 0.45)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.5)), r, r * 0.45, 18, 0, size=(0.3, 0.5))
        elif kind == "canto_rubble":
            a = rng.uniform(0, 6.283)                                      # the broken obelisk: tapered, leaning
            lathe(bm, uv, (0.0, 0.0), [(-0.3, 0.32), (1.6, 0.24), (1.75, 0.2)], 4, 0, (math.cos(a) * 0.12, math.sin(a) * 0.12))
            for i in range(2):                                              # pylon blocks, tilted half into the sand
                b_ = a + 2.2 + 2.0 * i
                c = Vector((math.cos(b_), math.sin(b_), 0.0)) * rng.uniform(0.8, 1.2)
                w = rng.uniform(0.3, 0.5)
                lathe(bm, uv, (c.x, c.y), [(-0.4, w), (rng.uniform(0.3, 0.6), w * 0.75)], 4, 0,
                      (rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4)))
            top = Vector((math.cos(a + 1.1) * 0.9, math.sin(a + 1.1) * 0.9, 0.12))   # its fallen top
            limb(bm, uv, top, top + Vector((math.cos(a + 0.6), math.sin(a + 0.6), 0.05)) * 0.9, 0.2, 0.15, 0, sides=4, segs=1)
            for _ in range(6):
                c = Vector((rng.uniform(-1.4, 1.4), rng.uniform(-1.4, 1.4), 0.0))
                lathe(bm, uv, (c.x, c.y), [(-0.1, rng.uniform(0.1, 0.2)), (0.15, 0.12), (0.22, 0.02)], 4, 0)
        elif kind == "bon_derrick":
            h = 3.2
            for i in range(4):                                              # the four legs, leaning in
                a = math.pi / 4 + i * math.pi / 2
                foot, head = Vector((math.cos(a) * 0.55, math.sin(a) * 0.55, -0.2)), Vector((math.cos(a) * 0.12, math.sin(a) * 0.12, h))
                limb(bm, uv, foot, head, 0.05, 0.035, 0, sides=4, segs=1)
                b_ = a + math.pi / 2
                for z in (0.7, 1.5, 2.3):                                   # cross braces between neighbouring legs
                    f = z / h
                    p0 = foot.lerp(head, f)
                    q = Vector((math.cos(b_) * 0.55, math.sin(b_) * 0.55, -0.2)).lerp(Vector((math.cos(b_) * 0.12, math.sin(b_) * 0.12, h)), f + 0.2)
                    limb(bm, uv, p0, q, 0.025, 0.025, 0, sides=3, segs=1)
            lathe(bm, uv, (0.0, 0.0), [(h - 0.05, 0.2), (h + 0.15, 0.2)], 4, 0)       # the crown block
            lathe(bm, uv, (0.9, -0.2), [(-0.2, 0.32), (0.45, 0.32), (0.55, 0.05)], 6, 0)   # pump house
            limb(bm, uv, Vector((0.9, -0.2, 0.15)), Vector((2.0, 0.6, 0.12)), 0.07, 0.07, 0, sides=5, segs=1)   # pipe
        elif kind == "bon_tanks":
            spots = [(0.0, 0.0, 0.55), (1.1, 0.35, 0.42), (-0.5, 1.0, 0.38), (0.6, -0.95, 0.32)]
            for x, y, r in spots[:rng.randint(3, 4)]:
                hh = rng.uniform(0.7, 1.1)
                lathe(bm, uv, (x, y), [(-0.2, r), (hh, r), (hh + 0.15 * r, r * 0.6), (hh + 0.25 * r, 0.02)], 10, 0)
            for (x0, y0, _), (x1, y1, _) in zip(spots, spots[1:3]):        # pipes between them
                limb(bm, uv, Vector((x0, y0, 0.35)), Vector((x1, y1, 0.35)), 0.05, 0.05, 0, sides=5, segs=1)
        elif kind == "bon_slag":
            for i in range(rng.randint(3, 5)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.0) * (i > 0)
                r = rng.uniform(0.5, 0.9) * (1.3 if i == 0 else 1.0)
                hh = r * rng.uniform(0.5, 0.75)
                c = (math.cos(a) * d, math.sin(a) * d)
                lathe(bm, uv, c, [(-0.2, r), (hh * 0.4, r * 0.8), (hh * 0.85, r * 0.35), (hh, 0.05)], 9, 0,
                      (rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1)))
        elif kind == "bon_stacks":
            lathe(bm, uv, (0.0, 0.0), [(-0.2, 0.55), (0.5, 0.55), (0.55, 0.4)], 4, 0)   # the small works
            for x, y, hh in ((0.25, 0.2, 2.6), (-0.3, -0.15, 2.0)):
                lathe(bm, uv, (x, y), [(0.3, 0.14), (hh, 0.1), (hh + 0.05, 0.12)], 8, 0)
        elif kind == "etti_tree":
            giant(bm, uv, 2.8, 0.17, 4, [(2.3, 5, 1.0, 0.95), (2.9, 3, 0.55, 0.8)], 3.3, 460)
        elif kind == "etti_burnt":
            for i in range(rng.randint(3, 5)):                              # charred snags, broken tops, a few limbs
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.0) * (i > 0)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.2))
                top = crooked(base, Vector((rng.uniform(-.2, .2), rng.uniform(-.2, .2), 1)), rng.uniform(1.0, 2.4),
                              rng.uniform(0.09, 0.15), parts=3, kink=0.15)
                if rng.random() < 0.6:
                    b_ = rng.uniform(0, 6.283)
                    crooked(top - Vector((0, 0, 0.4)), Vector((math.cos(b_), math.sin(b_), 0.3)), 0.5, 0.04, parts=2)
            for _ in range(rng.randint(2, 4)):                              # stumps and a fallen trunk
                a, d = rng.uniform(0, 6.283), rng.uniform(0.5, 1.3)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, 0.14), (0.2, 0.11), (0.26, 0.06)], 6, 0)
            a = rng.uniform(0, 6.283)
            limb(bm, uv, Vector((-0.9, 0.2, 0.08)), Vector((-0.9 + 1.6 * math.cos(a), 0.2 + 1.6 * math.sin(a), 0.12)),
                 0.11, 0.07, 0, sides=5, segs=1)
        elif kind == "etti_grass":
            for _ in range(9):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.3)
                r = rng.uniform(0.25, 0.45)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.55)), r * 0.8, r * 0.6, 14, 0, size=(0.3, 0.5))
        elif kind == "etti_reeds":
            for _ in range(8):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.35)), 0.22, 0.4, 12, 0, size=(0.25, 0.45))
        elif kind == "ruu_tree":
            giant(bm, uv, 3.4, 0.2, 5, [(3.0, 5, 1.2, 1.1), (3.6, 3, 0.6, 0.9)], 4.0, 520)
        elif kind == "ruu_fern":
            for i in range(rng.randint(2, 3)):                              # slim trunks, a rosette of fronds on top
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.7) * (i > 0)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.2))
                top = crooked(base, Vector((0, 0, 1)), rng.uniform(1.0, 1.8), 0.07, parts=2, kink=0.12)
                clump(bm, uv, top + Vector((0, 0, 0.1)), 0.6, 0.15, 14, 1, size=(0.5, 0.8))
        elif kind == "ruu_cocoons":
            clump(bm, uv, Vector((0, 0, 0.5)), 1.0, 0.45, 26, 1, size=(0.4, 0.7))   # the thicket
            for _ in range(rng.randint(3, 5)):                              # silk cocoons in it
                a, d = rng.uniform(0, 6.283), rng.uniform(0.2, 0.9)
                c = Vector((math.cos(a) * d, math.sin(a) * d, rng.uniform(0.4, 0.9)))
                tube(bm, uv, [(c + Vector((0, 0, -0.32)), 0.03), (c + Vector((0, 0, -0.2)), 0.13), (c, 0.16),
                              (c + Vector((0, 0, 0.2)), 0.12), (c + Vector((0, 0, 0.3)), 0.02)], 8, 0)
        elif kind == "ruu_reeds":
            for _ in range(8):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.35)), 0.22, 0.42, 12, 0, size=(0.25, 0.45))
        elif kind == "oss_bamboo":
            for _ in range(rng.randint(9, 14)):                             # culms: tall, thin, leaning a little
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.8)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.2))
                top = base + Vector((rng.uniform(-.25, .25), rng.uniform(-.25, .25), rng.uniform(2.2, 3.4)))
                limb(bm, uv, base, top, 0.045, 0.03, 0, sides=5, segs=2)
                clump(bm, uv, top - Vector((0, 0, 0.3)), 0.35, 0.45, 6, 1, size=(0.35, 0.55))
        elif kind == "oss_uneti":
            giant(bm, uv, 2.2, 0.32, 6, [(1.9, 6, 1.5, 1.1), (2.5, 3, 0.7, 1.0)], 2.9, 520)
        elif kind == "oss_wodobo":
            for _ in range(7):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.1)
                r = rng.uniform(0.3, 0.5)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.6)), r, r * 0.55, 18, 0, size=(0.35, 0.55))
        elif kind == "oss_rubble":
            a = rng.uniform(0, 6.283)                                       # a toppled column in pieces
            for i in range(3):
                c = Vector((math.cos(a) * 0.55 * i - 0.5, math.sin(a) * 0.55 * i, 0.12))
                limb(bm, uv, c, c + Vector((math.cos(a), math.sin(a), 0)) * 0.48, 0.14, 0.14, 0, sides=8, segs=1)
            lathe(bm, uv, (0.6, -0.5), [(-0.3, 0.3), (0.5, 0.26)], 8, 0)    # a standing stump
            for _ in range(6):
                c = Vector((rng.uniform(-1.3, 1.3), rng.uniform(-1.3, 1.3), 0.0))
                lathe(bm, uv, (c.x, c.y), [(-0.1, rng.uniform(0.12, 0.22)), (0.18, 0.14), (0.25, 0.03)], 4, 0)
        elif kind == "lola_vent":
            for i in range(rng.randint(2, 3)):                              # cones with a crater dip on top
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.9) * (i > 0)
                r, h = rng.uniform(0.5, 0.8) * (1.0 if i == 0 else 0.7), rng.uniform(0.6, 1.0) * (1.0 if i == 0 else 0.7)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (h * 0.7, r * 0.45), (h, r * 0.3),
                                                                     (h * 0.8, r * 0.15)], 9, 0)
        elif kind == "lola_shards":
            for _ in range(rng.randint(4, 7)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.1)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, rng.uniform(0.12, 0.25)), (rng.uniform(0.5, 1.5), 0.02)],
                      4, 0, (rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25)))
        elif kind == "rv_pillars":
            for i in range(rng.randint(3, 5)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.9) * (i > 0)
                h, r = rng.uniform(1.4, 2.8) * (1.0 if i == 0 else 0.75), rng.uniform(0.18, 0.3)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r * 1.4), (h * 0.3, r), (h * 0.75, r * 0.85),
                                                                     (h, r * 1.15), (h * 1.05, r * 0.6)], 7, 0)
        elif kind == "rv_arch":
            for x in (-0.8, 0.8):
                lathe(bm, uv, (x, 0.0), [(-0.2, 0.32), (1.2, 0.26), (1.5, 0.3)], 7, 0)
            pts = [Vector((-0.8 + 1.6 * i / 6, 0.0, 1.4 + 0.45 * math.sin(math.pi * i / 6))) for i in range(7)]
            for a_, b_ in zip(pts, pts[1:]):
                limb(bm, uv, a_, b_, 0.2, 0.2, 0, sides=6, segs=1)
        elif kind == "rv_tree":
            giant(bm, uv, 2.2, 0.15, 3, [(1.8, 5, 0.75, 0.85), (2.4, 3, 0.4, 0.75)], 2.8, 380)
        elif kind == "rh_ice":
            for _ in range(rng.randint(5, 8)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.0)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, rng.uniform(0.1, 0.22)), (rng.uniform(0.4, 1.3), 0.02)],
                      5, 0, (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)))
        elif kind == "rh_ruin":
            lathe(bm, uv, (0.0, 0.0), [(-0.3, 0.26), (rng.uniform(0.6, 1.2), 0.22)], 8, 0)            # a column stump
            box(bm, uv, (0.4, -0.6, -0.3), (1.2, -0.45, 0.6), 0)                                     # a wall corner
            box(bm, uv, (1.05, -0.6, -0.3), (1.2, 0.2, 0.45), 0)
            for _ in range(4):
                c = Vector((rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), 0.0))
                lathe(bm, uv, (c.x, c.y), [(-0.1, rng.uniform(0.12, 0.2)), (0.18, 0.13), (0.24, 0.03)], 4, 0)
        elif kind == "rh_deadtree":
            top = crooked(Vector((0, 0, -0.2)), Vector((0, 0, 1)), rng.uniform(1.8, 2.6), 0.13, parts=4, kink=0.2)
            for z in (0.9, 1.3, 1.7):
                a = rng.uniform(0, 6.283)
                crooked(Vector((0, 0, z)), Vector((math.cos(a), math.sin(a), 0.45)), rng.uniform(0.5, 0.9), 0.05, parts=2)
        elif kind == "sal_caketree":
            h = rng.uniform(2.6, 3.4)
            top = crooked(Vector((0, 0, -0.2)), Vector((0, 0, 1)), h, 0.1, parts=3, kink=0.06)
            for q, (r, dz) in enumerate(((0.95, -1.1), (0.75, -0.55), (0.5, 0.0))):   # stacked flat tiers
                c = top + Vector((0, 0, dz))
                for j in range(9):
                    a = 6.283 * j / 9 + q
                    clump(bm, uv, c + Vector((math.cos(a) * r * 0.6, math.sin(a) * r * 0.6, 0)), r * 0.45, 0.1, 4, 1,
                          size=(0.35, 0.55))
        elif kind == "sal_bith":
            for i in range(rng.randint(3, 5)):                              # ribbed fungal spires
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.8) * (i > 0)
                h, r = rng.uniform(1.8, 3.4) * (1.0 if i == 0 else 0.7), rng.uniform(0.18, 0.3)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r * 1.3), (h * 0.3, r), (h * 0.6, r * 1.1),
                                                                     (h * 0.85, r * 0.7), (h, r * 0.9), (h * 1.05, 0.02)],
                      8, 0, (rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06)))
        elif kind == "sal_reeds":
            for _ in range(9):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.35)), 0.2, 0.45, 12, 0, size=(0.25, 0.45))
        elif kind == "tel_blba":
            top = crooked(Vector((0, 0, -0.2)), Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), 1)),
                          rng.uniform(1.0, 1.4), 0.13, parts=3, kink=0.3)
            for j in range(6):                                              # thorny limbs under a low broad crown
                a = 6.283 * j / 6 + rng.uniform(-0.3, 0.3)
                tip = crooked(top - Vector((0, 0, 0.25)), Vector((math.cos(a), math.sin(a), 0.35)), rng.uniform(0.6, 0.9),
                              0.05, parts=2, kink=0.35)
                for _ in range(3):                                          # the thorns
                    limb(bm, uv, tip, tip + Vector((rng.uniform(-.2, .2), rng.uniform(-.2, .2), rng.uniform(-.1, .15))),
                         0.02, 0.003, 0, sides=3, segs=1)
                clump(bm, uv, tip + Vector((0, 0, 0.1)), 0.45, 0.25, 8, 1, size=(0.35, 0.6))
            clump(bm, uv, top + Vector((0, 0, 0.05)), 0.55, 0.25, 10, 1, size=(0.35, 0.6))
        elif kind == "tel_bachani":
            for _ in range(12):                                             # a bed of low flowering clumps
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.3)
                r = rng.uniform(0.18, 0.3)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.6)), r, r * 0.5, 10, 0, size=(0.2, 0.35))
        elif kind == "ser_tree":
            giant(bm, uv, rng.uniform(2.2, 2.7), 0.15, 3, [(1.9, 5, 0.8, 0.9), (2.5, 4, 0.45, 0.8)], 3.0, 400)
        elif kind == "ser_pine":
            h = rng.uniform(2.8, 3.6)
            limb(bm, uv, Vector((0, 0, -0.2)), Vector((0, 0, h)), 0.1, 0.03, 0, sides=6, segs=3)
            for q in range(6):                                              # tiers narrowing to the tip
                z, r = 0.7 + q * (h - 0.8) / 6, 0.85 * (1 - q / 6.5)
                clump(bm, uv, Vector((0, 0, z)), r, 0.22, 9, 1, size=(0.3, 0.5))
            clump(bm, uv, Vector((0, 0, h)), 0.15, 0.25, 3, 1, size=(0.25, 0.35))
        elif kind == "yav_massassi":
            giant(bm, uv, rng.uniform(3.4, 4.0), 0.22, 6, [(3.0, 5, 1.2, 1.0), (3.7, 4, 0.7, 0.95)], 4.2, 560)
        elif kind == "yav_fern":
            for _ in range(rng.randint(5, 7)):                              # fern clumps, a few on short stems
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.1)
                c = Vector((math.cos(a) * d, math.sin(a) * d, 0.0))
                h = rng.choice((0.0, 0.0, rng.uniform(0.5, 1.0)))
                if h:
                    limb(bm, uv, c - Vector((0, 0, 0.2)), c + Vector((0, 0, h)), 0.05, 0.03, 0, sides=4, segs=1)
                clump(bm, uv, c + Vector((0, 0, h + 0.25)), 0.4, 0.25, 9, 1, size=(0.35, 0.6))
        elif kind == "yav_ruin":
            for q in range(3):                                              # a stepped block fragment
                w = 0.9 - q * 0.28
                box(bm, uv, (-w, -w * 0.8, -0.3 + q * 0.3), (w, w * 0.8, q * 0.3), 0)
            a = rng.uniform(0, 6.283)                                       # a toppled pillar beside it
            c = Vector((math.cos(a) * 1.3, math.sin(a) * 1.3, 0.12))
            limb(bm, uv, c, c + Vector((math.cos(a + 1.4), math.sin(a + 1.4), 0.05)) * 1.1, 0.16, 0.15, 0, sides=8, segs=1)
            for _ in range(5):                                              # vines and moss over the stones
                b = rng.uniform(0, 6.283)
                clump(bm, uv, Vector((math.cos(b) * 0.7, math.sin(b) * 0.6, rng.uniform(0.1, 0.6))), 0.35, 0.25, 6, 1,
                      size=(0.3, 0.5))
        elif kind == "cel_tree":
            h = rng.uniform(2.6, 3.4)
            limb(bm, uv, Vector((0, 0, -0.2)), Vector((0, 0, h)), 0.1, 0.04, 0, sides=6, segs=3)
            for q in range(5):                                              # a narrow crown along the trunk
                clump(bm, uv, Vector((0, 0, 0.9 + q * (h - 0.9) / 5)), 0.42 - 0.04 * q, 0.35, 10, 1, size=(0.35, 0.55))
        elif kind == "cel_grass":
            for _ in range(10):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.3)), 0.22, 0.38, 10, 0, size=(0.25, 0.45))
        elif kind == "bot_tanks":
            for _ in range(rng.randint(3, 5)):                              # squat storage tanks
                a, d = rng.uniform(0, 6.283), rng.uniform(0.5, 1.2)
                r = rng.uniform(0.3, 0.45)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (r * 1.4, r), (r * 1.6, r * 0.7),
                                                                     (r * 1.65, 0.02)], 10, 0)
            lathe(bm, uv, (0.0, 0.0), [(-0.2, 0.25), (1.8, 0.22), (1.9, 0.1)], 8, 0)      # a tall one
            for _ in range(2):                                              # a pipe run
                b = rng.uniform(0, 6.283)
                limb(bm, uv, Vector((0, 0, 0.3)), Vector((math.cos(b) * 1.3, math.sin(b) * 1.3, 0.3)), 0.06, 0.06, 0,
                     sides=5, segs=1)
        elif kind == "axx_spoil":
            for _ in range(rng.randint(3, 5)):                              # spoil heaps
                a, d = rng.uniform(0, 6.283), rng.uniform(0.4, 1.2)
                r = rng.uniform(0.35, 0.6)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (r * 0.5, r * 0.55), (r * 0.8, 0.03)], 7, 0)
            for i in range(3):                                              # the drill rig: a tripod and a cab
                b = 6.283 * i / 3
                limb(bm, uv, Vector((math.cos(b) * 0.35, math.sin(b) * 0.35, -0.1)), Vector((0, 0, 1.6)), 0.04, 0.03, 1,
                     sides=4, segs=1)
            box(bm, uv, (-0.15, -0.15, 0.0), (0.15, 0.15, 0.35), 1)
        elif kind == "cit_tree":
            giant(bm, uv, rng.uniform(1.8, 2.3), 0.17, 4, [(1.5, 6, 0.85, 0.85), (2.1, 4, 0.5, 0.8)], 2.6, 420)
        elif kind == "dub_tree":
            giant(bm, uv, rng.uniform(2.2, 2.8), 0.15, 3, [(1.7, 5, 0.75, 0.95), (2.3, 3, 0.4, 0.9)], 2.7, 460)
        elif kind == "bas_tree":
            giant(bm, uv, rng.uniform(2.0, 2.5), 0.17, 3, [(1.5, 6, 0.8, 0.9), (2.1, 3, 0.4, 0.85)], 2.4, 440)
        elif kind == "kal_jungle":
            giant(bm, uv, rng.uniform(2.6, 3.4), 0.16, 4, [(2.0, 6, 0.9, 1.0), (2.6, 3, 0.45, 0.9)], 3.0, 480)
        elif kind == "muun_tree":
            giant(bm, uv, rng.uniform(3.0, 3.8), 0.1, 2, [(1.9, 4, 0.4, 0.6), (2.6, 4, 0.35, 0.55), (3.2, 2, 0.15, 0.5)],
                  3.6, 400)
        elif kind == "yag_tree":
            giant(bm, uv, rng.uniform(2.6, 3.2), 0.15, 3, [(1.8, 5, 0.8, 0.95), (2.5, 3, 0.45, 0.85)], 2.9, 460)
        elif kind == "myg_spur":
            for i in range(rng.randint(4, 7)):                              # leaning hexagonal spurs from one root
                a, lean = rng.uniform(0, 6.283), rng.uniform(0.0, 0.6) * (i > 0)
                h, r = rng.uniform(1.0, 2.6) * (1.0 if i == 0 else 0.7), rng.uniform(0.12, 0.25)
                base = Vector((math.cos(a) * r, math.sin(a) * r, -0.3))
                tip = base + Vector((math.cos(a) * lean * h, math.sin(a) * lean * h, h))
                limb(bm, uv, base, tip - base, r, r * 0.9, 0, sides=6, segs=1)
                limb(bm, uv, tip, (tip - base) * 0.2, r * 0.9, 0.01, 1, sides=6, segs=1)
        elif kind == "yag_rock":
            for i in range(rng.randint(2, 4)):                              # boulders, moss on their crowns
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.9) * (i > 0)
                h, r = rng.uniform(0.5, 1.1), rng.uniform(0.4, 0.7)
                c = (math.cos(a) * d, math.sin(a) * d)
                lathe(bm, uv, c, [(-0.3, r), (h * 0.6, r * 0.9)], 7, 0)
                lathe(bm, uv, c, [(h * 0.6, r * 0.92), (h * 0.9, r * 0.55), (h, 0.05)], 7, 1)
        elif kind == "ilu_shard":
            for i in range(rng.randint(5, 9)):                              # thin leaning shards
                a, lean = rng.uniform(0, 6.283), rng.uniform(0.0, 0.5) * (i > 0)
                h, r = rng.uniform(0.6, 1.8), rng.uniform(0.07, 0.15)
                base = Vector((math.cos(a) * rng.uniform(0.0, 0.8), math.sin(a) * rng.uniform(0.0, 0.8), -0.2))
                tip = base + Vector((math.cos(a) * lean * h, math.sin(a) * lean * h, h))
                limb(bm, uv, base, tip - base, r, r * 0.8, 0, sides=5, segs=1)
                limb(bm, uv, tip, (tip - base) * 0.25, r * 0.8, 0.01, 1, sides=5, segs=1)
        elif kind == "ilu_pine":
            h = rng.uniform(2.4, 3.4)                                       # a trunk under tiered snowy cones
            lathe(bm, uv, (0, 0), [(-0.2, 0.1), (h * 0.4, 0.08)], 5, 0)
            for i in range(4):
                z0, r = h * (0.25 + 0.17 * i), 0.9 * (1 - 0.2 * i)
                lathe(bm, uv, (0, 0), [(z0, r), (z0 + h * 0.3, 0.02)], 8, 1)
        elif kind == "dor_kand":
            giant(bm, uv, rng.uniform(1.4, 1.8), 0.14, 3, [(1.1, 5, 0.75, 0.7)], 1.7, 380)
        elif kind == "yin_spire":
            for i in range(rng.randint(1, 3)):                              # rock needles: stacked, eroded drums
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.0) * (i > 0)
                h, r = rng.uniform(1.6, 3.2) * (1 - 0.3 * (i > 0)), rng.uniform(0.3, 0.5)
                c = (math.cos(a) * d, math.sin(a) * d)
                lathe(bm, uv, c, [(-0.3, r * 1.3), (h * 0.3, r), (h * 0.45, r * 0.8), (h * 0.6, r * 0.9), (h * 0.85, r * 0.55)], 6, 0)
                lathe(bm, uv, c, [(h * 0.85, r * 0.6), (h, 0.05)], 6, 1)
        elif kind == "yin_thorn":
            giant(bm, uv, rng.uniform(0.8, 1.1), 0.08, 3, [(0.75, 4, 0.9, 0.35)], 1.3, 220)
        elif kind == "cha_sienta":
            giant(bm, uv, rng.uniform(2.0, 2.5), 0.17, 3, [(1.4, 5, 0.8, 0.75), (2.0, 4, 0.5, 0.65)], 2.5, 440)
        elif kind == "cha_balm":
            for i in range(rng.randint(5, 8)):                              # tufts of balmgrass
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.3)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, rng.uniform(0.2, 0.35))), rng.uniform(0.2, 0.35),
                      rng.uniform(0.3, 0.45), 7, 0, size=(0.15, 0.35))
        elif kind == "cor_bamboo":
            for i in range(rng.randint(6, 10)):                             # a stand of canes, leaf tufts up top
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.9)
                c, h = (math.cos(a) * d, math.sin(a) * d), rng.uniform(2.0, 3.4)
                lathe(bm, uv, c, [(-0.2, 0.07), (h * 0.5, 0.065), (h * 0.52, 0.08), (h * 0.54, 0.065), (h, 0.04)], 5, 0)
                clump(bm, uv, Vector((c[0], c[1], h * 0.9)), 0.3, 0.35, 6, 1, size=(0.12, 0.3))
        elif kind == "ark_ice":
            for i in range(rng.randint(2, 4)):                              # ice crags with bright glints
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.9) * (i > 0)
                h, r = rng.uniform(0.8, 2.2), rng.uniform(0.25, 0.45)
                c = (math.cos(a) * d, math.sin(a) * d)
                lathe(bm, uv, c, [(-0.3, r * 1.2), (h * 0.6, r * 0.8), (h * 0.8, r * 0.4)], 5, 0)
                lathe(bm, uv, c, [(h * 0.8, r * 0.42), (h, 0.02)], 5, 1)
        elif kind == "anx_red":
            for i in range(rng.randint(1, 3)):                              # giant flowers: stalk, open bloom of petals
                a, d = rng.uniform(0, 6.283), rng.uniform(0.4, 1.0) * (i > 0)
                bx, by, h = math.cos(a) * d, math.sin(a) * d, rng.uniform(2.6, 4.0) * (1 - 0.25 * (i > 0))
                lean = (rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08))
                lathe(bm, uv, (bx, by), [(-0.2, 0.14), (h * 0.5, 0.1), (h, 0.12)], 6, 0, lean=lean)
                top = Vector((bx + lean[0] * h, by + lean[1] * h, h))
                lathe(bm, uv, (top.x, top.y), [(h - 0.1, 0.14), (h + 0.2, 0.35), (h + 0.3, 0.12)], 7, 1)   # the heart
                n = rng.randint(6, 8)
                for q in range(n):                                          # petals splayed out and up
                    b = 6.283 * q / n + rng.uniform(-0.15, 0.15)
                    tip = top + Vector((math.cos(b) * 1.3, math.sin(b) * 1.3, rng.uniform(0.35, 0.8)))
                    limb(bm, uv, top + Vector((0, 0, 0.1)), tip, 0.28, 0.06, 1, sides=3, segs=2)
        elif kind == "anx_bloom":
            for i in range(rng.randint(4, 7)):                              # lesser flowers: curved stalks, cupped blooms
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.1)
                bx, by, h = math.cos(a) * d, math.sin(a) * d, rng.uniform(0.9, 1.7)
                tip = Vector((bx + math.cos(a) * 0.35, by + math.sin(a) * 0.35, h))
                limb(bm, uv, Vector((bx, by, -0.2)), tip, 0.06, 0.04, 0, sides=4, segs=3)
                lathe(bm, uv, (tip.x, tip.y), [(h - 0.1, 0.06), (h + 0.15, 0.3), (h + 0.3, 0.38)], 6, 1)
        elif kind == "ess_palm":
            giant(bm, uv, rng.uniform(2.2, 2.8), 0.1, 0, [(2.2, 6, 0.6, 0.5)], 2.6, 300)
        elif kind == "dor_stone":
            for i in range(rng.randint(2, 4)):                              # standing pillars, lichen on top
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.9) * (i > 0)
                h, r = rng.uniform(0.9, 2.0), rng.uniform(0.18, 0.3)
                c = (math.cos(a) * d, math.sin(a) * d)
                lathe(bm, uv, c, [(-0.3, r), (h * 0.85, r * 0.75)], 5, 0)
                lathe(bm, uv, c, [(h * 0.85, r * 0.77), (h, 0.03)], 5, 1)
        elif kind == "ans_sanwi":
            giant(bm, uv, rng.uniform(1.6, 2.0), 0.18, 4, [(1.3, 6, 1.0, 0.7), (1.8, 4, 0.6, 0.6)], 2.0, 420)
        elif kind == "ans_grass":
            for i in range(rng.randint(5, 8)):                              # tufts of tall grass
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.3)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, rng.uniform(0.3, 0.5))), rng.uniform(0.25, 0.4),
                      rng.uniform(0.4, 0.6), 7, 0, size=(0.15, 0.4))
        elif kind == "kal_moss":
            for i in range(rng.randint(3, 5)):                              # rock spires, moss on their tops
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.0) * (i > 0)
                h, r = rng.uniform(1.0, 2.4), rng.uniform(0.25, 0.45)
                c = (math.cos(a) * d, math.sin(a) * d)
                lathe(bm, uv, c, [(-0.3, r * 1.2), (h * 0.7, r * 0.8)], 6, 0)
                lathe(bm, uv, c, [(h * 0.7, r * 0.82), (h * 0.9, r * 0.6), (h, 0.05)], 6, 1)
        elif kind == "muun_smoker":
            h, r = rng.uniform(1.2, 2.0), rng.uniform(0.7, 1.0)          # a vent cone, its mouth glowing
            lathe(bm, uv, (0, 0), [(-0.3, r), (h * 0.8, r * 0.3), (h, r * 0.18)], 9, 0)
            lathe(bm, uv, (0, 0), [(h - 0.02, r * 0.18), (h + 0.02, 0.02)], 9, 1)
            for _ in range(rng.randint(1, 3)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0.9, 1.4)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, 0.3), (0.4, 0.08), (0.45, 0.02)], 7, 0)
        elif kind == "aga_binka":
            for i in range(3):                                              # regularly spaced, row by row
                for j in range(3):
                    x, y = -1.0 + i * 1.0 + rng.uniform(-0.05, 0.05), -1.0 + j * 1.0 + rng.uniform(-0.05, 0.05)
                    h = rng.uniform(1.4, 1.8)
                    lathe(bm, uv, (x, y), [(-0.2, 0.07), (h, 0.05)], 5, 0)
                    clump(bm, uv, Vector((x, y, h + 0.15)), 0.38, 0.32, 9, 1, size=(0.3, 0.5))
        elif kind == "aga_arch":
            span, h, a = rng.uniform(1.6, 2.4), rng.uniform(1.0, 1.6), rng.uniform(0, 3.14)
            ax, ay = math.cos(a), math.sin(a)
            for s_ in (-1, 1):                                              # the two piers
                lathe(bm, uv, (ax * s_ * span / 2, ay * s_ * span / 2), [(-0.3, 0.42), (h * 0.6, 0.34), (h, 0.3)], 7, 0)
            pts = [(-span / 2 + span * t / 8, h + 0.35 * math.sin(math.pi * t / 8)) for t in range(9)]
            for (u0, z0), (u1, z1) in zip(pts, pts[1:]):                    # the span
                limb(bm, uv, Vector((ax * u0, ay * u0, z0)), Vector((ax * u1, ay * u1, z1)), 0.28, 0.28, 0, sides=6, segs=1)
            for _ in range(3):
                c = (rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2))
                lathe(bm, uv, c, [(-0.1, 0.2), (0.2, 0.15), (0.3, 0.02)], 5, 0)
        elif kind == "aga_grass":
            for _ in range(rng.randint(6, 9)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.3)
                r = rng.uniform(0.18, 0.3)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.4)), r, r * 0.5, 9, 0, size=(0.22, 0.45))
        elif kind == "ot_scrub":
            for _ in range(rng.randint(4, 7)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.3)
                r = rng.uniform(0.15, 0.28)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.35)), r, r * 0.45, 8, 0, size=(0.2, 0.38))
        elif kind == "dan_blba":
            giant(bm, uv, rng.uniform(2.6, 3.2), 0.12, 2, [(2.3, 5, 0.7, 0.8), (2.7, 3, 0.35, 0.75)], 2.9, 420)
        elif kind == "dan_grass":
            for _ in range(rng.randint(7, 10)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.3)
                r = rng.uniform(0.2, 0.32)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.6)), r, r * 0.8, 10, 0, size=(0.3, 0.55))
        elif kind == "om_pine":
            h = rng.uniform(2.2, 3.0)
            lathe(bm, uv, (0, 0), [(-0.2, 0.1), (h, 0.03)], 5, 0)
            for i in range(4):                                              # tiers narrowing upward
                z = h * (0.35 + 0.17 * i)
                clump(bm, uv, Vector((0, 0, z)), 0.55 * (1 - 0.2 * i), 0.25, 24, 1, size=(0.35, 0.65))
        elif kind == "om_scrub":
            for _ in range(rng.randint(5, 8)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.3)
                r = rng.uniform(0.15, 0.3)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.4)), r, r * 0.5, 8, 0, size=(0.2, 0.4))
        elif kind == "gar_bimiza":
            giant(bm, uv, rng.uniform(2.0, 2.6), 0.12, 2, [(1.7, 5, 0.6, 0.85), (2.2, 3, 0.35, 0.8)], 2.6, 420)
        elif kind == "gar_shrub":
            for _ in range(rng.randint(5, 8)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                r = rng.uniform(0.2, 0.35)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.5)), r, r * 0.6, 10, 0, size=(0.25, 0.45))
        elif kind == "gar_caf":
            for i in range(3):                                              # three planted rows
                for j in range(5):
                    clump(bm, uv, Vector((-1.0 + j * 0.5, -0.6 + i * 0.6, 0.25)), 0.2, 0.2, 5, 0, size=(0.2, 0.35))
        elif kind == "ith_cloud":
            for i in range(rng.randint(5, 8)):                              # soft lumps heaped into a bank
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.3) * (i > 0)
                r = rng.uniform(0.45, 0.85) * (1.2 if i == 0 else 1.0)
                z0 = rng.uniform(-0.2, 0.3)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(z0, r * 0.7), (z0 + r * 0.35, r), (z0 + r * 0.75, r * 0.8),
                                                                   (z0 + r * 1.0, r * 0.4), (z0 + r * 1.08, 0.02)], 9, 0)
        elif kind == "ith_nlor":
            giant(bm, uv, rng.uniform(2.6, 3.4), 0.16, 4, [(1.8, 5, 0.6, 0.9), (2.5, 4, 0.45, 0.85), (3.1, 2, 0.2, 0.7)],
                  3.4, 520)
        elif kind == "ith_barge":
            z = rng.uniform(2.2, 3.0)                                       # floating: nothing reaches the ground
            lathe(bm, uv, (0, 0), [(z - 0.35, 0.02), (z - 0.25, 0.5), (z, 0.75), (z + 0.08, 0.7)], 10, 0)
            clump(bm, uv, Vector((0, 0, z + 0.3)), 0.5, 0.25, 12, 1, size=(0.3, 0.5))
            lathe(bm, uv, (0.2, 0.1), [(z, 0.08), (z + 0.7, 0.05)], 5, 0)
        elif kind == "ith_fungus":
            for i in range(rng.randint(7, 11)):                             # blue and pink caps
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.3)
                h, r = rng.uniform(0.1, 0.35), rng.uniform(0.12, 0.3)
                c = (math.cos(a) * d, math.sin(a) * d)
                m = i % 2
                lathe(bm, uv, c, [(-0.1, 0.04), (h, 0.03)], 5, m)
                lathe(bm, uv, c, [(h - 0.04, 0.03), (h, r), (h + 0.06, r * 0.8), (h + 0.12, 0.02)], 8, m)
        elif kind == "man_galek":
            giant(bm, uv, rng.uniform(2.6, 3.2), 0.12, 2, [(1.6, 4, 0.5, 0.75), (2.3, 4, 0.4, 0.7), (2.9, 2, 0.2, 0.6)],
                  3.3, 420)
        elif kind == "man_amberfern":
            for _ in range(rng.randint(6, 9)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                r = rng.uniform(0.25, 0.4)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.45)), r, r * 0.5, 10, 0, size=(0.3, 0.55))
        elif kind == "man_varos":
            giant(bm, uv, rng.uniform(1.8, 2.4), 0.16, 4, [(1.9, 6, 0.8, 0.95), (2.3, 3, 0.4, 0.9)], 2.5, 460)
        elif kind == "boz_headstone":
            for i in range(rng.randint(4, 7)):                              # headstones and stelae, leaning
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.3) * (i > 0)
                x, y = math.cos(a) * d, math.sin(a) * d
                w, h = rng.uniform(0.18, 0.32), rng.uniform(0.5, 1.4)
                if rng.random() < 0.35:                                     # a tall stele with a three-faced finial
                    lathe(bm, uv, (x, y), [(-0.2, w), (h, w * 0.7), (h + 0.05, w * 0.95), (h + 0.35, 0.02)], 3, 0)
                    lathe(bm, uv, (x, y), [(h + 0.3, 0.03), (h + 0.42, w * 0.6), (h + 0.6, 0.02)], 3, 1)
                else:                                                       # a slab with a rounded top
                    lean = (rng.uniform(-.12, .12), rng.uniform(-.12, .12))
                    lathe(bm, uv, (x, y), [(-0.2, w), (h * 0.8, w), (h, w * 0.6), (h * 1.08, 0.02)], 4, 0, lean)
            for _ in range(rng.randint(2, 4)):                              # grave slabs flat on the ground
                c = (rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2))
                box(bm, uv, (c[0] - 0.3, c[1] - 0.14, -0.1), (c[0] + 0.3, c[1] + 0.14, 0.08), 0)
        elif kind == "boz_bones":
            a0 = rng.uniform(0, 6.283)
            ax, ay = math.cos(a0), math.sin(a0)
            for i in range(rng.randint(5, 7)):                              # ribs arching out of the sand
                t = -1.2 + i * 0.4
                bx, by = ax * t, ay * t
                for s_ in (-1, 1):
                    p0 = Vector((bx - ay * s_ * 0.3, by + ax * s_ * 0.3, -0.2))
                    p1 = Vector((bx - ay * s_ * 0.9, by + ax * s_ * 0.9, 1.0 + 0.3 * math.cos(t)))
                    p2 = Vector((bx - ay * s_ * 0.5, by + ax * s_ * 0.5, 1.7 + 0.4 * math.cos(t)))
                    limb(bm, uv, p0, p1, 0.09, 0.07, 0, sides=5, segs=1)
                    limb(bm, uv, p1, p2, 0.07, 0.04, 0, sides=5, segs=1)
            limb(bm, uv, Vector((-ax * 1.6, -ay * 1.6, 0.05)), Vector((ax * 1.6, ay * 1.6, 0.1)), 0.14, 0.12, 0,
                 sides=6, segs=3)                                           # the spine
            for _ in range(rng.randint(2, 3)):                              # loose long bones with knobbed ends
                a, d = rng.uniform(0, 6.283), rng.uniform(1.0, 1.6)
                c = Vector((math.cos(a) * d, math.sin(a) * d, 0.05))
                b_ = rng.uniform(0, 6.283)
                e = Vector((math.cos(b_) * 0.6, math.sin(b_) * 0.6, 0.0))
                limb(bm, uv, c - e, c + e, 0.07, 0.07, 0, sides=5, segs=1)
                for q in (c - e, c + e):
                    lathe(bm, uv, (q.x, q.y), [(-0.05, 0.1), (0.1, 0.13), (0.22, 0.02)], 6, 0)
        elif kind == "boz_grass":
            for _ in range(rng.randint(5, 8)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.3)
                r = rng.uniform(0.2, 0.35)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.4)), r, r * 0.5, 10, 0, size=(0.25, 0.5))
        elif kind == "boz_rock":
            for i in range(rng.randint(3, 5)):                              # weathered boulders, flat-topped
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.1) * (i > 0)
                r, h = rng.uniform(0.3, 0.7), rng.uniform(0.3, 0.9)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.3, r * 1.1), (h * 0.5, r), (h, r * 0.7),
                                                                   (h * 1.05, 0.02)], 7, 0,
                      (rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1)))
        elif kind == "ces_fungus":
            for i in range(rng.randint(4, 6)):                              # stalks with broad flat caps
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.0) * (i > 0)
                h, r = rng.uniform(0.6, 1.6), rng.uniform(0.25, 0.5)
                c = (math.cos(a) * d, math.sin(a) * d)
                lathe(bm, uv, c, [(-0.2, 0.09), (h, 0.06)], 6, 0)
                lathe(bm, uv, c, [(h - 0.1, 0.05), (h, r), (h + 0.12, r * 0.85), (h + 0.22, 0.02)], 10, 1)
        elif kind == "ces_spike":
            for i in range(rng.randint(3, 5)):                              # red rock spikes, leaning
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.9) * (i > 0)
                h, r = rng.uniform(0.9, 2.2), rng.uniform(0.2, 0.4)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.3, r * 1.2), (h * 0.4, r * 0.8), (h, 0.03)], 6, 0,
                      (rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12)))
        elif kind == "dat_tree":
            top = crooked(Vector((0, 0, -0.2)), Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), 1)),
                          rng.uniform(1.8, 2.6), 0.14, parts=4, kink=0.35)
            for j in range(5):                                              # crooked limbs, sparse red tufts
                a = 6.283 * j / 5 + rng.uniform(-0.4, 0.4)
                tip = crooked(top - Vector((0, 0, rng.uniform(0.2, 0.7))), Vector((math.cos(a), math.sin(a), 0.5)),
                              rng.uniform(0.6, 1.1), 0.05, parts=3, kink=0.45)
                clump(bm, uv, tip, 0.35, 0.25, 6, 1, size=(0.3, 0.5))
            clump(bm, uv, top + Vector((0, 0, 0.05)), 0.4, 0.3, 7, 1, size=(0.3, 0.5))
        elif kind == "dat_fern":
            for _ in range(rng.randint(6, 9)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.25)), 0.35, 0.3, 9, 0, size=(0.3, 0.55))
        elif kind == "dat_rock":
            for i in range(rng.randint(2, 4)):                              # crooked spires, bulging and narrowing
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.8) * (i > 0)
                h, r = rng.uniform(1.6, 3.4) * (1.0 if i == 0 else 0.6), rng.uniform(0.3, 0.5)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.3, r * 1.3), (h * 0.3, r * 0.8), (h * 0.55, r),
                                                                     (h * 0.8, r * 0.5), (h, 0.05)], 7, 0,
                      (rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15)))
        elif kind == "man_veshok":
            h = rng.uniform(3.0, 3.8)
            limb(bm, uv, Vector((0, 0, -0.2)), Vector((0, 0, h)), 0.13, 0.05, 0, sides=6, segs=3)
            for q in range(4):                                              # a high oval crown
                z = h * 0.55 + q * h * 0.13
                clump(bm, uv, Vector((0, 0, z)), 0.75 - 0.12 * abs(q - 1.5), 0.4, 11, 1, size=(0.35, 0.6))
        elif kind == "con_wisp":
            h = rng.uniform(3.0, 3.8)
            top = crooked(Vector((0, 0, -0.2)), Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 1)), h, 0.09,
                          parts=3, kink=0.08)
            for q in range(7):                                              # wisps hanging in long streamers
                a = 6.283 * q / 7 + rng.uniform(-0.3, 0.3)
                for z in (h * 0.75, h * 0.55):
                    c = Vector((math.cos(a) * 0.45, math.sin(a) * 0.45, z))
                    clump(bm, uv, c, 0.18, 0.55, 4, 1, size=(0.2, 0.6))
            clump(bm, uv, top, 0.35, 0.45, 8, 1, size=(0.25, 0.6))
        elif kind == "tar_vines":
            for _ in range(rng.randint(2, 4)):                              # rubble blocks
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.9)
                w = rng.uniform(0.2, 0.45)
                c = (math.cos(a) * d, math.sin(a) * d)
                box(bm, uv, (c[0] - w, c[1] - w * 0.7, -0.2), (c[0] + w, c[1] + w * 0.7, rng.uniform(0.2, 0.7)), 0)
            for _ in range(rng.randint(6, 9)):                              # vine tangles over them
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.1)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, rng.uniform(0.2, 0.7))), 0.35, 0.3, 8, 1,
                      size=(0.3, 0.5))
        elif kind == "way_tree":
            giant(bm, uv, rng.uniform(2.4, 3.0), 0.18, 4, [(2.0, 6, 0.95, 0.9), (2.7, 4, 0.6, 0.85)], 3.3, 460)
        elif kind == "way_fern":
            for _ in range(rng.randint(6, 9)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.3)), 0.4, 0.32, 9, 0, size=(0.35, 0.6))
        elif kind == "bra_scrap":
            for _ in range(rng.randint(4, 7)):                              # hull plates leaning in a heap
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.8)
                w, h = rng.uniform(0.25, 0.5), rng.uniform(0.3, 0.8)
                c = (math.cos(a) * d, math.sin(a) * d)
                box(bm, uv, (c[0] - w, c[1] - 0.05, -0.2), (c[0] + w, c[1] + 0.05, h), rng.randint(0, 1))
            lathe(bm, uv, (0.0, 0.0), [(-0.2, 0.9), (0.3, 0.6), (0.6, 0.15)], 7, 1)          # the heap of slag
            for _ in range(2):                                              # girders sticking out
                b = rng.uniform(0, 6.283)
                limb(bm, uv, Vector((0, 0, 0.2)), Vector((math.cos(b) * 1.0, math.sin(b) * 1.0, rng.uniform(0.6, 1.2))),
                     0.04, 0.04, 0, sides=4, segs=1)
            b = rng.uniform(0, 6.283)                                       # a broken engine cone
            lathe(bm, uv, (math.cos(b) * 0.9, math.sin(b) * 0.9), [(-0.1, 0.35), (0.5, 0.25), (0.55, 0.1)], 8, 0,
                  (0.3, 0.0))
        elif kind == "bra_rock":
            for i in range(rng.randint(2, 4)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.8) * (i > 0)
                r = rng.uniform(0.3, 0.6)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (r * 0.6, r * 0.9), (r * 1.1, r * 0.4),
                                                                     (r * 1.2, 0.05)], 6, 0)
        elif kind == "tra_jungle":
            giant(bm, uv, rng.uniform(3.0, 3.6), 0.2, 6, [(2.6, 5, 1.1, 0.95), (3.3, 4, 0.7, 0.9)], 3.8, 520)
        elif kind == "tra_thorn":
            top = crooked(Vector((0, 0, -0.2)), Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 1)),
                          rng.uniform(1.4, 1.9), 0.09, parts=3, kink=0.25)
            for j in range(5):                                              # a flat wide crown
                a = 6.283 * j / 5 + rng.uniform(-0.3, 0.3)
                clump(bm, uv, top + Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, rng.uniform(-0.05, 0.1))), 0.45, 0.14,
                      8, 1, size=(0.35, 0.6))
            for _ in range(6):                                              # grass round it
                a, d = rng.uniform(0, 6.283), rng.uniform(0.4, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.2)), 0.2, 0.3, 8, 1, size=(0.2, 0.4))
        elif kind == "tra_spine":
            for i in range(rng.randint(2, 4)):                              # ribbed columns, thorny crowns
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.7) * (i > 0)
                h, r = rng.uniform(0.8, 1.8), rng.uniform(0.1, 0.18)
                c = (math.cos(a) * d, math.sin(a) * d)
                lathe(bm, uv, c, [(-0.2, r), (h * 0.8, r), (h, r * 0.4), (h * 1.05, 0.02)], 7, 0)
        elif kind == "nyr_meadlin":
            top = crooked(Vector((0, 0, -0.2)), Vector((0, 0, 1)), rng.uniform(1.0, 1.4), 0.12, parts=2, kink=0.1)
            for j in range(4):                                              # the fork into spreading limbs
                a = 6.283 * j / 4 + rng.uniform(-0.4, 0.4)
                tip = crooked(top, Vector((math.cos(a), math.sin(a), 0.7)), rng.uniform(0.8, 1.2), 0.06, parts=2, kink=0.2)
                clump(bm, uv, tip + Vector((0, 0, 0.1)), 0.5, 0.35, 9, 1, size=(0.35, 0.6))
            clump(bm, uv, top + Vector((0, 0, 0.6)), 0.5, 0.35, 9, 1, size=(0.35, 0.6))
        elif kind == "nyr_nettle":
            for _ in range(rng.randint(6, 9)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.1)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.35)), 0.18, 0.5, 9, 0, size=(0.15, 0.55))
        elif kind == "crs_palm":
            lean = (rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25))
            h = rng.uniform(2.4, 3.2)
            lathe(bm, uv, (0.0, 0.0), [(-0.2, 0.12), (h * 0.5, 0.09), (h, 0.07)], 6, 0, lean)
            top = Vector((lean[0] * h, lean[1] * h, h))
            for j in range(8):                                              # long arching fronds
                a = 6.283 * j / 8 + rng.uniform(-0.2, 0.2)
                clump(bm, uv, top + Vector((math.cos(a) * 0.55, math.sin(a) * 0.55, -0.2)), 0.35, 0.12, 5, 1,
                      size=(0.25, 0.8))
            clump(bm, uv, top, 0.3, 0.25, 5, 1, size=(0.25, 0.6))
        elif kind == "crs_shrub":
            for _ in range(rng.randint(5, 8)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.0)
                r = rng.uniform(0.25, 0.45)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.7)), r, r * 0.7, 10, 0, size=(0.25, 0.45))
        elif kind == "kas_vine":
            for _ in range(rng.randint(7, 10)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.3)), 0.4, 0.4, 9, 0, size=(0.35, 0.6))
        elif kind == "kas_black":
            top = crooked(Vector((0, 0, -0.2)), Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 1)),
                          rng.uniform(2.2, 3.0), 0.16, parts=4, kink=0.4)
            for j in range(6):                                              # twisted bare limbs hung with web
                a = 6.283 * j / 6 + rng.uniform(-0.4, 0.4)
                tip = crooked(top - Vector((0, 0, rng.uniform(0.3, 1.0))), Vector((math.cos(a), math.sin(a), 0.2)),
                              rng.uniform(0.7, 1.2), 0.06, parts=3, kink=0.5)
                clump(bm, uv, tip - Vector((0, 0, 0.2)), 0.3, 0.45, 4, 1, size=(0.3, 0.6))
        elif kind == "ond_broadleaf":
            giant(bm, uv, rng.uniform(2.8, 3.4), 0.17, 5, [(2.4, 6, 1.1, 0.9), (3.1, 4, 0.7, 0.85)], 3.6, 480)
        elif kind == "ond_weed":
            for _ in range(rng.randint(7, 10)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.3)), 0.3, 0.45, 8, 0, size=(0.25, 0.6))
        elif kind == "umb_tentacle":
            for _ in range(rng.randint(3, 5)):                              # tentacles rising and arching over
                a, d0 = rng.uniform(0, 6.283), rng.uniform(0.0, 0.5)
                base = Vector((math.cos(a) * d0, math.sin(a) * d0, -0.3))
                b = a + rng.uniform(-0.6, 0.6)
                out = Vector((math.cos(b), math.sin(b), 0.0))
                H, Wd = rng.uniform(3.2, 5.4), rng.uniform(2.2, 3.4)
                P0, P1 = base, base + Vector((0, 0, H * 1.6)) + out * Wd * 0.35
                P2 = base + out * Wd + Vector((0, 0, H * rng.uniform(0.05, 0.3)))   # arching back toward the ground
                n, r0 = 10, rng.uniform(0.26, 0.36)
                pts = [((1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t * t * P2, r0 * (1 - t) + 0.04)
                       for t in (q / n for q in range(n + 1))]
                tube(bm, uv, pts, 7, 0)
                strip = []                                                  # the glow strip on the inner side
                for q, (p, r) in enumerate(pts[:-1]):
                    tdir = (pts[q + 1][0] - p).normalized()
                    nrm = (p - P1) - tdir * (p - P1).dot(tdir)              # away from the control point: concave side
                    nrm = nrm.normalized() if nrm.length > 1e-6 else Vector((0, 0, -1))
                    strip.append((p + nrm * r * 0.8, r * 0.6))
                tube(bm, uv, strip, 5, 1, vrep=4.0)
        elif kind == "umb_mushroom":
            H = rng.uniform(2.0, 3.0)
            lean = (rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06))
            lathe(bm, uv, (0.0, 0.0), [(-0.2, 0.42), (0.6, 0.3), (H * 0.6, 0.24), (H, 0.32)], 9, 0, lean)
            prof = [(H, 0.32), (H + 0.12, 1.15), (H + 0.5, 1.3), (H + 0.9, 1.08), (H + 1.2, 0.6), (H + 1.32, 0.05)]
            lathe(bm, uv, (lean[0] * H, lean[1] * H), prof, 12, 0)
            for _ in range(26):                                             # glowing spots on the cap
                z = rng.uniform(H + 0.15, H + 1.15)
                k_ = max(q for q in range(len(prof) - 1) if prof[q][0] <= z)          # on the cap's surface
                (z0_, r0_), (z1_, r1_) = prof[k_], prof[k_ + 1]
                rr = r0_ + (r1_ - r0_) * (z - z0_) / max(z1_ - z0_, 1e-6)
                a = rng.uniform(0, 6.283)
                c = (lean[0] * H + math.cos(a) * rr, lean[1] * H + math.sin(a) * rr)
                sr = rng.uniform(0.1, 0.2)
                lathe(bm, uv, c, [(z - sr, 0.02), (z - sr * 0.4, sr), (z + sr * 0.4, sr), (z + sr, 0.02)], 6, 1)
            for _ in range(6):                                              # and round the base of the trunk
                a, z = rng.uniform(0, 6.283), rng.uniform(0.0, 0.6)
                sr = rng.uniform(0.07, 0.12)
                c = (math.cos(a) * 0.38, math.sin(a) * 0.38)
                lathe(bm, uv, c, [(z - sr, 0.02), (z - sr * 0.4, sr), (z + sr * 0.4, sr), (z + sr, 0.02)], 6, 1)
        elif kind == "umb_flamestalk":
            for _ in range(rng.randint(4, 7)):                              # thin black stalks, flame-red blades
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.8)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.2))
                h = rng.uniform(1.4, 3.2)
                bend = Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 0))
                pts = [(base + Vector((0, 0, h * t)) + bend * t * t, 0.07 * (1 - 0.6 * t)) for t in (0, 0.33, 0.66, 1.0)]
                tube(bm, uv, pts, 5, 0)
                tip = pts[-1][0]
                for q in range(rng.randint(3, 5)):
                    c = 6.283 * q / 4 + rng.uniform(-0.4, 0.4)
                    end = tip + Vector((math.cos(c) * 0.35, math.sin(c) * 0.35, rng.uniform(0.2, 0.5)))
                    limb(bm, uv, tip, end, 0.07, 0.004, 1, sides=4, segs=1)
        elif kind == "umb_pod":
            for _ in range(rng.randint(2, 3)):                              # black pods with glowing spots
                a, d = rng.uniform(0, 6.283), rng.uniform(0.1, 0.9)
                c = (math.cos(a) * d, math.sin(a) * d)
                s_ = rng.uniform(0.7, 1.1)
                lathe(bm, uv, c, [(-0.1, 0.22 * s_), (0.25 * s_, 0.42 * s_), (0.6 * s_, 0.32 * s_), (0.8 * s_, 0.08)], 9, 0)
                for _q in range(7):
                    b, z = rng.uniform(0, 6.283), rng.uniform(0.1, 0.6) * s_
                    rr = 0.4 * s_
                    sr = rng.uniform(0.05, 0.09)
                    lathe(bm, uv, (c[0] + math.cos(b) * rr, c[1] + math.sin(b) * rr),
                          [(z - sr, 0.02), (z, sr), (z + sr, 0.02)], 5, 1)
            for _ in range(rng.randint(2, 3)):                              # curled pink-glowing tendrils
                a, d = rng.uniform(0, 6.283), rng.uniform(0.3, 1.1)
                cx, cy = math.cos(a) * d, math.sin(a) * d
                pts = [(Vector((cx + 0.25 * math.cos(t * 4.5) * (1 - t * 0.6), cy + 0.25 * math.sin(t * 4.5) * (1 - t * 0.6),
                                -0.1 + 0.9 * t)), 0.05 * (1 - 0.5 * t)) for t in (q / 8 for q in range(9))]
                tube(bm, uv, pts, 5, 2, vrep=3.0)
            for _ in range(6):                                              # dark blue grass with red tips
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.25)), 0.25, 0.35, 8, 3, size=(0.2, 0.45))
        elif kind == "rus_tree":
            giant(bm, uv, rng.uniform(2.0, 2.6), 0.14, 3, [(1.7, 5, 0.75, 0.95), (2.3, 3, 0.4, 0.9)], 2.8, 440)
        elif kind == "rus_scrub":
            for _ in range(rng.randint(6, 9)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                r = rng.uniform(0.25, 0.4)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.5)), r, r * 0.6, 12, 0, size=(0.25, 0.45))
        elif kind == "rus_scorched":
            for i in range(rng.randint(2, 4)):                              # scorched snags, broken tops
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.0) * (i > 0)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.2))
                top = crooked(base, Vector((rng.uniform(-.2, .2), rng.uniform(-.2, .2), 1)), rng.uniform(0.9, 2.2),
                              rng.uniform(0.09, 0.14), parts=3, kink=0.18)
                if rng.random() < 0.5:
                    b_ = rng.uniform(0, 6.283)
                    crooked(top - Vector((0, 0, 0.3)), Vector((math.cos(b_), math.sin(b_), 0.3)), 0.45, 0.04, parts=2)
            for _ in range(rng.randint(3, 5)):                              # pale fallen stones, half sunk
                a, d = rng.uniform(0, 6.283), rng.uniform(0.4, 1.4)
                r = rng.uniform(0.15, 0.32)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (r * 0.6, r * 0.9), (r * 1.1, r * 0.4),
                                                                   (r * 1.2, 0.03)], 5, 1)
        elif kind == "col_tree":
            giant(bm, uv, rng.uniform(2.2, 2.8), 0.15, 4, [(1.8, 6, 1.0, 0.9), (2.5, 4, 0.6, 0.85)], 3.0, 420)
        elif kind == "col_mound":
            for i in range(rng.randint(1, 3)):                              # ribbed earthen spires
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.7) * (i > 0)
                h, r = rng.uniform(1.2, 2.6) * (1.0 if i == 0 else 0.6), rng.uniform(0.35, 0.55)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (h * 0.3, r * 0.8), (h * 0.6, r * 0.55),
                                                                     (h * 0.85, r * 0.3), (h, 0.04)], 7, 0)
        elif kind == "col_eggs":
            for _ in range(rng.randint(5, 9)):                              # pale egg clusters among reeds
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.0)
                r = rng.uniform(0.12, 0.22)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.05, r * 0.6), (r * 0.8, r), (r * 1.7, r * 0.7),
                                                                     (r * 2.1, 0.02)], 7, 0)
            for _ in range(3):
                b = rng.uniform(0, 6.283)
                clump(bm, uv, Vector((math.cos(b) * 0.9, math.sin(b) * 0.9, 0.25)), 0.3, 0.4, 7, 1, size=(0.2, 0.5))
        elif kind == "man_crystal":
            for i in range(rng.randint(4, 7)):                              # glassy shards, steep and sharp
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.0) * (i > 0)
                h, r = rng.uniform(0.4, 1.4), rng.uniform(0.1, 0.25)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (h, 0.01)], 4, 0,
                      (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)))
        elif kind == "jab_tree":
            top = crooked(Vector((0, 0, -0.2)), Vector((0, 0, 1)), rng.uniform(1.8, 2.4), 0.14, parts=3, kink=0.12)
            for j in range(7):                                              # heavy limbs, the crown drooping
                a = 6.283 * j / 7 + rng.uniform(-0.2, 0.2)
                tip = crooked(top - Vector((0, 0, 0.5)), Vector((math.cos(a), math.sin(a), 0.6)), rng.uniform(0.6, 0.9),
                              0.06, parts=2, kink=0.2)
                clump(bm, uv, tip, 0.5, 0.35, 10, 1, size=(0.4, 0.7))
                clump(bm, uv, tip + Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, -0.45)), 0.35, 0.3, 6, 1, size=(0.35, 0.6))
            clump(bm, uv, top + Vector((0, 0, 0.1)), 0.6, 0.4, 12, 1, size=(0.4, 0.7))
        elif kind == "jab_marsh":
            for _ in range(10):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, 0.35)), 0.2, 0.45, 12, 0, size=(0.25, 0.5))
        elif kind == "jab_bamboo":
            for _ in range(rng.randint(12, 18)):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.9)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.2))
                top = base + Vector((rng.uniform(-.3, .3), rng.uniform(-.3, .3), rng.uniform(2.0, 3.0)))
                limb(bm, uv, base, top, 0.05, 0.03, 0, sides=5, segs=2)
                clump(bm, uv, top - Vector((0, 0, 0.35)), 0.35, 0.5, 6, 1, size=(0.35, 0.55))
        elif kind == "lia_tree":
            top = crooked(Vector((0, 0, -0.2)), Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 1)),
                          rng.uniform(1.6, 2.2), 0.11, parts=3, kink=0.15)
            for j in range(5):                                              # limbs fanning out under a flat crown
                a = 6.283 * j / 5 + rng.uniform(-0.3, 0.3)
                tip = crooked(top - Vector((0, 0, 0.3)), Vector((math.cos(a), math.sin(a), 0.5)), rng.uniform(0.6, 0.9), 0.05,
                              parts=2, kink=0.2)
                clump(bm, uv, tip + Vector((0, 0, 0.1)), 0.55, 0.18, 10, 1, size=(0.4, 0.7))
        elif kind == "lia_grass":
            for _ in range(9):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.2)
                r = rng.uniform(0.2, 0.32)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.5)), r, r * 0.6, 10, 0, size=(0.25, 0.45))
        elif kind == "lia_pylon":
            for i in range(2):                                              # two lattice pylons joined by a cable
                x = -0.9 + 1.8 * i
                legs = [Vector((x + 0.25 * sx, 0.25 * sy, -0.2)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
                apex = Vector((x, 0, 2.6))
                for lg in legs:
                    limb(bm, uv, lg, apex, 0.04, 0.025, 0, sides=4, segs=1)
                for z in (0.9, 1.6, 2.2):
                    limb(bm, uv, Vector((x - 0.45, 0, z)), Vector((x + 0.45, 0, z)), 0.03, 0.03, 0, sides=4, segs=1)
            limb(bm, uv, Vector((-0.9, 0, 2.2)), Vector((0.9, 0, 2.15)), 0.015, 0.015, 0, sides=3, segs=2)
            lathe(bm, uv, (0.0, 0.9), [(-0.2, 0.06), (2.8, 0.03)], 6, 0)       # a comm mast with a dish
            lathe(bm, uv, (0.0, 0.9), [(2.3, 0.05), (2.45, 0.3), (2.5, 0.34)], 10, 0)
        elif kind == "ieg_reeksa":
            for _ in range(rng.randint(3, 5)):                              # stalks curling up, a toothed maw on each
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.7)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.2))
                tip = crooked(base, Vector((math.cos(a) * 0.5, math.sin(a) * 0.5, 1)), rng.uniform(1.2, 2.2), 0.14,
                              parts=4, kink=0.3)
                lathe(bm, uv, (tip.x, tip.y), [(tip.z - 0.25, 0.08), (tip.z - 0.05, 0.28), (tip.z + 0.15, 0.3),
                                                 (tip.z + 0.3, 0.12)], 7, 0)
                for j in range(5):                                          # the teeth round the maw
                    b = 6.283 * j / 5
                    c = Vector((tip.x + 0.28 * math.cos(b), tip.y + 0.28 * math.sin(b), tip.z + 0.15))
                    limb(bm, uv, c, c + Vector((0.1 * math.cos(b), 0.1 * math.sin(b), 0.22)), 0.04, 0.005, 0, sides=3, segs=1)
            for _ in range(4):                                              # thorned runners on the ground
                a = rng.uniform(0, 6.283)
                crooked(Vector((0, 0, 0.0)), Vector((math.cos(a), math.sin(a), 0.05)), rng.uniform(0.8, 1.4), 0.06, parts=3)
        elif kind == "ieg_basalt":
            for i in range(rng.randint(5, 9)):                              # hexagonal columns, tops at different heights
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.8) * (i > 0)
                h, r = rng.uniform(0.8, 2.6) * (1.0 if i == 0 else 0.8), rng.uniform(0.16, 0.26)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (h, r), (h + 0.05, r * 0.9)], 6, 0)
        elif kind == "ieg_bones":
            a0 = rng.uniform(0, 6.283)
            ax = Vector((math.cos(a0), math.sin(a0), 0))
            side = Vector((-math.sin(a0), math.cos(a0), 0))
            for j in range(6):                                              # rib arches along a sunken spine
                c = ax * (j * 0.38 - 1.0)
                for sg in (-1, 1):
                    crooked(c, side * sg * 0.6 + Vector((0, 0, 1)), 1.3 - 0.1 * abs(j - 2.5), 0.06, parts=3, kink=0.08)
            limb(bm, uv, ax * -1.1 + Vector((0, 0, 0.05)), ax * 1.2 + Vector((0, 0, 0.05)), 0.1, 0.06, 0, sides=5, segs=2)
            sk = ax * 1.55                                                  # the skull, half buried
            lathe(bm, uv, (sk.x, sk.y), [(-0.2, 0.35), (0.15, 0.42), (0.4, 0.3), (0.55, 0.05)], 8, 0)
        elif kind == "mcl_coral":
            for _ in range(rng.randint(2, 3)):                              # brain-coral domes
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 0.8)
                r = rng.uniform(0.3, 0.55)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.2, r), (r * 0.5, r * 0.9), (r * 0.85, r * 0.5),
                                                                     (r, 0.05)], 9, 0)
            for _ in range(rng.randint(4, 6)):                              # staghorn branches, forking once
                a, d = rng.uniform(0, 6.283), rng.uniform(0.2, 1.1)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.1))
                tip = crooked(base, Vector((math.cos(a) * 0.4, math.sin(a) * 0.4, 1)), rng.uniform(0.6, 1.1), 0.07,
                              parts=2, kink=0.3)
                for _ in range(2):
                    crooked(tip, Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0.8)), rng.uniform(0.25, 0.45), 0.04,
                            parts=1)
        elif kind == "mcl_palm":
            for i in range(rng.randint(2, 3)):                              # leaning ringed trunks
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 0.7) * (i > 0)
                base = Vector((math.cos(a) * d, math.sin(a) * d, -0.2))
                lean = Vector((math.cos(a + 1.0) * 0.45, math.sin(a + 1.0) * 0.45, 1.0))
                top = crooked(base, lean, rng.uniform(2.2, 3.2), 0.09, parts=4, kink=0.12)
                for j in range(7):                                          # the frond crown: drooping fronds
                    b = 2 * math.pi * j / 7 + rng.uniform(-0.2, 0.2)
                    mid = top + Vector((math.cos(b) * 0.55, math.sin(b) * 0.55, 0.12))
                    clump(bm, uv, mid, 0.32, 0.12, 4, 1, size=(0.4, 0.7))
                    clump(bm, uv, mid + Vector((math.cos(b) * 0.4, math.sin(b) * 0.4, -0.22)), 0.25, 0.1, 3, 1,
                          size=(0.35, 0.6))
        elif kind == "mcl_seastack":
            for i in range(rng.randint(2, 4)):                              # wave-cut pillars, notched at the foot
                a, d = rng.uniform(0, 6.283), rng.uniform(0.0, 1.0) * (i > 0)
                h, r = rng.uniform(1.6, 3.2) * (1.0 if i == 0 else 0.7), rng.uniform(0.25, 0.42)
                lathe(bm, uv, (math.cos(a) * d, math.sin(a) * d), [(-0.3, r * 1.2), (0.25, r * 0.7), (0.6, r),
                                                                     (h * 0.8, r * 0.9), (h, r * 0.6), (h * 1.03, 0.05)],
                      7, 0, (rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08)))
        elif kind == "zyg_tree":
            giant(bm, uv, 1.6, 0.12, 3, [(1.45, 5, 0.85, 0.7)], 1.75, 360)   # short trunk, flat spreading crown
        else:                                                               # zyg_shrubs
            for _ in range(6):
                a, d = rng.uniform(0, 6.283), rng.uniform(0, 1.0)
                r = rng.uniform(0.3, 0.5)
                clump(bm, uv, Vector((math.cos(a) * d, math.sin(a) * d, r * 0.6)), r, r * 0.5, 24, 0, size=(0.35, 0.6))

    def homestead(bm, uv):
        dome(bm, uv, (0, 0, -0.05), 0.45)              # main dome
        dome(bm, uv, (0.75, 0.2, -0.03), 0.22)         # entrance
        dome(bm, uv, (-0.55, 0.55, -0.03), 0.2)
        box(bm, uv, (0.25, -0.12, 0.0), (0.7, 0.12, 0.12), 0)   # corridor to the entrance dome
        vaporator = [(0.0, .05), (.06, .02), (.5, .02), (.52, .04), (.56, .04), (.6, .005)]
        tube(bm, uv, [(Vector((-0.2, -0.75, z)), r) for z, r in vaporator], 6, 0)

    for idx, kind in PROCEDURAL.items():
        if only and str(idx) not in only and kind not in only:
            continue
        if kind.startswith(("dk_", "zyg_", "canto_", "bon_", "etti_", "ruu_", "oss_", "lola_", "rv_", "rh_", "mcl_", "ieg_", "lia_", "jab_", "sal_", "tel_", "ser_", "yav_", "cel_", "bot_", "axx_", "cit_", "ces_", "dat_", "man_", "con_", "tar_", "way_", "bra_", "tra_", "nyr_", "crs_", "kas_", "ond_", "umb_", "col_", "rus_", "boz_", "ith_", "om_", "gar_", "aga_", "ot_", "dan_", "dub_", "kal_", "muun_", "bas_", "myg_", "yag_", "ans_", "ilu_", "dor_", "yin_", "cha_", "cor_", "ark_", "anx_", "ess_")):
            rng.seed(kind)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        me = bpy.data.meshes.new(kind)
        obj = bpy.data.objects.new(kind, me)
        bpy.context.scene.collection.objects.link(obj)
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new("UVMap")
        if kind == "wroshyr":
            giant(bm, uv, 4.6, 0.32, 5, [(2.6, 3, 1.4, 1.2), (3.5, 3, 1.15, 1.05), (4.4, 3, 0.9, 0.9), (5.2, 2, 0.6, 0.8)],
                  5.7, 700)
            mats = PROC_MATS[idx]
        elif kind == "jungle_giant":
            giant(bm, uv, 2.8, 0.30, 6, [(3.2, 5, 1.5, 1.2), (3.7, 3, 0.8, 1.1)], 4.0, 650)
            mats = PROC_MATS[idx]
        elif kind.startswith("fel_"):
            felucia(bm, uv, kind)
            mats = PROC_MATS[idx]
        elif kind.startswith("rax_"):
            raxus_flora(bm, uv, kind)
            mats = PROC_MATS[idx]
        elif kind.startswith("rp_heap"):
            junk_heap(bm, uv, kind)
            mats = PROC_MATS[idx]
        elif kind.startswith("kor_"):
            korriban_flora(bm, uv, kind)
            mats = PROC_MATS[idx]
        elif kind.startswith(("dk_", "zyg_", "canto_", "bon_", "etti_", "ruu_", "oss_", "lola_", "rv_", "rh_", "mcl_", "ieg_", "lia_", "jab_", "sal_", "tel_", "ser_", "yav_", "cel_", "bot_", "axx_", "cit_", "ces_", "dat_", "man_", "con_", "tar_", "way_", "bra_", "tra_", "nyr_", "crs_", "kas_", "ond_", "umb_", "col_", "rus_", "boz_", "ith_", "om_", "gar_", "aga_", "ot_", "dan_", "dub_", "kal_", "muun_", "bas_", "myg_", "yag_", "ans_", "ilu_", "dor_", "yin_", "cha_", "cor_", "ark_", "anx_", "ess_")):
            planet_flora(bm, uv, kind)
            mats = PROC_MATS[idx]
        else:
            homestead(bm, uv)
            mats = PROC_MATS[idx]
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(bpy.data.materials.new(m))
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if kind not in ("wroshyr", "jungle_giant") and not kind.startswith(("fel_", "rax_", "rp_heap", "kor_", "dk_", "zyg_", "canto_", "bon_", "etti_", "ruu_", "oss_", "lola_", "rv_", "rh_", "mcl_", "ieg_", "lia_", "jab_", "sal_", "tel_", "ser_", "yav_", "cel_", "bot_", "axx_", "cit_", "ces_", "dat_", "man_", "con_", "tar_", "way_", "bra_", "tra_", "nyr_", "crs_", "kas_", "ond_", "umb_", "col_", "rus_", "boz_", "ith_", "om_", "gar_", "aga_", "ot_", "dan_", "dub_", "kal_", "muun_", "bas_", "myg_", "yag_", "ans_", "ilu_", "dor_", "yin_", "cha_", "cor_", "ark_", "anx_", "ess_")):   # hard-surface props: Blender unwraps
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(island_margin=0.02)
            bpy.ops.object.mode_set(mode="OBJECT")
            for v in me.vertices:
                v.co *= 1.15
        m = obj.modifiers.new("t", "TRIANGULATE")
        bpy.ops.object.modifier_apply(modifier=m.name)
        single_material(obj, idx, [m.name.split(".")[0] for m in me.materials], bie, PDX_SHADER, out_dir)
        uv1 = me.uv_layers.new()
        for d in uv1.data:
            d.uv = (0.0, 0.0)
        name = f"hod_flora_{idx}_{kind}"
        obj.name = me.name = name
        bie.export_meshfile(os.path.join(out_dir, name + ".mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
        if kind in ("rax_tree", "rax_tiered"):     # copies stood on Raxulon's Great Alley as map objects: the map
            me.materials[0][PDX_SHADER] = "PdxMeshHodAlphaTest"   # object shader must cut the leaf cards out itself
            bie.export_meshfile(os.path.join(out_dir, f"hod_rax_alley_{idx}.mesh"), exp_mesh=True, exp_skel=False, exp_locs=False)
        zs = [v.co.z for v in me.vertices]
        print(f"{idx} {kind}: {len(me.polygons)} tris, height {max(zs):.2f}")


def wire():
    """gfx/entities/trees.gfx: the vanilla tree entries (the mod file replaces vanilla's) plus ours."""
    van = open(VANILLA_TREES, encoding="utf-8-sig").read().rstrip()
    assert van.endswith("}")
    ours = "\n\t# HOD: Poly Haven (CC0) flora and rocks, WIPGFX/plans & scripts/flora_props.py\n"
    files = {idx: f"hod_flora_{idx}_{pid}" for idx, (pid, *_rest) in ASSETS.items()}
    files.update({idx: f"hod_flora_{idx}_{kind}" for idx, kind in PROCEDURAL.items()})
    files.update({idx: f"hod_flora_{idx}_{name}" for idx, name in EXTERNAL.items()})
    for idx, name in sorted(files.items()):
        ours += (f'\tpdxmesh = {{\n\t\tname = "mapobject_{idx}"\n'
                 f'\t\tfile = "{OUT}/{name}.mesh"\n\t\tscale = 1\n\t}}\n')
    os.makedirs("gfx/entities", exist_ok=True)
    open("gfx/entities/trees.gfx", "w", encoding="utf-8", newline="\n").write(van[:-1] + ours + "}\n")
    print("gfx/entities/trees.gfx:", len(ASSETS), "HOD objects added")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    {"download": download, "textures": textures, "planet_textures": planet_textures, "meshes": meshes,
     "procedural": procedural, "wire": wire}[args[0]](*args[1:])
