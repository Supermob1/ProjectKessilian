Includes = {
	"constants.fxh"
	"standardfuncsgfx.fxh"
}

PixelShader =
{
	Samplers =
	{
		DiffuseTexture =
		{
			Index = 0
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		FoWTexture =
		{
			Index = 1
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
		FoWDiffuse =
		{
			Index = 2
			MagFilter = "Linear"
			MinFilter = "Linear"
			MipFilter = "Linear"
			AddressU = "Wrap"
			AddressV = "Wrap"
		}
	}
}


VertexStruct VS_INPUT
{
    float4 vPosition		: POSITION;
	float4 vUV				: TEXCOORD0;
};

VertexStruct VS_OUTPUT
{
    float4  vPosition 	: PDX_POSITION;
    float2	vUV		  	: TEXCOORD0;
	float3	vPos		: TEXCOORD1;
	float2	vUVExtra	: TEXCOORD2;   // the engine's uv.zw (unused by vanilla; shown by LANE_DEBUG)
};

VertexShader =
{
	MainCode VertexShader
	[[
		VS_OUTPUT main( const VS_INPUT v )
		{
			VS_OUTPUT Out;

			float4 vPos = float4( v.vPosition.xyz, 1.0f );
		   	Out.vPosition  = mul( ViewProjectionMatrix, vPos );

			// move z value slightly closer to camera to avoid intersections with terrain
			float4 vDistortedPos = vPos - float4( vCamLookAtDir * 0.05f, 0.0f );
			float vNewZ = dot( vDistortedPos, float4( GetMatrixData( ViewProjectionMatrix, 2, 0 ), GetMatrixData( ViewProjectionMatrix, 2, 1 ), GetMatrixData( ViewProjectionMatrix, 2, 2 ), GetMatrixData( ViewProjectionMatrix, 2, 3 ) ) );
			Out.vPosition.z = vNewZ;

		   	Out.vUV = v.vUV.xy;
			Out.vUVExtra = v.vUV.zw;
			Out.vPos = vPos.rgb;

			return Out;
		}


	]]
}

PixelShader =
{
	MainCode PixelShader
	[[
		// HOD: hyperlanes. The engine's strait strip (straight, from one end of the lane to the other) drawn as a band of
		// hyperspace streaks seen from above: thin light lines rushing along the lane, both ways, over a faint glowing
		// band. strait.dds is no longer read. uv.x runs across the strip (vanilla's line sat in its middle: the strip is
		// much wider than the old line), uv.y along it (tiles).
		// The strip's width is set by the engine (no define found); the band can fill all of it, not more.
		static const float LANE_WIDTH     = 1.0f;    // share of the strip's width the band fills (vanilla line ~0.03)
		static const float LANE_BASE_FAR  = 0.20f;   // the band's glow when zoomed fully out (readable on the chart)
		static const int   LANE_DEBUG     = 0;       // 1: show what the engine sends (red = uv.x across, green = uv.y
		                                             // along, blue = |uv.z|, white stripes = uv.w), to plan wider bands
		static const float LANE_LANES     = 9.0f;    // streak tracks across the band
		static const float LANE_SPEED     = 3.0f;    // streak speed, uv.y units per second
		static const float LANE_DENSITY   = 0.35f;   // streak repeats per uv.y unit
		static const float LANE_STREAK    = 0.45f;   // streak length, share of its repeat
		static const float LANE_ALPHA     = 0.38f;   // brightest a streak gets (keeps it see-through, no flash)
		static const float LANE_BASE      = 0.07f;   // the band's own faint glow
		static const float3 LANE_COLOR    = float3( 0.62f, 0.84f, 1.00f );
		static const float3 LANE_CORE     = float3( 0.95f, 0.98f, 1.00f );

		float LaneHash( float n )
		{
			return frac( sin( n * 12.9898f ) * 43758.5453f );
		}

		float4 main( VS_OUTPUT v ) : PDX_COLOR
		{
			float vAcross = ( frac( v.vUV.x ) - 0.5f ) * 2.0f / LANE_WIDTH;     // -1..1 inside the band
			float vBand = saturate( 1.0f - abs( vAcross ) );
			float vEdge = smoothstep( 0.0f, 0.35f, vBand );                     // soft band edges

			// streak tracks: each with its own speed, phase, direction (alternating) and brightness
			float vTrack = ( vAcross * 0.5f + 0.5f ) * LANE_LANES;
			float vIdx = floor( vTrack );
			float vInTrack = frac( vTrack );
			float vThin = pow( saturate( 1.0f - abs( vInTrack - 0.5f ) * 2.0f ), 3.0f );   // thin line in its track
			float vDir = fmod_loop( vIdx, 2.0f ) < 1.0f ? 1.0f : -1.0f;
			float vRnd = LaneHash( vIdx + 3.7f );
			float vPhase = v.vUV.y * LANE_DENSITY * ( 0.7f + 0.6f * vRnd )
			             - vDir * vGlobalTime * LANE_SPEED * LANE_DENSITY * ( 0.6f + 0.8f * LaneHash( vIdx + 9.1f ) ) + vRnd * 7.0f;
			float vCycle = frac( vPhase * vDir );
			float vStreak = saturate( vCycle / LANE_STREAK );                          // tail fading behind a bright head
			vStreak = vStreak * vStreak * step( vCycle, LANE_STREAK );
			float vLine = vThin * vStreak * ( 0.5f + 0.5f * vRnd );

			// zoomed out: a stronger band so the lanes read clearly on the chart, streaks a little calmer
			float vFar = saturate( ( vCamPos.y - 500.0f ) / 1200.0f );
			vLine *= 1.0f - 0.3f * vFar;
			float vBase = lerp( LANE_BASE, LANE_BASE_FAR, vFar );

			float3 vColor = lerp( LANE_COLOR, LANE_CORE, saturate( vLine * 1.5f ) );
			float vAlpha = ( vBase * vBand + LANE_ALPHA * vLine ) * vEdge;
			vColor = ApplyDistanceFog( vColor, v.vPos );
			if ( LANE_DEBUG == 1 )
			{
				float vStripe = step( 0.5f, frac( v.vUVExtra.y * 4.0f ) );
				return float4( lerp( float3( frac( v.vUV.x ), frac( v.vUV.y ), saturate( abs( v.vUVExtra.x ) ) ), vec3( 1.0f ), vStripe * 0.5f ), 1.0f );
			}
			return float4( vColor, saturate( vAlpha ) );
		}


	]]
}


BlendState BlendState
{
	BlendEnable = yes
	AlphaTest = no
	SourceBlend = "SRC_ALPHA"
	DestBlend = "INV_SRC_ALPHA"
}

DepthStencilState DepthStencil
{
	DepthEnable = yes
}

RasterizerState RasterizerState
{
	FillMode = "FILL_SOLID"
	CullMode = "CULL_BACK"
	FrontCCW = no
}


Effect strait
{
	VertexShader = "VertexShader"
	PixelShader = "PixelShader"
}

