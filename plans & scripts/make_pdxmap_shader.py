"""Build gfx/FX/pdxmap.shader = vanilla + anti-tiling in PixelShaderTerrain. Run from the mod root."""
VANILLA = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/FX/pdxmap.shader"
s = open(VANILLA, encoding="utf-8-sig").read()

a = s.index("\tMainCode PixelShaderTerrain")
b = s.index("\tMainCode PixelShaderUnderwater")
part = s[a:b]

helpers = '''
		// HOD anti-tiling: every atlas lookup is taken twice (normal UVs and rotated/rescaled UVs)
		// and the two are swapped by a slow world-space noise, so single-texture planets don't show a grid.
		static const float AT_ANGLE = 0.65f;      // radians between the two samples
		static const float AT_SCALE = 0.73f;      // scale of the second sample
		static const float AT_NOISE_FREQ = 0.035f; // patch size of the swap (map units)
		static const float AT_MACRO = 0.10f;      // +- brightness variation at large scale

		float ATHash( float2 p )
		{
			float3 p3 = frac( float3( p.x, p.y, p.x ) * 0.1031f );
			p3 += dot( p3, p3.yzx + 33.33f );
			return frac( ( p3.x + p3.y ) * p3.z );
		}
		float ATNoise( float2 p )
		{
			float2 i = floor( p );
			float2 f = frac( p );
			float2 u = f * f * ( 3.0f - 2.0f * f );
			return lerp( lerp( ATHash( i ), ATHash( i + float2( 1.0f, 0.0f ) ), u.x ),
			             lerp( ATHash( i + float2( 0.0f, 1.0f ) ), ATHash( i + float2( 1.0f, 1.0f ) ), u.x ), u.y );
		}
		float2 ATRotate( float2 v, float a )
		{
			float c = cos( a );
			float s = sin( a );
			return float2( v.x * c - v.y * s, v.x * s + v.y * c );
		}
		float4 ATDiffuse( float u, float v, float2 uvA, float mipA, float lodA, float2 uvB, float mipB, float lodB, float w )
		{
			return lerp( tex2Dlod( TerrainDiffuse, sample_terrain( u, v, uvA, mipA, lodA ) ),
			             tex2Dlod( TerrainDiffuse, sample_terrain( u, v, uvB, mipB, lodB ) ), w );
		}
		float4 ATNormal( float u, float v, float2 uvA, float mipA, float lodA, float2 uvB, float mipB, float lodB, float w )
		{
			float4 nA = tex2Dlod( TerrainNormal, sample_terrain( u, v, uvA, mipA, lodA ) );
			float4 nB = tex2Dlod( TerrainNormal, sample_terrain( u, v, uvB, mipB, lodB ) );
			nB.rg = ATRotate( nB.rg - 0.5f, -AT_ANGLE ) + 0.5f;   // undo the UV rotation on the tangent-space normal
			return lerp( nA, nB, w );
		}

		float4 main( VS_OUTPUT_TERRAIN Input ) : PDX_COLOR'''
assert part.count("\t\tfloat4 main( VS_OUTPUT_TERRAIN Input ) : PDX_COLOR") == 1
part = part.replace("\t\tfloat4 main( VS_OUTPUT_TERRAIN Input ) : PDX_COLOR", helpers.lstrip("\n"), 1)

setup_old = '''			float vMipTexels = pow( 2.0f, ATLAS_TEXEL_POW2_EXPONENT - lod );
'''
setup_new = '''			float vMipTexels = pow( 2.0f, ATLAS_TEXEL_POW2_EXPONENT - lod );
			float2 vTileRepeatB = ATRotate( vTileRepeat, AT_ANGLE ) * AT_SCALE + float2( 0.37f, 0.71f );
			float lodB = clamp( mipmapLevel( vTileRepeatB ) - 0.5f, 0.0f, 6.0f );
			float vMipTexelsB = pow( 2.0f, ATLAS_TEXEL_POW2_EXPONENT - lodB );
			float2 vATPos = Input.uv2 * float2( MAP_SIZE_X, MAP_SIZE_Y );
			float vATn = ATNoise( vATPos * AT_NOISE_FREQ ) * 0.65f + ATNoise( vATPos * AT_NOISE_FREQ * 2.7f + 13.0f ) * 0.35f;
			float vATw = smoothstep( 0.4f, 0.6f, vATn );
			float vATMacro = 1.0f + ( ATNoise( vATPos * 0.008f + 71.0f ) - 0.5f ) * 2.0f * AT_MACRO;
'''
assert part.count(setup_old) == 1
part = part.replace(setup_old, setup_new, 1)

for ch in "wxyz":
    for tex, fn in (("TerrainDiffuse", "ATDiffuse"), ("TerrainNormal", "ATNormal")):
        old = f"tex2Dlod( {tex}, sample_terrain( IndexU.{ch}, IndexV.{ch}, vTileRepeat, vMipTexels, lod ) )"
        new = f"{fn}( IndexU.{ch}, IndexV.{ch}, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw )"
        assert part.count(old) == 1, old
        part = part.replace(old, new)

macro_old = '''		#ifndef NO_SHADER_TEXTURE_LOD
			terrain_normal =  terrain_normalRaw.rbg - 0.5f;'''
macro_new = '''			diffuse.rgb *= vATMacro;
		#ifndef NO_SHADER_TEXTURE_LOD
			terrain_normal =  terrain_normalRaw.rbg - 0.5f;'''
assert part.count(macro_old) == 1
part = part.replace(macro_old, macro_new, 1)

# HOD planet globes: colormap RGB = clean flat planet maps (planet_clean.py), colormap A = distance from the planet's
# centre (0 centre .. 1 rim, planet_terrain_gen.py). Up close only the map's hue tints the terrain; zoomed out the
# map replaces the terrain and is shaded as a sphere (normal from r and its gradient), the map wrapped onto the
# sphere (asin projection), day/night terminator, limb darkening and a sun glint. Borders / map modes are applied afterwards and stay visible. City lights come from the city tile now.
tint_old = '''			float4 TerrainColor = tex2D( TerrainColorTint, Input.uv2 );
'''
tint_new = '''			float4 TerrainColor = tex2D( TerrainColorTint, Input.uv2 );
			static const float PLANET_PAINT_NEAR = 450.0f;   // camera height where the globes start to show
			static const float PLANET_PAINT_FAR = 1100.0f;   // camera height where they fully cover the terrain
			static const float PLANET_PAINT_GAIN = 1.15f;    // brightness of the globes
			static const float3 PLANET_SUN_DIR = float3( -0.55f, 0.6f, 0.5f );   // light on the globes (x east, y up, z north)
			static const float PLANET_AMBIENT = 0.28f;       // light on the night side
			static const float PLANET_DAY = 1.3f;            // light at the sub-solar point
			static const float PLANET_LIMB = 0.3f;           // darkening towards the edge (0 = none)
			static const float PLANET_SPECULAR = 0.18f;      // sun glint
			static const float CITY_TILE_SLOT = 10.0f;       // atlas slot of the city texture (00_terrain.txt)
			float3 vPlanetPaint = TerrainColor.rgb;
			float vPlanetR = TerrainColor.a;
			float vPaintLum = dot( vPlanetPaint, vec3( 1.0f / 3.0f ) );
			TerrainColor.rgb = lerp( vec3( 0.5f ), saturate( 0.4f + 0.1f * vPlanetPaint / max( vPaintLum, 0.05f ) ), saturate( vPaintLum * 10.0f ) );
			float vPlanetFade = smoothstep( PLANET_PAINT_NEAR, PLANET_PAINT_FAR, vCamPos.y );
			// (no branch: texture reads inside a dynamic branch are not allowed to take gradients)
			float3 vGlobe = vPlanetPaint;
			{
				// sphere normal: r gives the tilt, the gradient of r the direction towards the rim
				float2 vTexel = float2( 2.0f / MAP_SIZE_X, 2.0f / MAP_SIZE_Y );
				float2 vGrad = float2(
					tex2D( TerrainColorTint, Input.uv2 + float2( vTexel.x, 0.0f ) ).a - tex2D( TerrainColorTint, Input.uv2 - float2( vTexel.x, 0.0f ) ).a,
					tex2D( TerrainColorTint, Input.uv2 + float2( 0.0f, vTexel.y ) ).a - tex2D( TerrainColorTint, Input.uv2 - float2( 0.0f, vTexel.y ) ).a );
				float2 vRim = vGrad / max( length( vGrad ), 0.00001f );
				float vMu = sqrt( saturate( 1.0f - vPlanetR * vPlanetR ) );
				float3 vSphereN = normalize( float3( vRim.x * vPlanetR, vMu, vRim.y * vPlanetR ) );
				// wrap the flat planet map onto the sphere: a point seen at radius r lies at arc asin(r) from the
				// centre, so the map is sampled at asin(r) / (pi / 2) of the radius -> features squeeze towards the limb
				// (r grows by |vGrad| over 4 map px -> planet radius = 4 / |vGrad| map px)
				float vRadius = 4.0f / max( length( vGrad ), 0.0001f );
				float vArc = asin( saturate( vPlanetR ) ) / 1.5707963f;
				float2 vWrapUV = Input.uv2 + float2( vRim.x / MAP_SIZE_X, vRim.y / MAP_SIZE_Y ) * ( vArc - vPlanetR ) * vRadius;
				float3 vWrapped = tex2D( TerrainColorTint, vWrapUV ).rgb;
				float3 vL = normalize( PLANET_SUN_DIR );
				float vLambert = saturate( dot( vSphereN, vL ) );
				float vGlobeLight = lerp( PLANET_AMBIENT, PLANET_DAY, pow( vLambert, 0.8f ) ) * ( 1.0f - PLANET_LIMB * ( 1.0f - vMu ) );
				float vGlint = pow( saturate( dot( reflect( -vL, vSphereN ), float3( 0.0f, 1.0f, 0.0f ) ) ), 24.0f ) * PLANET_SPECULAR;
				vGlobe = vWrapped * vGlobeLight + vGlint;
			}
'''
assert part.count(tint_old) == 1
part = part.replace(tint_old, tint_new, 1)
paint_old = '''			diffuse.rgb = GetOverlay( diffuse.rgb, TerrainColor.rgb, COLORMAP_OVERLAY_STRENGTH );
'''
paint_new = paint_old + '''			diffuse.rgb = lerp( diffuse.rgb, vGlobe * PLANET_PAINT_GAIN, vPlanetFade );
'''
assert part.count(paint_old) == 1
part = part.replace(paint_old, paint_new, 1)
# city lights: colormap alpha now holds the globe radius, so the light mask comes from the city tile
lights_old = '''			float CityLightsMask = TerrainColor.a;
'''
lights_new = '''			float4 vTileIds = IndexV * MAP_NUM_TILES + IndexU;
			float CityLightsMask = dot( 1.0f - saturate( abs( vTileIds - CITY_TILE_SLOT ) ), vec4( 0.25f ) ) * 0.8f;
'''
assert part.count(lights_old) == 1
part = part.replace(lights_old, lights_new, 1)

# HOD: zoomed out, country colours (gradient borders + occupation stripes) fade to a faint tint over the globes.
gb_old = '''			gradient_border_apply( diffuse.rgb,'''
gb_new = '''			float3 vPreBorder = diffuse.rgb;
			static const float PLANET_BORDER_KEEP = 0.2f;   // share of the country colour left when fully zoomed out
			gradient_border_apply( diffuse.rgb,'''
assert part.count(gb_old) == 1
part = part.replace(gb_old, gb_new, 1)
sc_old = '''			secondary_color_mask( diffuse.rgb, normal, Input.uv2, ProvinceSecondaryColorMap, vBloomAlpha );
'''
sc_new = sc_old + '''			diffuse.rgb = lerp( diffuse.rgb, vPreBorder, vPlanetFade * ( 1.0f - PLANET_BORDER_KEEP ) );
			vBloomAlpha *= 1.0f - vPlanetFade * ( 1.0f - PLANET_BORDER_KEEP );
'''
assert part.count(sc_old) == 1
part = part.replace(sc_old, sc_new, 1)

out = s[:a] + part + s[b:]
open("gfx/FX/pdxmap.shader", "w", encoding="utf-8", newline="\n").write(out)
print("ok", len(out.splitlines()), "lines")
