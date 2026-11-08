// Panda Colonists v6.1 - shell + fin fur for Timberborn characters (URP 17.5 / Unity 6000.5).
//
// Submesh 0 (_IsFin = 0): the panda duplicated N times (shells), innermost first, alpha blended.
// Submesh 1 (_IsFin = 1): fins - a strand card standing on every edge, only visible near the silhouette,
//                          so outlines are real fuzzy strands instead of stacked shell layers.
// Per vertex:
//   TEXCOORD1.xy  fins: (metres along the edge, random seed)
//   TEXCOORD2.xy  (original vertex index for the game's vertex animation, height 0..1)
//   TEXCOORD3.xyz rest-pose comb direction
//   TEXCOORD4.xyz rest-pose smoothed (welded) normal: shells/fins grow along it, so no gaps at seams/hard edges
Shader "PandaColonists/ShellFurV61"
{
    Properties
    {
        _BaseMap ("Base Map", 2D) = "white" {}
        _FurMask ("Fur Mask (R=length, G=panda AO)", 2D) = "white" {}
        _FurLength ("Fur Length (m)", Float) = 0.013
        _FurDensity ("Strands per UV unit", Float) = 560
        _FurThickness ("Strand thickness", Range(0.1, 1.5)) = 1.0
        _CombStrength ("Comb lean", Range(0, 2)) = 0.85
        _FurGravity ("Gravity droop", Range(0, 1)) = 0.3
        _Clump ("Clumping", Range(0, 1.5)) = 0.4
        _ClumpSize ("Clump size (strands)", Float) = 5
        _FaceSoften ("Soften fur seen head-on", Range(0, 1)) = 0.85
        _RootFill ("Dense undercoat", Range(0, 1)) = 0.95
        _AOStrength ("Panda ambient occlusion", Range(0, 1)) = 0.8
        _RootDarken ("Root darkening", Range(0, 1)) = 0.32
        _TipLighten ("Tip lightening", Range(0, 0.5)) = 0.03
        _Wrap ("Light wrap", Range(0, 1)) = 0.3
        _SpecStrength ("Sheen strength", Range(0, 1)) = 0.06
        _SpecPower ("Sheen tightness", Range(4, 256)) = 40
        _Backlight ("Backlit rim", Range(0, 1)) = 0.35
        _MotionGain ("Animation follow-through", Range(0, 4)) = 1.2
        _Wind ("Wind sway", Range(0, 1)) = 0.25
        _FurOpacity ("Opacity", Range(0, 1)) = 1
        _ShellBoost ("Shell alpha boost", Float) = 1
        _FurFade ("Fur fade (distance LOD)", Range(0, 1)) = 1
        _LengthScale ("Per-panda length scale", Float) = 1
        _DensityScale ("Per-panda density scale", Float) = 1
        _MoveLag ("Move lag (world, fur lengths)", Vector) = (0, 0, 0, 0)
        _IsFin ("Fin material", Float) = 0
        _FinStrands ("Fin strands per metre", Float) = 1000
        _FinLength ("Fin length vs shells", Float) = 1.25
        [Enum(UnityEngine.Rendering.CullMode)] _Cull ("Cull", Float) = 2

        // ---- copied every frame from the panda's own material by the mod DLL ----
        [NoScaleOffset] _Offsets ("VAT Offsets", 2D) = "black" {}
        [NoScaleOffset] _Rotations ("VAT Rotations", 2D) = "black" {}
        _AnimationTime ("AnimationTime", Float) = 0
        _AnimatedVertexCount ("AnimatedVertexCount", Float) = 0
        _FrameCount ("FrameCount", Float) = 1
        _Looped ("Looped", Float) = 1
        _AnimationEnabled ("AnimationEnabled", Float) = 0
        [NoScaleOffset] _ContaminationDiffuse ("Contamination Diffuse", 2D) = "black" {}
        _BadwaterContamination ("BadwaterContamination", Float) = 0
        [NoScaleOffset] _WorkerOutfitDiffuse ("WorkerOutfitDiffuse", 2D) = "black" {}
        _WetFur ("WetFur", Float) = 0
        [NoScaleOffset] _InjuryDiffuse ("Injury Diffuse", 2D) = "black" {}
        _TintColor ("TintColor", Color) = (1, 1, 1, 1)
        _TintEnabled ("TintEnabled", Float) = 0
    }

    HLSLINCLUDE
    #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

    TEXTURE2D(_BaseMap);              SAMPLER(sampler_BaseMap);
    TEXTURE2D(_FurMask);              SAMPLER(sampler_FurMask);
    TEXTURE2D(_Offsets);
    TEXTURE2D(_Rotations);
    TEXTURE2D(_ContaminationDiffuse); SAMPLER(sampler_ContaminationDiffuse);
    TEXTURE2D(_WorkerOutfitDiffuse);  SAMPLER(sampler_WorkerOutfitDiffuse);
    TEXTURE2D(_InjuryDiffuse);        SAMPLER(sampler_InjuryDiffuse);
    SAMPLER(sampler_linear_repeat);
    SAMPLER(sampler_linear_clamp);

    CBUFFER_START(UnityPerMaterial)
        float4 _BaseMap_ST;
        float4 _FurMask_ST;
        float4 _MoveLag;
        float4 _TintColor;
        float _TintEnabled;
        float _RootFill;
        float _AOStrength;
        float _FurLength;
        float _FurDensity;
        float _FurThickness;
        float _CombStrength;
        float _FurGravity;
        float _Clump;
        float _ClumpSize;
        float _FaceSoften;
        float _RootDarken;
        float _TipLighten;
        float _Wrap;
        float _SpecStrength;
        float _SpecPower;
        float _Backlight;
        float _MotionGain;
        float _Wind;
        float _FurOpacity;
        float _ShellBoost;
        float _FurFade;
        float _LengthScale;
        float _DensityScale;
        float _IsFin;
        float _FinStrands;
        float _FinLength;
        float _Cull;
        float _AnimationTime;
        float _AnimatedVertexCount;
        float _FrameCount;
        float _Looped;
        float _AnimationEnabled;
        float _BadwaterContamination;
        float _WetFur;
    CBUFFER_END
    ENDHLSL

    SubShader
    {
        // Transparent queue: drawn after all opaque geometry (works with or without depth priming)
        Tags { "RenderPipeline" = "UniversalPipeline" "RenderType" = "Transparent" "Queue" = "Transparent-20" "IgnoreProjector" = "True" }
        LOD 100

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull [_Cull]
            ZWrite Off
            ZTest LEqual
            Blend SrcAlpha OneMinusSrcAlpha, One OneMinusSrcAlpha

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex FurVert
            #pragma fragment FurFrag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                float2 uv0        : TEXCOORD0;
                float2 finData    : TEXCOORD1;
                float2 shellData  : TEXCOORD2;
                float3 combOS     : TEXCOORD3;
                float3 smoothOS   : TEXCOORD4;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv         : TEXCOORD0;
                float3 normalWS   : TEXCOORD1;
                float3 positionWS : TEXCOORD2;
                float3 rootWS     : TEXCOORD3;   // lighting/shadows are evaluated at the root (no shell acne)
                float3 strandWS   : TEXCOORD4;
                float4 data       : TEXCOORD5;   // x height, y fur amount, z wet, w fog
                float2 fin        : TEXCOORD6;   // x strand coordinate along the edge, y silhouette factor
            };

            float3 RotateByQuat(float3 v, float4 q)
            {
                float3 t = 2.0 * cross(q.xyz, v);
                return v + q.w * t + cross(q.xyz, t);
            }

            float3 SampleOffset(float vertexIndex, float frameIndex)
            {
                float3 o;
                if (_Looped > 0.5)
                    o = SAMPLE_TEXTURE2D_LOD(_Offsets, sampler_linear_repeat, float2(vertexIndex, frameIndex), 0).xyz;
                else
                    o = SAMPLE_TEXTURE2D_LOD(_Offsets, sampler_linear_clamp, float2(vertexIndex, saturate(frameIndex)), 0).xyz;
                return o;
            }

            float4 SampleRotation(float vertexIndex, float frameIndex)
            {
                float4 r;
                if (_Looped > 0.5)
                    r = SAMPLE_TEXTURE2D_LOD(_Rotations, sampler_linear_repeat, float2(vertexIndex, frameIndex), 0);
                else
                    r = SAMPLE_TEXTURE2D_LOD(_Rotations, sampler_linear_clamp, float2(vertexIndex, frameIndex), 0);
                return r;
            }

            // Same maths as Timberborn's AnimateVAT.hlsl, plus the offset a few frames earlier (follow-through)
            void AnimateVAT(float vertexId, float3 inPos, float3 inNormal, out float3 pos, out float3 nrm, out float3 vel)
            {
                pos = inPos; nrm = inNormal; vel = 0;
                if (_AnimationEnabled > 0.5 && vertexId < _AnimatedVertexCount)
                {
                    float vertexIndex = (vertexId + 0.5) / _AnimatedVertexCount;
                    float frameIndex = _AnimationTime + 0.5 * (1.0 / _FrameCount);
                    float targetFrame = frameIndex * _FrameCount;
                    float fromFrame = floor(targetFrame) / _FrameCount;
                    float toFrame = ceil(targetFrame) / _FrameCount;
                    float w = frac(targetFrame);
                    float3 offset = SampleOffset(vertexIndex, frameIndex);
                    float3 prev = SampleOffset(vertexIndex, frameIndex - 2.0 / _FrameCount);
                    float4 r0 = SampleRotation(vertexIndex, fromFrame);
                    float4 r1 = SampleRotation(vertexIndex, toFrame);
                    pos = inPos + offset;
                    nrm = normalize(lerp(RotateByQuat(float3(-1, 0, 0), r0), RotateByQuat(float3(-1, 0, 0), r1), w));
                    vel = offset - prev;
                }
            }

            Varyings FurVert(Attributes input)
            {
                Varyings o = (Varyings)0;
                float3 pos, nrm, vel;
                AnimateVAT(input.shellData.x, input.positionOS.xyz, input.normalOS, pos, nrm, vel);
                float h = input.shellData.y;

                float mask = SAMPLE_TEXTURE2D_LOD(_FurMask, sampler_FurMask, input.uv0, 0).r;
                float wet = saturate(_WetFur);
                float dirt = saturate(_BadwaterContamination);
                float fade = saturate(_FurFade);
                float len = _FurLength * _LengthScale * mask * lerp(0.55, 1.0, fade)
                            * (1.0 - 0.45 * wet) * (1.0 - 0.3 * dirt);
                if (_IsFin > 0.5) len *= _FinLength;

                // carry the rest-pose directions along with the animated normal (shortest-arc rotation)
                float3 n0 = normalize(input.normalOS);
                float4 q = float4(cross(n0, nrm), 1.0 + dot(n0, nrm));
                q = q.w > 1e-4 ? normalize(q) : float4(0, 0, 0, 1);
                float3 grow = normalize(RotateByQuat(input.smoothOS, q) + nrm * 1e-3);
                float3 comb = RotateByQuat(input.combOS, q);
                comb -= grow * dot(comb, grow);

                float lean = _CombStrength * (1.0 + 0.6 * wet + 0.4 * dirt);
                float3 offsetOS = grow * (h * len) + comb * (h * h * len * lean);
                float3 lag = -vel * _MotionGain * h * h;
                float lagLen = length(lag);
                float maxLag = 0.8 * len;
                if (lagLen > maxLag) lag *= maxLag / max(lagLen, 1e-6);
                offsetOS += lag;

                float3 rootWS = TransformObjectToWorld(pos);
                float3 nWS = TransformObjectToWorldNormal(grow);
                float3 pWS = TransformObjectToWorld(pos + offsetOS);
                float h2 = h * h;
                pWS.y -= _FurGravity * h2 * len;
                float sway = sin(_Time.y * 1.7 + rootWS.x * 2.3 + rootWS.z * 1.9) + 0.5 * sin(_Time.y * 3.1 + rootWS.z * 4.1);
                float3 wind = float3(sway, 0, 0.6 * sway) * (_Wind * 0.35);
                pWS += (_MoveLag.xyz + wind) * (h2 * len);

                o.positionWS = pWS;
                o.positionCS = TransformWorldToHClip(pWS);
                o.normalWS = nWS;
                o.rootWS = rootWS + nWS * 0.015;
                o.strandWS = normalize(pWS - rootWS + nWS * 1e-4);
                o.uv = input.uv0;
                o.data = float4(h, mask * fade, wet, ComputeFogFactor(o.positionCS.z));
                // fins: strands along the edge, shown only where the surface turns away from the camera
                float3 viewWS = GetWorldSpaceNormalizeViewDir(rootWS);
                float edgeOn = 1.0 - abs(dot(nWS, viewWS));
                o.fin = float2(input.finData.x * _FinStrands * _DensityScale + input.finData.y * 97.0,
                               smoothstep(0.62, 0.93, edgeOn));
                // collapse shells where there is no fur (eyes, nose, paw pads) so they cost no pixels
                if (_IsFin < 0.5 && (len < 1e-5 || fade <= 0.001)) o.positionCS = float4(0, 0, -1, 1);
                return o;
            }

            float Hash21(float2 p)
            {
                p = frac(p * float2(123.34, 456.21));
                p += dot(p, p + 45.32);
                return frac(p.x * p.y);
            }

            // Soft, anti-aliased strand coverage. 'soften' (0..1) blends towards the strands' average coverage.
            float StrandCoverage(float2 uv, float h, float mask, float soften)
            {
                float2 g = uv * (_FurDensity * _DensityScale);
                // gentle, irregular clumps on long fur only
                float2 cg = g / _ClumpSize;
                float2 ccell = floor(cg);
                float2 cjit = float2(Hash21(ccell + 3.7), Hash21(ccell + 9.1)) - 0.5;
                float2 centre = (ccell + 0.5 + cjit * 0.6) * _ClumpSize;
                float clump = _Clump * h * (0.3 + 1.2 * Hash21(ccell)) * saturate(mask * 2.0 - 0.8);
                g = centre + (g - centre) * (1.0 + clump);

                float2 fw = fwidth(g);
                float pw = max(max(fw.x, fw.y), 1e-4);

                float2 cell = floor(g);
                float2 f = frac(g) - 0.5;
                float hsh = Hash21(cell);
                float2 jitter = float2(Hash21(cell + 17.0), Hash21(cell + 41.0)) - 0.5;
                float d = length(f - jitter * 0.4);
                float height = lerp(0.6, 1.0, hsh);
                float alive = step(h, height);
                float radius = _FurThickness * 0.5 * saturate(1.0 - h / height) + 0.04;
                float sharp = saturate((radius - d) / pw + 0.5) * alive;
                // average coverage of the strands at this height (all heights between 0.6 and 1 are equally likely)
                float rAvg = _FurThickness * 0.5 * saturate(1.0 - h / 0.8) + 0.04;
                float average = saturate(3.14159 * rAvg * rAvg) * saturate((1.0 - h) / 0.4 + 0.25);
                float t = max(saturate((pw - 0.25) / 0.5), soften);
                return lerp(sharp, average, t);
            }

            // Fins: fine strands rooted along the edge that splay apart towards their tips; a few strays are longer.
            float FinCoverage(float x, float h)
            {
                float pw = max(fwidth(x), 1e-4);
                float base = floor(x);
                float cover = 0.0;
                [unroll] for (int k = -1; k <= 1; k++)
                {
                    float cell = base + k;
                    float h1 = Hash21(float2(cell, 7.3));
                    float h2 = Hash21(float2(cell, 2.9));
                    float h3 = Hash21(float2(cell, 5.1));
                    float height = h3 > 0.88 ? lerp(0.85, 1.0, h1) : lerp(0.3, 0.8, h1);   // strays reach the full fin
                    float t = saturate(h / height);
                    float centre = cell + 0.5 + (h2 - 0.5) * 0.6 + (h3 - 0.5) * 1.8 * t * t;   // splay + curve
                    float halfWidth = 0.42 * _FurThickness * (1.0 - t) + 0.03;
                    float c = saturate((halfWidth - abs(x - centre)) / pw + 0.5) * step(h, height);
                    c *= 1.0 - 0.55 * t * t;                                                    // wispy tips
                    cover = 1.0 - (1.0 - cover) * (1.0 - c);
                }
                // strands thinner than a pixel: their average coverage
                float average = 0.45 * _FurThickness * saturate(1.0 - h / 0.75) + 0.03 * step(h, 0.9);
                return lerp(cover, saturate(average), saturate((pw - 0.35) / 0.6));
            }

            half4 FurFrag(Varyings i) : SV_Target
            {
                float h = i.data.x;
                float amount = i.data.y;
                float wet = i.data.z;
                float outfit = SAMPLE_TEXTURE2D(_WorkerOutfitDiffuse, sampler_WorkerOutfitDiffuse, i.uv).a;
                float4 maskTex = SAMPLE_TEXTURE2D(_FurMask, sampler_FurMask, i.uv);
                float mask = maskTex.r;
                float ao = lerp(1.0, maskTex.g, _AOStrength);

                float3 n = normalize(i.normalWS);
                float3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                float facing = saturate(abs(dot(n, v)));

                // both coverages are evaluated unconditionally (screen-space derivatives need uniform control flow)
                float finA = FinCoverage(i.fin.x, h) * i.fin.y;
                // seen head-on, single strands read as dots: soften them, strongly on short fur (face, head),
                // only a little on long fur so bellies and backs stay fluffy
                float longFur = saturate((mask - 0.45) / 0.4);
                float soften = smoothstep(0.45, 0.95, facing) * _FaceSoften * lerp(1.0, 0.45, longFur);
                float shellA = StrandCoverage(i.uv, h, mask, soften);
                shellA = 1.0 - pow(saturate(1.0 - shellA), _ShellBoost);   // same density with fewer shells
                // dense undercoat: the innermost layers hide the body underneath completely
                shellA = max(shellA, _RootFill * saturate(1.0 - h / 0.3));
                float a = _IsFin > 0.5 ? finA : shellA;
                a *= saturate(mask * 10.0) * saturate((0.5 - outfit) * 4.0);
                a *= _FurOpacity * saturate(amount * 4.0) * (1.0 - 0.25 * wet);
                a = saturate(a);
                clip(a - 0.003);

                half3 albedo = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).rgb;
                half4 contam = SAMPLE_TEXTURE2D(_ContaminationDiffuse, sampler_ContaminationDiffuse, i.uv);
                albedo = lerp(albedo, contam.rgb, saturate(contam.a * _BadwaterContamination));
                half4 injury = SAMPLE_TEXTURE2D(_InjuryDiffuse, sampler_InjuryDiffuse, i.uv);
                albedo = lerp(albedo, injury.rgb, saturate(injury.a));
                albedo *= lerp(1.0, 0.72, wet);
                albedo *= lerp(half3(1, 1, 1), _TintColor.rgb, saturate(_TintEnabled));
                // darker roots, but less contrast where we look straight down the strands (no salt-and-pepper)
                half occlusion = lerp(1.0 - _RootDarken * (1.0 - 0.6 * facing), 1.0 + _TipLighten, h);

                float3 T = normalize(i.strandWS);
                InputData inputData = (InputData)0;
                inputData.positionWS = i.rootWS;
                inputData.normalWS = n;
                inputData.viewDirectionWS = v;
                inputData.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);

                float4 shadowCoord = TransformWorldToShadowCoord(i.rootWS);
                Light mainLight = GetMainLight(shadowCoord);
                half shadow = mainLight.shadowAttenuation * mainLight.distanceAttenuation;
                half ndl = dot(n, mainLight.direction);
                half diff = saturate((ndl + _Wrap) / (1.0 + _Wrap));
                float3 hv = normalize(mainLight.direction + v);
                float tdh = dot(T, hv);
                half sheen = pow(saturate(sqrt(saturate(1.0 - tdh * tdh))), _SpecPower)
                             * _SpecStrength * (1.0 + 1.5 * wet) * saturate(ndl + 0.2) * h;
                // light shining through the fringe when the panda is backlit
                half back = _Backlight * pow(1.0 - facing, 3.0) * saturate(dot(-v, mainLight.direction)) * h;
                half3 direct = mainLight.color * shadow * (diff + back) * lerp(1.0, ao, 0.35);
                half3 spec = mainLight.color * shadow * sheen;

                #if defined(_ADDITIONAL_LIGHTS)
                #if USE_CLUSTER_LIGHT_LOOP
                [loop] for (uint lightIndex = 0; lightIndex < min(URP_FP_DIRECTIONAL_LIGHTS_COUNT, MAX_VISIBLE_LIGHTS); lightIndex++)
                {
                    CLUSTER_LIGHT_LOOP_SUBTRACTIVE_LIGHT_CHECK
                    Light l = GetAdditionalLight(lightIndex, i.rootWS);
                    direct += l.color * l.distanceAttenuation * l.shadowAttenuation * saturate((dot(n, l.direction) + _Wrap) / (1.0 + _Wrap));
                }
                #endif
                uint pixelLightCount = GetAdditionalLightsCount();
                LIGHT_LOOP_BEGIN(pixelLightCount)
                    Light l = GetAdditionalLight(lightIndex, i.rootWS);
                    direct += l.color * l.distanceAttenuation * l.shadowAttenuation * saturate((dot(n, l.direction) + _Wrap) / (1.0 + _Wrap));
                LIGHT_LOOP_END
                #endif

                half3 ambient = SampleSH(n) * ao;
                half3 color = albedo * occlusion * (direct + ambient) + spec * ao
                              + _TintColor.rgb * saturate(_TintEnabled) * 0.25;
                color = MixFog(color, i.data.w);
                return half4(color, a);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
