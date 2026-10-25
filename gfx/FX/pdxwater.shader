Includes = {
	"constants.fxh"
	"standardfuncsgfx.fxh"
	"pdxmap.fxh"
	"shadow.fxh"
	"tiled_pointlights.fxh"
	"fow.fxh"
}

PixelShader =
{
	Samplers =
	{
		HeightTexture =
		{
			Index = 0
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		LeanTexture1 =
		{
			Index = 1
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		LeanTexture2 =
		{
			Index = 2
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		ProvinceSecondaryColorMap =
		{
			Index = 3
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		SpecularMap =
		{
			Index = 4
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		WaterRefraction =
		{
			Index = 5
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		IceDiffuse =
		{
			Index = 6
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		IceNoise =
		{
			Index = 7
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		ReflectionCubeMap =
		{
			Index = 8
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
			Type = "Cube"
		}
		SnowMudTexture =
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
		GradientBorderChannel1 =
		{
			Index = 12
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		GradientBorderChannel2 =
		{
			Index = 13
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}		
		GradientBorderChannel3 =
		{
			Index = 14
			MagFilter = "Point"
			MinFilter = "Point"
			MipFilter = "Point"
			AddressU = "Clamp"
			AddressV = "Clamp"
		}
		ShadowMap =
		{
			Index = 15
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
			Type = "Shadow"
		}
	}
}


VertexStruct VS_INPUT_WATER
{
    int2 position			: POSITION;
};

VertexStruct VS_OUTPUT_WATER
{
    float4 position			: PDX_POSITION;
	float3 pos				: TEXCOORD0; 
	float2 uv				: TEXCOORD1;
	float4 screen_pos		: TEXCOORD2; 
	float3 cubeRotation     : TEXCOORD3;
	float4 vShadowProj      : TEXCOORD4;	
	float4 vScreenCoord		: TEXCOORD5;
	float2 uv_ice			: TEXCOORD6;	
};


ConstantBuffer( 3, 48 )
{
	float3 vTime_HalfPixelOffset;
};



VertexShader =
{
	MainCode VertexShader
	[[
		VS_OUTPUT_WATER main( const VS_INPUT_WATER VertexIn )
		{
			VS_OUTPUT_WATER VertexOut;
			VertexOut.pos = float3( VertexIn.position.x, WATER_HEIGHT, VertexIn.position.y );
			VertexOut.position = mul( ViewProjectionMatrix, float4( VertexOut.pos.x, VertexOut.pos.y, VertexOut.pos.z, 1.0f ) );
			VertexOut.screen_pos = VertexOut.position;
			VertexOut.screen_pos.y = FIX_FLIPPED_UV( VertexOut.screen_pos.y );
			VertexOut.uv = float2( ( VertexIn.position.x + 0.5f ) / MAP_SIZE_X,  ( VertexIn.position.y + 0.5f - MAP_SIZE_Y ) / -MAP_SIZE_Y );
			VertexOut.uv *= float2( MAP_POW2_X, MAP_POW2_Y ); //POW2
			VertexOut.uv_ice = VertexOut.uv * float2( MAP_SIZE_X, MAP_SIZE_Y ) * 0.1f;
			VertexOut.uv_ice *= float2( FOW_POW2_X, FOW_POW2_Y ); //POW2
		
			float vAnimTime = vTime_HalfPixelOffset.x * 0.01f;
			VertexOut.cubeRotation = normalize( float3( sin( vAnimTime ) * 0.5f, sin( vAnimTime ), cos( vAnimTime ) * 0.3f ) );
			
			VertexOut.vShadowProj = mul( ShadowMapTextureMatrix, float4( VertexOut.pos, 1.0f ) );	
			
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
	MainCode PixelShader
	[[
		// HOD: the sea is deep space. Star Wars galaxy chart (zoomed out) + parallax starfield + baked planet atmospheres.
		// Waves, reflections, refraction distortion and ice from vanilla pdxwater.shader are removed on purpose.

		float SpaceHash( float2 p )
		{
			float3 p3 = frac( float3( p.x, p.y, p.x ) * 0.1031f );
			p3 += dot( p3, p3.yzx + 33.33f );
			return frac( ( p3.x + p3.y ) * p3.z );
		}

		float SpaceNoise( float2 p )
		{
			float2 i = floor( p );
			float2 f = frac( p );
			float2 u = f * f * ( 3.0f - 2.0f * f );
			return lerp( lerp( SpaceHash( i ), SpaceHash( i + float2( 1.0f, 0.0f ) ), u.x ),
			             lerp( SpaceHash( i + float2( 0.0f, 1.0f ) ), SpaceHash( i + float2( 1.0f, 1.0f ) ), u.x ), u.y );
		}

		float SpaceFbm( float2 p )
		{
			float v = 0.0f;
			float amp = 0.5f;
			for ( int i = 0; i < 5; ++i )
			{
				v += amp * SpaceNoise( p );
				p = p * 2.03f + float2( 17.1f, 9.2f );
				amp *= 0.5f;
			}
			return v;
		}

		// Portable atan2 (the GLSL atan2 wrapper in defines_glsl.fxh swaps its arguments)
		float SpaceAtan2( float y, float x )
		{
			float a = atan( y / ( abs( x ) + 1e-5f ) );
			return x < 0.0f ? ( y >= 0.0f ? 3.14159265f - a : -3.14159265f - a ) : a;
		}

		// Star Wars galaxy chart, in map units. The regions (fills, outlines, names) are baked by
		// WIPGFX/plans & scripts/galaxy_regions.py round the planets' canon regions into the alpha of ice_diffuse.dds
		// (vChart); the arms, haze, core glow, murk and grid stay procedural here.
		static const float2 GALAXY_CORE = float2( 793.0f, 1551.0f );       // the Deep Core planets' centre
		static const float2 GALAXY_GRID_CELL = float2( 215.0f, 215.0f );   // chart grid squares
		static const float2 GALAXY_GRID_ORIGIN = float2( 860.6f, 1778.0f );
		static const float GALAXY_GRID_STRENGTH = 0.10f;

		float3 GalaxyColor( float2 vPos, float vChart, out float vArmMask )
		{
			float2 d = vPos - GALAXY_CORE;
			float d0 = length( d );

			// faint outer spiral arms, tightly wound so they read as arcs around the regions
			float theta = SpaceAtan2( d.y, d.x );
			float rn = d0 / 1700.0f;
			float phi = theta - log( max( rn, 0.05f ) ) / 0.28f + 0.4f + ( SpaceFbm( vPos * 0.0018f ) - 0.5f ) * 0.9f;
			float vArm = pow( saturate( 0.5f + 0.5f * cos( 2.0f * phi ) ), 4.0f ) * saturate( ( rn - 0.3f ) * 3.0f ) * saturate( 1.7f - rn );
			vArm *= 0.3f + 0.7f * saturate( ( 0.1f - vChart ) * 12.0f );   // canon chart: arms swirl outside the Mid Rim, not through known space
			float vGrain = SpaceFbm( vPos * 0.03f + 3.0f );
			float vHaze = exp( -rn / 0.45f ) * ( 0.6f + 0.5f * SpaceFbm( vPos * 0.006f + 40.0f ) );
			vArmMask = saturate( vArm * 2.0f + vChart );

			float3 vCol = float3( 0.08f, 0.17f, 0.25f ) * vHaze * 0.32f;
			vCol += float3( 0.20f, 0.40f, 0.52f ) * vArm * ( 0.35f + 0.9f * vGrain ) * 0.6f;
			vCol += float3( 1.00f, 0.97f, 0.92f ) * exp( -( d0 / 150.0f ) * ( d0 / 150.0f ) ) * 1.15f;  // Deep Core (was 1.6)
			vCol += float3( 0.75f, 0.88f, 1.00f ) * exp( -( d0 / 330.0f ) * ( d0 / 330.0f ) ) * 0.35f;  // Core glow (was 0.45)

			// Unknown Regions: murky west
			float vWest = saturate( ( GALAXY_CORE.x - 350.0f - vPos.x ) / 400.0f ) * saturate( 1.4f - abs( vPos.y - GALAXY_CORE.y ) / 1400.0f );
			float vMurk = 0.35f + 0.4f * SpaceFbm( vPos * 0.004f + 70.0f );
			vCol *= 1.0f - vWest * ( 1.0f - vMurk ) * 0.9f;
			vCol += float3( 0.42f, 0.64f, 0.76f ) * vChart * 0.42f;   // the regions after the murk, so their names stay legible

			// coordinate grid of the chart
			float2 g = abs( frac( ( vPos - GALAXY_GRID_ORIGIN ) / GALAXY_GRID_CELL ) - 0.5f ) * GALAXY_GRID_CELL;
			vCol += float3( 0.35f, 0.45f, 0.50f ) * ( 1.0f - saturate( min( g.x, g.y ) ) ) * GALAXY_GRID_STRENGTH;
			return vCol + float3( 0.003f, 0.005f, 0.012f );
		}

		// Drifting nebulae over the zoomed-out chart: one slowly flowing, domain-warped cloud field, coloured and
		// concentrated in a few canon nebulae (centres = the planets' positions in WIPGFX/Assets/galaxy_planets.json)
		float NebulaBlob( float2 vPos, float2 vCentre, float fRadius )
		{
			float2 d = ( vPos - vCentre ) / fRadius;
			return exp( -dot( d, d ) );
		}

		float3 NebulaColor( float2 vPos, float vTime, float vChart )
		{
			float t = vTime * 0.01f;
			float2 q = vPos * 0.0022f;
			float2 w = float2( SpaceFbm( q + float2( t, 0.3f * t ) ), SpaceFbm( q + float2( 5.2f, 1.3f ) - 0.8f * t ) );
			float n = SpaceFbm( q + 1.8f * w + float2( 0.0f, 0.5f * t ) );
			float vWisps = smoothstep( 0.42f, 0.85f, n ) * ( 0.6f + 0.4f * w.x );

			float3 vCol = float3( 0.10f, 0.16f, 0.30f ) * 0.35f;                                                  // faint everywhere
			vCol += float3( 0.45f, 0.40f, 0.85f ) * NebulaBlob( vPos, float2( 1690.0f, 1887.0f ), 260.0f );   // Ghost Nebula (Umbara)
			vCol += float3( 1.00f, 0.45f, 0.15f ) * NebulaBlob( vPos, float2( 2899.0f, 1848.0f ), 240.0f );   // the Maw (Kessel)
			vCol += float3( 0.15f, 0.75f, 0.70f ) * NebulaBlob( vPos, float2( 2475.0f, 1045.0f ), 280.0f );   // Rishi Maze (Rishi, Kamino)
			vCol += float3( 0.60f, 0.20f, 0.70f ) * NebulaBlob( vPos, float2( 250.0f, 1500.0f ), 420.0f );    // Unknown Regions
			return vCol * vWisps * 0.45f * ( 1.0f - 0.6f * vChart );
		}

		// Saturn-like ring round a planet disc, in map units: a tilted ellipse of bands with a dark gap. The planet's land
		// covers the inner part, so the ring passes behind the disc on both sides. Returns rgb and coverage in a.
		float4 PlanetRing( float2 vPos, float2 vCentre, float fRadius, float fAngle, float fTilt, float3 vTint )
		{
			float2 d = vPos - vCentre;
			float s = sin( fAngle );
			float c = cos( fAngle );
			float2 e = float2( d.x * c + d.y * s, ( d.y * c - d.x * s ) / fTilt );
			float k = length( e ) / fRadius;
			float vCover = smoothstep( 1.30f, 1.38f, k ) * ( 1.0f - smoothstep( 2.10f, 2.25f, k ) );
			vCover *= 1.0f - 0.85f * exp( -( k - 1.80f ) * ( k - 1.80f ) / 0.0012f );                           // Cassini-style gap
			vCover *= 0.55f + 0.45f * SpaceNoise( float2( k * 45.0f, 3.0f ) );                                       // banding
			float vFar = e.y > 0.0f ? 0.7f : 1.0f;                                                                  // far half dimmer
			return float4( vTint * vFar * ( 0.75f + 0.25f * SpaceNoise( float2( k * 9.0f, 8.0f ) ) ), vCover * 0.8f );
		}

		float3 ApplyRing( float3 vColor, float4 vRing )
		{
			return lerp( vColor, vRing.rgb, saturate( vRing.a ) );
		}

		// One star layer: one jittered star per grid cell, ~fDensity of cells lit
		float StarLayer( float2 p, float fCell, float fDensity, float fSize, float fTime )
		{
			float2 vCell = floor( p / fCell );
			float2 vLocal = frac( p / fCell ) - 0.5f;
			float vRnd = SpaceHash( vCell );
			float2 vOffset = float2( SpaceHash( vCell + 7.3f ), SpaceHash( vCell + 13.7f ) ) - 0.5f;
			float vDist = length( vLocal - vOffset * 0.7f ) * fCell;
			float vLit = step( 1.0f - fDensity, vRnd );
			float vTwinkle = 0.75f + 0.25f * sin( fTime * ( 1.0f + vRnd * 3.0f ) + vRnd * 40.0f );
			float vBright = ( vRnd - ( 1.0f - fDensity ) ) / fDensity; // 0..1 among lit cells
			float vCore = saturate( 1.0f - vDist / fSize );
			return vLit * vTwinkle * ( 0.35f + 0.65f * vBright ) * vCore * vCore;
		}

		float4 main( VS_OUTPUT_WATER Input ) : PDX_COLOR
		{
			float waterHeight = tex2D( HeightTexture, Input.uv ).x / ( 95.7f / 255.0f );
			float waterShore = saturate( ( waterHeight - 0.954f ) * 25.0f );
			float3 normal = float3( 0.0f, 1.0f, 0.0f );
			float vTime = vTime_HalfPixelOffset.x;
			float2 vPos = Input.pos.xz;

			// --- procedural galaxy chart, shown only when zoomed out; up close space is just dark with stars
			static const float GALAXY_BRIGHTNESS = 0.85f;
			static const float GALAXY_FADE_NEAR = 400.0f;    // camera height where the galaxy is gone
			static const float GALAXY_FADE_FAR = 1000.0f;    // camera height where it is fully shown (max 3000)
			float vGalaxyFade = smoothstep( GALAXY_FADE_NEAR, GALAXY_FADE_FAR, vCamPos.y );
			float vArmMask = 0.0f;
			float3 vColor = float3( 0.003f, 0.005f, 0.012f );
			float4 vIce = tex2D( IceDiffuse, Input.uv );   // rgb: the planets' atmospheres, a: the region chart
			if ( vGalaxyFade > 0.0f )
			{
				vColor = lerp( vColor, ( GalaxyColor( vPos, vIce.a, vArmMask ) + NebulaColor( vPos, vTime, vIce.a ) ) * GALAXY_BRIGHTNESS, vGalaxyFade );
				vArmMask *= vGalaxyFade;
			}
			// per-planet atmospheres: colormap_water_0.dds (black elsewhere) copied to map/terrain/ice_diffuse.dds by
			// planet_terrain_gen.py, read here at the map UV (= the terrain's uv2). Not through the refraction pass: that
			// buffer also holds the engine's mirrored copies of trees and buildings (the "reflections" in lakes and at
			// coasts). 0.3 ~ the underwater pass's tint * WATER_COLOR_LIGHTNESS mixed with the dark space floor
			vColor += vIce.rgb * 0.3f;

			// --- stars, three parallax layers (far layers pan slower than the map) for depth over the flat galaxy art
			float vStarSize = max( vCamPos.y * 0.0012f, 0.06f ); // keeps stars ~1-2 px wide at any zoom (camera y 50..3000)
			float2 vCam = vCamPos.xz;
			float vStars = 0.0f;
			vStars += StarLayer( vPos - vCam * 0.75f, 9.0f, 0.08f, vStarSize, vTime ) * 0.45f;
			vStars += StarLayer( vPos - vCam * 0.50f + 311.0f, 17.0f, 0.10f, vStarSize * 1.4f, vTime * 0.7f ) * 0.6f;
			vStars += StarLayer( vPos - vCam * 0.25f + 733.0f, 37.0f, 0.15f, vStarSize * 2.0f, vTime * 0.5f ) * 0.8f;
			float vTint = SpaceHash( floor( vPos * 0.11f ) );
			float3 vStarColor = lerp( float3( 0.75f, 0.85f, 1.0f ), float3( 1.0f, 0.88f, 0.7f ), vTint );
			// keep stars a quiet background layer: dim overall, and thinner when zoomed out (where they read as snow)
			static const float STAR_INTENSITY = 0.3f;
			float vStarFade = lerp( 1.0f, 0.35f, saturate( ( vCamPos.y - 300.0f ) / 1500.0f ) );
			vColor = lerp( vColor, vColor + vStarColor * vStars, STAR_INTENSITY * vStarFade * ( 0.5f + vArmMask ) );

			// --- planetary rings (centre and radius from WIPGFX/Assets/galaxy_planets.json; angle in radians, tilt = minor/major)
			vColor = ApplyRing( vColor, PlanetRing( vPos, float2( 1818.0f, 2696.0f ), 60.0f, 0.35f, 0.38f, float3( 0.80f, 0.66f, 0.48f ) ) );  // Yavin IV (gas giant Yavin's moon)
			vColor = ApplyRing( vColor, PlanetRing( vPos, float2( 428.0f, 604.0f ), 60.0f, -0.25f, 0.42f, float3( 0.62f, 0.70f, 0.78f ) ) );   // Endor (gas giant Endor's moon)
			vColor = ApplyRing( vColor, PlanetRing( vPos, float2( 2686.0f, 2375.0f ), 60.0f, 0.15f, 0.34f, float3( 0.70f, 0.60f, 0.72f ) ) );  // Iego
			vColor = ApplyRing( vColor, PlanetRing( vPos, float2( 2396.0f, 1461.0f ), 60.0f, -0.40f, 0.40f, float3( 0.72f, 0.70f, 0.50f ) ) ); // Nal Hutta
			vColor = ApplyRing( vColor, PlanetRing( vPos, float2( 2466.0f, 2172.0f ), 60.0f, 0.55f, 0.36f, float3( 0.78f, 0.74f, 0.66f ) ) );  // Saleucami

			float vBloomAlpha = 0.0f;
			gradient_border_apply( vColor, normal, Input.uv,
				GradientBorderChannel1, GradientBorderChannel2, 0.0f,
				vGBCamDistOverride_GBOutlineCutoff.zw * GB_OUTLINE_CUTOFF_SEA,
				vGBCamDistOverride_GBOutlineCutoff.xy, vBloomAlpha );

			secondary_color_mask( vColor, normal, Input.uv, ProvinceSecondaryColorMap, vBloomAlpha );

			float3 vOut = vColor;
		#ifndef LOW_END_GFX
			vOut = ApplyFOW( vOut, ShadowMap, Input.vScreenCoord );
		#endif

			dominance_fx_apply( vOut, normal,
				Input.uv,
				GradientBorderChannel1, GradientBorderChannel2, GradientBorderChannel3,
				vGBCamDistOverride_GBOutlineCutoff.zw * GB_OUTLINE_CUTOFF_SEA, vGBCamDistOverride_GBOutlineCutoff.xy, 0.0f );

			return float4( vOut, 1.0f - waterShore );
		}
	]]
}


BlendState BlendState
{
	BlendEnable = yes
	AlphaTest = no
	SourceBlend = "src_alpha"
	DestBlend = "inv_src_alpha"
	WriteMask = "RED|GREEN|BLUE"
}

Effect water_low_gfx
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShader"
	Defines = { "LOW_END_GFX" "NO_REFRACTIONS" }
}

Effect water_no_refractions
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShader"
	Defines = { "NO_REFRACTIONS" }
}

Effect water
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShader"
}


