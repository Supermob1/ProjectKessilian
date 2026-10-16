Includes = {
	"constants.fxh"
	"standardfuncsgfx.fxh"
	"tiled_pointlights.fxh"
	"pdxmap.fxh"
	"shadow.fxh"
	"fow.fxh"
}

PixelShader =
{
	Samplers =
	{
		TerrainDiffuse =
		{
			Index = 0
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		HeightNormal =
		{
			Index = 1
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		TerrainColorTint =
		{
			Index = 2
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		SnowTexture =
		{
			Index = 3
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		TerrainNormal =
		{
			Index = 4
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		TerrainIDMap =
		{
			Index = 5
			MagFilter = "Point"
			MinFilter = "Point"
			MipFilter = "None"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		ProvinceSecondaryColorMap =
		{
			Index = 6
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		SnowMudData =
		{
			Index = 7
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		CityLightsAndSnowNoise =
		{
			Index = 8
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		MudNormalSpec =
		{
			Index = 9
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		LightIndexMap =
		{
			Index = 10
			MagFilter = "Point"
			MinFilter = "Point"
			MipFilter = "Point"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		LightDataMap =
		{
			Index = 11
			MagFilter = "Point"
			MinFilter = "Point"
			MipFilter = "Point"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		ShadowMap =
		{
			Index = 12
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
			Type = "Shadow"
		}
		MudDiffuseGloss =
		{
			Index = 13
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		GradientBorderChannel1 =
		{
			Index = 14
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		GradientBorderChannel2 =
		{
			Index = 15
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
	}
}


VertexStruct VS_INPUT_TERRAIN_NOTEXTURE
{
    int4 position			: POSITION;
	int2 height				: TEXCOORD0;
};

VertexStruct VS_OUTPUT_TERRAIN
{
    float4 position			: PDX_POSITION;
	float2 uv				: TEXCOORD0;
	float2 uv2				: TEXCOORD1;
	float3 prepos 			: TEXCOORD2;
	float4 vShadowProj		: TEXCOORD3;
	float4 vScreenCoord		: TEXCOORD4;
};



VertexShader =
{
	MainCode VertexShader
	[[
		VS_OUTPUT_TERRAIN main( const VS_INPUT_TERRAIN_NOTEXTURE VertexIn )
		{
			VS_OUTPUT_TERRAIN VertexOut;
			
			float2 pos = VertexIn.position.xy * QuadOffset_Scale_IsDetail.z + QuadOffset_Scale_IsDetail.xy;
		
			float vSatPosZ = saturate( VertexIn.position.z ); // VertexIn.position.z can have a value [0-4], if != 0 then we shall displace vertex
			float vUseAltHeight = vSatPosZ * vSnap[ int( VertexIn.position.z - 1.0f ) ]; // the snap values are set to either 0 or 1 before each draw call to enable/disable snapping due to LOD
		
			pos += vUseAltHeight 
				* float2( 1.0f - VertexIn.position.w, VertexIn.position.w ) // VertexIn.position.w determines offset direction
				* QuadOffset_Scale_IsDetail.z; // and of course we need to scale it to the same LOD
		
			VertexOut.uv = float2( ( pos.x + 0.5f ) / MAP_SIZE_X,  ( pos.y + 0.5f ) / MAP_SIZE_Y );
			VertexOut.uv2.x = ( pos.x + 0.5f ) / MAP_SIZE_X;
			VertexOut.uv2.y = ( pos.y + 0.5f - MAP_SIZE_Y ) / -MAP_SIZE_Y;	
			VertexOut.uv2.xy *= float2( MAP_POW2_X, MAP_POW2_Y ); //POW2
		
			float vHeight = VertexIn.height.x * ( 1.0f - vUseAltHeight ) + VertexIn.height.y * vUseAltHeight;
			vHeight *= 0.01f;
		
			VertexOut.prepos = float3( pos.x, vHeight, pos.y );
			VertexOut.position = mul( ViewProjectionMatrix, float4( VertexOut.prepos, 1.0f ) );
			
			VertexOut.vShadowProj = mul( ShadowMapTextureMatrix, float4( VertexOut.prepos, 1.0f ) );
			
			// Output the screen-space texture coordinates
			VertexOut.vScreenCoord.x = ( VertexOut.position.x * 0.5 + VertexOut.position.w * 0.5 );
			VertexOut.vScreenCoord.y = ( VertexOut.position.w * 0.5 - VertexOut.position.y * 0.5 );
		#ifdef PDX_OPENGL
			VertexOut.vScreenCoord.y = -VertexOut.vScreenCoord.y;
		#endif	
			VertexOut.vScreenCoord.z = VertexOut.position.w;
			VertexOut.vScreenCoord.w = VertexOut.position.w;	
		
			return VertexOut;
		}
	]]
}

PixelShader =
{	
	MainCode PixelShaderTerrain
	[[		
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
		float HodCaustic( float2 p, float t )
		{
			// thin bright ridges of domain-warped value noise, two drifting layers (the second turned 37 degrees and
			// finer), a large patchy mask: no lattice, nothing repeats
			float2 w = float2( ATNoise( p * 0.21f + t * 0.03f ), ATNoise( p * 0.21f + 31.7f - t * 0.025f ) ) * 4.0f;
			float n1 = ATNoise( p * 0.9f + w + float2( t * 0.12f, -t * 0.08f ) );
			float2 r = float2( p.x * 0.8f - p.y * 0.6f, p.x * 0.6f + p.y * 0.8f ) * 1.6f;
			float n2 = ATNoise( r - w * 0.7f + float2( -t * 0.1f, t * 0.14f ) + 7.3f );
			float c1 = pow( saturate( 1.0f - abs( n1 * 2.0f - 1.0f ) ), 12.0f );
			float c2 = pow( saturate( 1.0f - abs( n2 * 2.0f - 1.0f ) ), 12.0f );
			return max( c1, c2 * 0.8f ) * ( 0.45f + 0.9f * ATNoise( p * 0.07f + 5.0f ) );
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

		float4 main( VS_OUTPUT_TERRAIN Input ) : PDX_COLOR
		{
			//return float4( 0, 1.0f, 0, 1.0f );
			//clip( Input.prepos.y + TERRAIN_WATER_CLIP_HEIGHT - WATER_HEIGHT );
		
			float2 vOffsets = float2( -0.5f / MAP_SIZE_X, -0.5f / MAP_SIZE_Y );
			
			float vAllSame;
			float4 IndexU;
			float4 IndexV;
			calculate_map_tex_index( tex2D( TerrainIDMap, Input.uv + vOffsets.xy ), IndexU, IndexV, vAllSame );
						
			float2 vTileRepeat = Input.uv2 * TERRAIN_TILE_FREQ;
			vTileRepeat.x *= MAP_SIZE_X/MAP_SIZE_Y;
			
			float lod = clamp( mipmapLevel( vTileRepeat ) - 0.5f, 0.0f, 6.0f );
			float vMipTexels = pow( 2.0f, ATLAS_TEXEL_POW2_EXPONENT - lod );
			float2 vTileRepeatB = ATRotate( vTileRepeat, AT_ANGLE ) * AT_SCALE + float2( 0.37f, 0.71f );
			float lodB = clamp( mipmapLevel( vTileRepeatB ) - 0.5f, 0.0f, 6.0f );
			float vMipTexelsB = pow( 2.0f, ATLAS_TEXEL_POW2_EXPONENT - lodB );
			float2 vATPos = Input.uv2 * float2( MAP_SIZE_X, MAP_SIZE_Y );
			float vATn = ATNoise( vATPos * AT_NOISE_FREQ ) * 0.65f + ATNoise( vATPos * AT_NOISE_FREQ * 2.7f + 13.0f ) * 0.35f;
			float vATw = smoothstep( 0.4f, 0.6f, vATn );
			float vATMacro = 1.0f + ( ATNoise( vATPos * 0.008f + 71.0f ) - 0.5f ) * 2.0f * AT_MACRO;
					
		#ifdef LOW_END_GFX
			float3 normal = float3( 0, 1, 0 );
		#else
			float3 normal = normalize( tex2D( HeightNormal, Input.uv2 ).rbg - 0.5f );
		#endif
			float4 diffuse = ATDiffuse( IndexU.w, IndexV.w, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw ).rgba;
			float vGlossiness = diffuse.a;
									
		#ifdef NO_SHADER_TEXTURE_LOD
			float3 terrain_normal = float3( 0,1,0 );
		#else	
			float3 terrain_normal;
			float4 terrain_normalRaw = ATNormal( IndexU.w, IndexV.w, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw );
		#endif //NO_SHADER_TEXTURE_LOD
			
			if ( vAllSame < 1.0f )
			{
				float4 ColorRD = ATDiffuse( IndexU.x, IndexV.x, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw ).rgba;
				float4 ColorLU = ATDiffuse( IndexU.y, IndexV.y, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw ).rgba;
				float4 ColorRU = ATDiffuse( IndexU.z, IndexV.z, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw ).rgba;
		
		#ifndef NO_SHADER_TEXTURE_LOD	
				float4 terrain_normalRD = ATNormal( IndexU.x, IndexV.x, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw );
				float4 terrain_normalLU = ATNormal( IndexU.y, IndexV.y, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw );
				float4 terrain_normalRU = ATNormal( IndexU.z, IndexV.z, vTileRepeat, vMipTexels, lod, vTileRepeatB, vMipTexelsB, lodB, vATw );
		#endif //NO_SHADER_TEXTURE_LOD
		
				float2 vFrac = frac( float2( Input.uv.x * MAP_SIZE_X - 0.5f, Input.uv.y * MAP_SIZE_Y - 0.5f ) );
		
				diffuse = lerp( 
					lerp( ColorRU, ColorLU, vFrac.x ),
					lerp( ColorRD, diffuse, vFrac.x ), 
						vFrac.y );
		
		#ifndef NO_SHADER_TEXTURE_LOD
				terrain_normalRaw = lerp( 
					lerp( terrain_normalRU, terrain_normalLU, vFrac.x ),
					lerp( terrain_normalRD, terrain_normalRaw, vFrac.x ), 
						vFrac.y );
		#endif //NO_SHADER_TEXTURE_LOD
			}
			
			diffuse.rgb *= vATMacro;

			// HOD: the water tile (atlas slot WATER_TILE_SLOT: marsh terrain_9, sea_town_30) is drawn as water: the water
			// plane shows space here, so seas on land provinces (Mon Cala) are painted by the terrain. vSea = the water
			// tile's share of this pixel, with the same bilinear weights as the four-corner diffuse blend above
			static const float WATER_TILE_SLOT = 6.0f;
			float4 vIsWater = 1.0f - saturate( abs( IndexV * MAP_NUM_TILES + IndexU - WATER_TILE_SLOT ) );
			float2 vFracW = frac( float2( Input.uv.x * MAP_SIZE_X - 0.5f, Input.uv.y * MAP_SIZE_Y - 0.5f ) );
			float vSea = dot( vIsWater, float4( ( 1.0f - vFracW.x ) * vFracW.y, vFracW.x * ( 1.0f - vFracW.y ),
			                                    ( 1.0f - vFracW.x ) * ( 1.0f - vFracW.y ), vFracW.x * vFracW.y ) );
			vSea = smoothstep( 0.15f, 0.85f, vSea );
			// HOD: the lava tile (atlas slot LAVA_TILE_SLOT: desert_hills = terrain.bmp 8) drawn as moving lava
			static const float LAVA_TILE_SLOT = 14.0f;
			float4 vIsLava = 1.0f - saturate( abs( IndexV * MAP_NUM_TILES + IndexU - LAVA_TILE_SLOT ) );
			float vLava = dot( vIsLava, float4( ( 1.0f - vFracW.x ) * vFracW.y, vFracW.x * ( 1.0f - vFracW.y ),
			                                    ( 1.0f - vFracW.x ) * ( 1.0f - vFracW.y ), vFracW.x * vFracW.y ) );
			vLava = smoothstep( 0.15f, 0.85f, vLava );
		#ifndef NO_SHADER_TEXTURE_LOD
			terrain_normal =  terrain_normalRaw.rbg - 0.5f; //UnpackRRxGNormal(terrain_normalRaw).rgb;
			//return float4(terrain_normal.rgb, 1.0f);
			#ifdef LOW_END_GFX
				float vSpec = 0.0f;
			#else
				float vSpec = terrain_normalRaw.a;
				vGlossiness = diffuse.a;
			#endif
		#else
			float vSpec = 0.0f;
		#endif

		#ifndef NO_SHADER_TEXTURE_LOD
		 	terrain_normal = normalize( terrain_normal );
			
			//Calculate terrain normal
			normal = RotateVectorByVector( normal, terrain_normal );
			normal = normalize(normal);
		#endif
			// HOD: a flat water surface with moving ripples instead of the ground's relief
			{
				// the slope of two drifting noise layers (finite differences): irregular ripples, no wave pattern
				float2 vRP = vATPos * 1.4f;
				float vRT = vGlobalTime;
				float2 vD1 = float2( vRT * 0.11f, vRT * 0.07f );
				float2 vD2 = float2( -vRT * 0.08f, vRT * 0.12f ) + 19.0f;
				float vE = 0.35f;
				float vHx = ATNoise( vRP + float2( vE, 0.0f ) + vD1 ) - ATNoise( vRP - float2( vE, 0.0f ) + vD1 )
				          + 0.5f * ( ATNoise( vRP * 2.3f + float2( vE, 0.0f ) + vD2 ) - ATNoise( vRP * 2.3f - float2( vE, 0.0f ) + vD2 ) );
				float vHz = ATNoise( vRP + float2( 0.0f, vE ) + vD1 ) - ATNoise( vRP - float2( 0.0f, vE ) + vD1 )
				          + 0.5f * ( ATNoise( vRP * 2.3f + float2( 0.0f, vE ) + vD2 ) - ATNoise( vRP * 2.3f - float2( 0.0f, vE ) + vD2 ) );
				float3 vRipple = normalize( float3( -vHx * 0.12f, 1.0f, -vHz * 0.12f ) );
				normal = normalize( lerp( normal, vRipple, vSea ) );
				normal = normalize( lerp( normal, float3( 0.0f, 1.0f, 0.0f ), vLava * 0.7f ) );   // molten rock lies flat
			}
			
			float4 TerrainColor = tex2D( TerrainColorTint, Input.uv2 );
			static const float PLANET_PAINT_NEAR = 450.0f;   // camera height where the globes start to show
			static const float PLANET_PAINT_FAR = 1100.0f;   // camera height where they fully cover the terrain
			static const float PLANET_PAINT_GAIN = 1.15f;    // brightness of the globes
			static const float3 PLANET_SUN_DIR = float3( -0.55f, 0.6f, 0.5f );   // light on the globes (x east, y up, z north)
			static const float PLANET_AMBIENT = 0.28f;       // light on the night side
			static const float PLANET_DAY = 1.3f;            // light at the sub-solar point
			static const float PLANET_LIMB = 0.3f;           // darkening towards the edge (0 = none)
			static const float PLANET_SPECULAR = 0.18f;      // sun glint
			static const float PLANET_OWNER_TINT = 0.55f;    // how much of the owner's map colour tints the globes
			static const float CITY_TILE_SLOT = 10.0f;       // atlas slot of the city texture (00_terrain.txt)
			float3 vPlanetPaint = TerrainColor.rgb;
			float vPlanetR = TerrainColor.a;
			float vPaintLum = dot( vPlanetPaint, vec3( 1.0f / 3.0f ) );
			TerrainColor.rgb = lerp( vec3( 0.5f ), saturate( 0.5f + 0.3f * ( vPlanetPaint / max( vPaintLum, 0.05f ) - 1.0f ) ), saturate( vPaintLum * 10.0f ) );   // planet hue up close (0.3: purple worlds read purple)
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
				float3 vWrapped = tex2D( MudDiffuseGloss, vWrapUV ).rgb;   // sharp 2x globe texture baked into the mud slot (planet_terrain_gen.py globe_texture)
				float3 vL = normalize( PLANET_SUN_DIR );
				float vLambert = saturate( dot( vSphereN, vL ) );
				float vGlobeLight = lerp( PLANET_AMBIENT, PLANET_DAY, pow( vLambert, 0.8f ) ) * ( 1.0f - PLANET_LIMB * ( 1.0f - vMu ) );
				float vGlint = pow( saturate( dot( reflect( -vL, vSphereN ), float3( 0.0f, 1.0f, 0.0f ) ) ), 24.0f ) * PLANET_SPECULAR;
				vGlobe = vWrapped * vGlobeLight + vGlint;
				// owner colour on the zoomed-out globes: the gradient border texture holds the map mode colours (top half,
				// as gradient_border_apply reads it); keep the globe's light and shade, swap in the owner's colour
				float vGBHalfPix = 0.5f / GB_TextureHeight;
				float2 vGBUV = float2( Input.uv2.x, Input.uv2.y * ( 0.5f - vGBHalfPix ) );
				float3 vOwnerCol = tex2D( GradientBorderChannel1, vGBUV ).rgb;
				float vOwned = tex2D( GradientBorderChannel2, vGBUV ).g;
				float vGlobeLum = dot( vGlobe, vec3( 1.0f / 3.0f ) );
				vGlobe = lerp( vGlobe, vOwnerCol * ( 0.35f + 1.3f * vGlobeLum ), saturate( vOwned ) * PLANET_OWNER_TINT );
			}

		#ifndef LOW_END_GFX
			float4 vTileIds = IndexV * MAP_NUM_TILES + IndexU;
			float CityLightsMask = dot( 1.0f - saturate( abs( vTileIds - CITY_TILE_SLOT ) ), vec4( 0.25f ) ) * 0.8f;
		#endif
	
			float vSnowAlpha = 1-vSpec;
			diffuse.rgb = GetOverlay( diffuse.rgb, TerrainColor.rgb, COLORMAP_OVERLAY_STRENGTH );
			// HOD: the water itself: deep teal to shallow turquoise (large slow patches), the seabed faint below,
			// animated caustic light and sun glints on the surface
			{
				float vT = vGlobalTime;
				float2 vP = vATPos * 0.9f;
				float vCaustic = HodCaustic( vP * 0.55f, vT ) * smoothstep( 0.4f, 0.75f, ATNoise( vATPos * 0.05f + 3.0f ) );
				float vGlintN = ATNoise( vP * 2.3f + float2( vT * 0.45f, -vT * 0.3f ) ) * ATNoise( vP * 3.1f - float2( vT * 0.3f, vT * 0.4f ) );
				float vGlint = pow( saturate( vGlintN * 1.6f ), 14.0f );
				float vShallow = saturate( ATNoise( vATPos * 0.04f + 17.0f ) * 1.4f - 0.2f );
				float3 vWaterCol = lerp( float3( 0.03f, 0.15f, 0.24f ), float3( 0.08f, 0.38f, 0.44f ), vShallow );
				float vBed = 0.25f + 0.75f * ATNoise( vATPos * 0.13f + 43.0f );
				float3 vUnder = vWaterCol + diffuse.rgb * float3( 0.06f, 0.11f, 0.12f ) * ( 0.5f + vShallow ) * vBed
				              + vCaustic * float3( 0.05f, 0.10f, 0.11f ) * ( 0.4f + vShallow ) + vGlint * 0.2f;
				diffuse.rgb = lerp( diffuse.rgb, vUnder, vSea );
				vGlossiness = lerp( vGlossiness, 1.0f, vSea );
				vSpec = lerp( vSpec, 0.9f, vSea );
			}
			float3 vLavaGlow = vec3( 0.0f );
			{
				float vT = vGlobalTime * 0.15f;
				float2 vP = vATPos * 0.6f;
				float2 vW = float2( ATNoise( vP * 0.35f + float2( vT, 0.0f ) ), ATNoise( vP * 0.35f + float2( 17.0f, vT * 0.8f ) ) ) * 3.0f;
				float vN = ATNoise( vP + vW ) * 0.65f + ATNoise( vP * 2.3f + vW * 1.7f - vT * 0.5f ) * 0.35f;
				float vCrack = pow( saturate( 1.0f - abs( vN * 2.0f - 1.0f ) ), 5.0f );
				float vPool = smoothstep( 0.55f, 0.8f, ATNoise( vP * 0.12f + float2( -vT * 0.3f, 9.0f ) ) );
				float vPulse = 0.85f + 0.15f * sin( vGlobalTime * 1.3f + vN * 6.0f );
				float vHot = saturate( max( vCrack, vPool ) ) * vPulse;
				float3 vCrust = float3( 0.07f, 0.05f, 0.045f ) * ( 0.7f + 0.6f * ATNoise( vP * 3.7f ) ) + diffuse.rgb * 0.08f;
				float3 vMolten = lerp( float3( 0.85f, 0.18f, 0.02f ), float3( 1.0f, 0.75f, 0.25f ), vHot * vHot );
				diffuse.rgb = lerp( diffuse.rgb, lerp( vCrust, vMolten * 0.5f, vHot ), vLava );
				vLavaGlow = vMolten * vHot * vLava * 1.1f;
				vGlossiness = lerp( vGlossiness, 0.3f, vLava );
				vSpec = lerp( vSpec, 0.1f, vLava );
			}
			diffuse.rgb = lerp( diffuse.rgb, vGlobe * PLANET_PAINT_GAIN, vPlanetFade );

			float4 vMudSnow = GetMudSnowColor( Input.prepos, SnowMudData );	
			diffuse.rgb = ApplySnow( diffuse.rgb, Input.prepos, normal, vMudSnow, SnowTexture, CityLightsAndSnowNoise, vGlossiness, vSnowAlpha );
			// HOD: no mud: the mud slot holds the globe texture
							
			// Gradient Borders
			float vBloomAlpha = 0.0f;
			float3 vPreBorder = diffuse.rgb;
			static const float PLANET_BORDER_KEEP = 0.2f;   // share of the country colour left when fully zoomed out
			gradient_border_apply( diffuse.rgb, normal, Input.uv2, GradientBorderChannel1, GradientBorderChannel2, 1.0f, vGBCamDistOverride_GBOutlineCutoff.zw, vGBCamDistOverride_GBOutlineCutoff.xy, vBloomAlpha );
					
			// Secondary color mask
			secondary_color_mask( diffuse.rgb, normal, Input.uv2, ProvinceSecondaryColorMap, vBloomAlpha );
			diffuse.rgb = lerp( diffuse.rgb, vPreBorder, vPlanetFade * ( 1.0f - PLANET_BORDER_KEEP ) );
			vBloomAlpha *= 1.0f - vPlanetFade * ( 1.0f - PLANET_BORDER_KEEP );

			LightingProperties lightingProperties;
			lightingProperties._WorldSpacePos = Input.prepos;
			lightingProperties._ToCameraDir = normalize(vCamPos - Input.prepos);
			lightingProperties._Normal = normal;
			
		#ifdef PDX_IMPROVED_BLINN_PHONG

			#ifdef NO_SHADER_TEXTURE_LOD
				float SpecRemapped = 0.1;
			#else
				float SpecRemapped = vSpec * vSpec * 0.4;
			#endif // NO_SHADER_TEXTURE_LOD			

			float MetalnessRemapped = 0.0;// - (1.0 - vProperties.b) * (1.0 - vProperties.b);
			lightingProperties._Diffuse = MetalnessToDiffuse(MetalnessRemapped, diffuse.rgb);
			lightingProperties._Glossiness = vGlossiness;
			lightingProperties._SpecularColor = MetalnessToSpec(MetalnessRemapped, diffuse.rgb, SpecRemapped);
			lightingProperties._NonLinearGlossiness = GetNonLinearGlossiness(vGlossiness);
		#else
			lightingProperties._Diffuse = diffuse.rgb;
			lightingProperties._Glossiness = vGlossiness;
			lightingProperties._SpecularColor = vec3(vSpec);
			lightingProperties._NonLinearGlossiness = GetNonLinearGlossiness(vGlossiness);

		#endif //PDX_IMPROVED_BLINN_PHONG

			float3 diffuseLight = vec3(0.0);
			float3 specularLight = vec3(0.0);

			float fShadowTerm = max(GetShadowScaled( SHADOW_WEIGHT_TERRAIN, Input.vScreenCoord, ShadowMap ), 0.1f );
		
			CalculateSunLight( lightingProperties, fShadowTerm, diffuseLight, specularLight );

		#ifndef LOW_END_GFX
			CalculatePointLights( lightingProperties, LightDataMap, LightIndexMap, diffuseLight, specularLight);
		#endif
			
		#ifdef PDX_IMPROVED_BLINN_PHONG
			float3 vEyeDir = normalize( Input.prepos - vCamPos.xyz );
			//float3 reflection = reflect( vEyeDir, lightingProperties._Normal );
			//float MipmapIndex = GetEnvmapMipLevel(lightingProperties._Glossiness); 
			
			float3 reflectiveColor = FAKE_CUBEMAP_COLOR; //texCUBElod( EnvironmentMap, float4(reflection, MipmapIndex) ).rgb * CubemapIntensity;
			specularLight += reflectiveColor * FresnelGlossy(lightingProperties._SpecularColor, -vEyeDir, lightingProperties._Normal, lightingProperties._Glossiness);
		#endif
			
			float3 vOut = ComposeLightSnow(lightingProperties, diffuseLight, specularLight, vSnowAlpha);
		
			vOut = lerp( vOut, diffuse.rgb, BORDER_LIGHT_REMOVAL_FACTOR * ( 1 - vBloomAlpha ) );
			vOut += vLavaGlow * ( 1.0f - vPlanetFade );   // HOD: the lava glows on its own (not on the zoomed-out globes)
				
			float3 vGlobeNormal = CalcGlobeNormal( Input.prepos.xz );
			float vNightFactor = DayNightFactor( vGlobeNormal );

		#ifndef LOW_END_GFX
			float3 CityLights = tex2D( CityLightsAndSnowNoise, Input.prepos.xz * CITY_LIGHTS_TILING ).rgb;
			vOut += CityLights * CITY_LIGHTS_INTENSITY * CityLightsMask * vNightFactor;
		#endif

			float3 vFOW = ApplyFOW( vOut, ShadowMap, Input.vScreenCoord );
			vOut = lerp( vFOW, vOut, BORDER_FOW_REMOVAL_FACTOR * ( 1 - vBloomAlpha ) );
		
		#ifndef LOW_END_GFX
			vOut = ApplyDistanceFog( vOut, Input.prepos );
		#endif
			
			vOut = DayNightWithBlend( vOut, vGlobeNormal, lerp(BORDER_NIGHT_DESATURATION_MAX, 1.0f, vBloomAlpha) );
			
			DebugReturn(vOut, lightingProperties, fShadowTerm);

		#ifdef LOW_END_GFX
			return float4( vOut, vNightFactor * CITY_LIGHTS_BLOOM_FACTOR );
		#else
			return float4( vOut, saturate(CityLightsMask * vNightFactor * CITY_LIGHTS_BLOOM_FACTOR) );
		#endif
		}		
	]]

	MainCode PixelShaderUnderwater
	[[
		float4 main( VS_OUTPUT_TERRAIN Input ) : PDX_COLOR
		{
			clip( WATER_HEIGHT - Input.prepos.y + TERRAIN_WATER_CLIP_HEIGHT );
		
			float3 normal = normalize( tex2D( HeightNormal,Input.uv2 ).rbg - 0.5f );
			float3 diffuse = tex2D( TerrainDiffuse, Input.uv2 * float2(( MAP_SIZE_X / 32.0f ), ( MAP_SIZE_Y / 32.0f ) ) ).rgb;

			// TOMASZ: SnowTexture texture slot here was some kind of normalmap that is obsolete 
			//         and makes no visual effect, so I've removed it.
			//float3 offset = tex2D( SnowTexture, Input.uv2 * float2(( MAP_SIZE_X / 32.0f ), ( MAP_SIZE_Y / 32.0f ) ) ).rgb;
			//offset -= vec3(0.5);
			
			float3 waterColorTint = tex2D( TerrainColorTint, Input.uv2 /*+ offset.xy * WATER_RIPPLE_EFFECT*/ ).rgb;		
			waterColorTint *= WATER_COLOR_LIGHTNESS;
			
			float vMin = 5.3f; //5.3f; Depthfog ish for bottom
			float vMax = 13.0f; //30.0f; 

			//float vWaterAlpha = saturate( Input.prepos.y * Input.prepos.y * Input.prepos.y * WATER_HEIGHT_RECP_SQUARED * WATER_HEIGHT_RECP  );
			float vWaterAlpha = saturate(( Input.prepos.y - vMin ) / ( vMax - vMin ) );
		
			float vGlossiness = MAP_SPECULAR_WIDTH;
		
			LightingProperties lightingProperties;
			lightingProperties._WorldSpacePos = Input.prepos;
			lightingProperties._ToCameraDir = normalize(vCamPos - Input.prepos);
			lightingProperties._Normal = normal;
			lightingProperties._Diffuse = diffuse;

			lightingProperties._Glossiness = vGlossiness;
			lightingProperties._SpecularColor = SunDiffuseIntensity.rgb * 0.1f;
			lightingProperties._NonLinearGlossiness = GetNonLinearGlossiness(vGlossiness);
			
			float3 diffuseLight = vec3(0.0);
			float3 specularLight = vec3(0.0);		
			float fShadowTerm = GetShadowScaled( SHADOW_WEIGHT_TERRAIN, Input.vScreenCoord, ShadowMap );
		
			CalculateSunLight( lightingProperties, fShadowTerm, diffuseLight, specularLight );
			CalculatePointLights( lightingProperties, LightDataMap, LightIndexMap, diffuseLight, specularLight);
			
			float3 vOut = ComposeLight(lightingProperties, diffuseLight, specularLight );
						
			vOut = lerp( waterColorTint, vOut, vWaterAlpha );			
		
			return float4( vOut, 1.0f );
		}
	]]

	MainCode PixelShaderTerrainUnlit
	[[
		float4 main( VS_OUTPUT_TERRAIN Input ) : PDX_COLOR
		{	
			// Grab the shadow term
			float fShadowTerm = CalculateShadow( Input.vShadowProj, ShadowMap);
			
			float FogColorFactor = 0.0;
			float FogAlphaFactor = 0.0;
			GetFogFactors( FogColorFactor, FogAlphaFactor, Input.prepos, 0.0, TerrainDiffuse, HeightNormal, TerrainColorTint);
			return float4( fShadowTerm, FogColorFactor, FogAlphaFactor, 1.0f );
		}
	]]
}


BlendState BlendState
{
	BlendEnable = no
	AlphaTest = no
	WriteMask = "RED|GREEN|BLUE|ALPHA"
}


Effect terrain_low_gfx
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShaderTerrain"
	Defines = { "LOW_END_GFX" }
}

Effect terrain
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShaderTerrain"
	Defines = { "PDX_IMPROVED_BLINN_PHONG" }
}

Effect underwater
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShaderUnderwater"
}

Effect terrainunlit
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShaderTerrainUnlit"
}

