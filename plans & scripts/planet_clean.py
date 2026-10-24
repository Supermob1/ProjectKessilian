"""Clean planet surface maps from the painted spheres (WIPGFX/Assets/map_base colormap = fow_rgb_waterspec_a art):
flatten the sphere and its baked lighting (planet_terrain_gen.deshade), then remove clouds and the painted night side.
Used by planet_terrain_gen.py for the colormap RGB; the shader adds sphere shading and animated clouds itself."""
import numpy as np
from scipy import ndimage as ndi


def clean_planets(img, lab):
    out = img.copy()
    rgb = img[..., :3]
    v = rgb.max(-1)
    s = (v - rgb.min(-1)) / np.maximum(v, 1e-3)
    for l, sl in enumerate(ndi.find_objects(lab), 1):
        if sl is None:
            continue
        m = lab[sl] == l
        if m.sum() < 40:
            continue
        blk = rgb[sl].copy()
        vv, ss = v[sl][m], s[sl][m]
        med = np.median(blk[m], 0)
        # clouds: brighter and less saturated than the typical surface
        cloud = m & (v[sl] > np.percentile(vv, 50) + 0.05) & (s[sl] < np.percentile(ss, 55))
        # painted night side / shadow: much darker than the typical surface
        shade = m & (v[sl] < np.percentile(vv, 50) * 0.7)
        bad = ndi.binary_dilation(cloud | shade, iterations=1) & m
        if bad.mean() < 0.7 and bad.any():
            idx = ndi.distance_transform_edt(~(m & ~bad), return_distances=False, return_indices=True)
            fill = ndi.gaussian_filter(blk[idx[0], idx[1]], (2, 2, 0))
            blk[bad] = fill[bad]
        else:                                   # mostly cloud/shade (ice, gas-like art): just pull towards the median
            blk[m] = blk[m] * 0.6 + med * 0.4
        o = out[sl]
        o[..., :3] = np.where(m[..., None], blk, o[..., :3])
        out[sl] = o
    return out
