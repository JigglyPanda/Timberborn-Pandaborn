// Panda Colonists v6.1 - shell + fin fur for the panda colonists.
// Needs the fur shader bundle (AssetBundles/pandacolonistsv6_win). Without it the fur silently stays off.
using System;
using System.Collections.Generic;
using System.IO;
using Bindito.Core;
using Timberborn.AssetSystem;
using Timberborn.BaseComponentSystem;
using Timberborn.Beavers;
using Timberborn.EntitySystem;
using Timberborn.TemplateInstantiation;
using UnityEngine;
using UnityEngine.Rendering;

namespace PandaColonistsV6
{
    /// <summary>Tunables, read once from PandaFurSettings.txt in the mod folder (key=value lines).</summary>
    public static class PandaFurSettings
    {
        public static bool Enabled = true;
        public static int NearShells, FarShells, MaxFurryPandas;
        public static float LodDistance, FadeStart, MaxDistance;
        public static bool Motion = true;
        public static bool Fins = true;
        public static float LengthAdult = 0.014f, LengthChild = 0.013f;
        public static float DensityAdult = 520f, DensityChild = 600f;
        public const int ReferenceShells = 16;
        private static bool _loaded;

        static PandaFurSettings() { ApplyPreset("high"); }

        private static void ApplyPreset(string q)
        {
            switch (q)
            {
                case "low":    Set(8, 4, 7f, 10f, 13f, 20); break;
                case "medium": Set(12, 6, 8f, 12f, 16f, 30); break;
                case "ultra":  Set(24, 12, 14f, 22f, 28f, 60); break;
                default:       Set(16, 8, 10f, 15f, 20f, 40); break;   // high
            }
        }

        private static void Set(int near, int far, float lod, float fade, float max, int cap)
        {
            NearShells = near; FarShells = far; LodDistance = lod; FadeStart = fade; MaxDistance = max; MaxFurryPandas = cap;
        }

        public static string SettingsPath()
        {
            try
            {
                var dll = typeof(PandaFurSettings).Assembly.Location;
                if (!string.IsNullOrEmpty(dll))
                {
                    var parent = Directory.GetParent(Path.GetDirectoryName(dll));
                    if (parent != null)
                    {
                        var p = Path.Combine(parent.FullName, "PandaFurSettings.txt");
                        if (File.Exists(p)) return p;
                    }
                }
            }
            catch (Exception) { }
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                                "Timberborn", "Mods", "PandaColonistsV2", "PandaFurSettings.txt");
        }

        public static void Load()
        {
            if (_loaded) return;
            _loaded = true;
            try
            {
                var path = SettingsPath();
                if (!File.Exists(path)) return;
                var lines = File.ReadAllLines(path);
                // the preset first, then any individual overrides
                foreach (var raw in lines)
                {
                    var kv = Split(raw);
                    if (kv != null && kv[0] == "quality") ApplyPreset(kv[1].ToLowerInvariant());
                }
                foreach (var raw in lines)
                {
                    var kv = Split(raw);
                    if (kv == null) continue;
                    var k = kv[0];
                    var v = kv[1];
                    float f;
                    bool num = float.TryParse(v, System.Globalization.NumberStyles.Float,
                                              System.Globalization.CultureInfo.InvariantCulture, out f);
                    bool on = v.ToLowerInvariant() != "false" && v != "0" && v.ToLowerInvariant() != "off";
                    switch (k)
                    {
                        case "enabled": Enabled = on; break;
                        case "motion": Motion = on; break;
                        case "fins": Fins = on; break;
                        case "nearshells": if (num) NearShells = Mathf.Clamp((int)f, 2, 32); break;
                        case "farshells": if (num) FarShells = Mathf.Clamp((int)f, 2, 32); break;
                        case "loddistance": if (num) LodDistance = f; break;
                        case "fadestart": if (num) FadeStart = f; break;
                        case "maxdistance": if (num) MaxDistance = f; break;
                        case "maxfurrypandas": if (num) MaxFurryPandas = Mathf.Max(0, (int)f); break;
                        case "lengthadult": if (num) LengthAdult = f; break;
                        case "lengthchild": if (num) LengthChild = f; break;
                        case "densityadult": if (num) DensityAdult = f; break;
                        case "densitychild": if (num) DensityChild = f; break;
                    }
                }
                FarShells = Mathf.Min(FarShells, NearShells);
                FadeStart = Mathf.Min(FadeStart, MaxDistance);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[PandaFur] settings: " + e.Message);
            }
        }

        private static string[] Split(string raw)
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith("#")) return null;
            int i = line.IndexOf('=');
            if (i <= 0) return null;
            return new[] { line.Substring(0, i).Trim().ToLowerInvariant(), line.Substring(i + 1).Trim() };
        }
    }

    public class PandaFurAttacher : BaseComponent, IPostInitializableEntity
    {
        private readonly IAssetLoader _assetLoader;
        private static Material _adultMat, _childMat;
        private static bool _warned;

        public PandaFurAttacher(IAssetLoader assetLoader)
        {
            _assetLoader = assetLoader;
        }

        public void PostInitializeEntity()
        {
            try
            {
                PandaFurSettings.Load();
                if (!PandaFurSettings.Enabled) return;
                // (re)load when missing: mod bundles are unloaded/reloaded between game sessions
                if (!_adultMat)
                {
                    _adultMat = _assetLoader.LoadSafe<Material>("PandaFur6/PandaFurAdult");
                    _childMat = _assetLoader.LoadSafe<Material>("PandaFur6/PandaFurChild");
                }
                if (!_adultMat)
                {
                    if (!_warned) Debug.LogWarning("[PandaFur] fur shader bundle not found - fur disabled");
                    _warned = true;
                    return;
                }
                bool child = (bool)GetComponent<Child>();
                var furry = GameObject.AddComponent<PandaFurRenderer>();
                furry.Init(child ? (_childMat ? _childMat : _adultMat) : _adultMat, child);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[PandaFur] attach failed: " + e.Message);
            }
        }
    }

    /// <summary>Owns the fur (shells + silhouette fins) of one panda.</summary>
    public class PandaFurRenderer : MonoBehaviour
    {
        private static readonly int AnimationTime = Shader.PropertyToID("_AnimationTime");
        private static readonly int AnimatedVertexCount = Shader.PropertyToID("_AnimatedVertexCount");
        private static readonly int FrameCount = Shader.PropertyToID("_FrameCount");
        private static readonly int Looped = Shader.PropertyToID("_Looped");
        private static readonly int AnimationEnabled = Shader.PropertyToID("_AnimationEnabled");
        private static readonly int Offsets = Shader.PropertyToID("_Offsets");
        private static readonly int Rotations = Shader.PropertyToID("_Rotations");
        private static readonly int BaseMap = Shader.PropertyToID("_BaseMap");
        private static readonly int ContaminationDiffuse = Shader.PropertyToID("_ContaminationDiffuse");
        private static readonly int Badwater = Shader.PropertyToID("_BadwaterContamination");
        private static readonly int Outfit = Shader.PropertyToID("_WorkerOutfitDiffuse");
        private static readonly int WetFur = Shader.PropertyToID("_WetFur");
        private static readonly int FurFade = Shader.PropertyToID("_FurFade");
        private static readonly int FurLength = Shader.PropertyToID("_FurLength");
        private static readonly int FurDensity = Shader.PropertyToID("_FurDensity");
        private static readonly int ShellBoost = Shader.PropertyToID("_ShellBoost");
        private static readonly int LengthScale = Shader.PropertyToID("_LengthScale");
        private static readonly int DensityScale = Shader.PropertyToID("_DensityScale");
        private static readonly int Clump = Shader.PropertyToID("_Clump");
        private static readonly int MoveLag = Shader.PropertyToID("_MoveLag");
        private static readonly int MotionGain = Shader.PropertyToID("_MotionGain");
        private static readonly int Wind = Shader.PropertyToID("_Wind");
        private static readonly int IsFin = Shader.PropertyToID("_IsFin");
        private static readonly int Cull = Shader.PropertyToID("_Cull");
        private static readonly int InjuryDiffuse = Shader.PropertyToID("_InjuryDiffuse");
        private static readonly int TintColor = Shader.PropertyToID("_TintColor");
        private static readonly int TintEnabled = Shader.PropertyToID("_TintEnabled");
        private static Texture2D _clear;

        /// <summary>1x1 fully transparent texture for overlays the panda doesn't currently have.</summary>
        private static Texture Clear()
        {
            if (!_clear)
            {
                _clear = new Texture2D(1, 1, TextureFormat.RGBA32, false);
                _clear.SetPixel(0, 0, new Color(0f, 0f, 0f, 0f));
                _clear.Apply(false, true);
            }
            return _clear;
        }

        private class FurMeshes
        {
            public readonly Dictionary<int, Mesh> ByShells = new Dictionary<int, Mesh>();
        }

        // fur meshes are shared by every panda using the same body mesh and shell count
        private static readonly Dictionary<Mesh, FurMeshes> Cache = new Dictionary<Mesh, FurMeshes>();
        private static readonly List<PandaFurRenderer> All = new List<PandaFurRenderer>();
        private static readonly List<float> Distances = new List<float>();
        private static int _budgetFrame = -1;
        private static int _seedCounter;
        private static float _budgetDistance = float.MaxValue;

        private Material _template;
        private bool _child;
        private MeshRenderer _source;
        private MeshFilter _sourceFilter;
        private MeshRenderer _fur;
        private MeshFilter _furFilter;
        private Material _shellMat, _finMat;
        private MaterialPropertyBlock _block;
        private int _searchFrames;
        private int _shells;
        private float _lengthScale, _densityScale, _clump;
        private float _lastDistance = float.MaxValue;
        private Vector3 _lastPos;
        private Vector3 _velocity;
        private Vector4 _lag;
        private bool _hasPos;

        public void Init(Material template, bool child)
        {
            _template = template;
            _child = child;
        }

        private void OnEnable() { All.Add(this); }

        private void OnDisable()
        {
            All.Remove(this);
            _lastDistance = float.MaxValue;
            if (_fur) _fur.enabled = false;
        }

        private void OnDestroy()
        {
            if (_shellMat) Destroy(_shellMat);
            if (_finMat) Destroy(_finMat);
            if (_fur) Destroy(_fur.gameObject);
        }

        private bool TryFindSource()
        {
            foreach (var r in GetComponentsInChildren<MeshRenderer>(true))
            {
                var m = r.sharedMaterial;
                var mf = r.GetComponent<MeshFilter>();
                if (m && mf && mf.sharedMesh && m.HasProperty(Offsets) && m.HasProperty(BaseMap))
                {
                    _source = r;
                    _sourceFilter = mf;
                    return true;
                }
            }
            return false;
        }

        private void Build()
        {
            var go = new GameObject("PandaFur");
            go.layer = _source.gameObject.layer;
            go.transform.SetParent(_source.transform, false);
            _furFilter = go.AddComponent<MeshFilter>();
            _fur = go.AddComponent<MeshRenderer>();
            _shellMat = new Material(_template);
            _shellMat.SetFloat(FurLength, _child ? PandaFurSettings.LengthChild : PandaFurSettings.LengthAdult);
            _shellMat.SetFloat(FurDensity, _child ? PandaFurSettings.DensityChild : PandaFurSettings.DensityAdult);
            if (!PandaFurSettings.Motion)
            {
                _shellMat.SetFloat(MotionGain, 0f);
                _shellMat.SetFloat(Wind, 0f);
            }
            _shellMat.SetFloat(IsFin, 0f);
            _shellMat.SetFloat(Cull, (float)CullMode.Back);
            _finMat = new Material(_shellMat);
            _finMat.SetFloat(IsFin, 1f);
            _finMat.SetFloat(Cull, (float)CullMode.Off);
            // a little individuality: every panda's coat is slightly different
            var rnd = new System.Random(unchecked(++_seedCounter * 7919 + 17));
            _lengthScale = 0.88f + 0.26f * (float)rnd.NextDouble();
            _densityScale = 0.9f + 0.2f * (float)rnd.NextDouble();
            _clump = (_child ? 0.2f : 0.3f) + 0.18f * (float)rnd.NextDouble();
            _block = new MaterialPropertyBlock();
            _fur.sharedMaterials = PandaFurSettings.Fins ? new[] { _shellMat, _finMat } : new[] { _shellMat };
            _fur.shadowCastingMode = ShadowCastingMode.Off;   // the body already casts the shadow
            _fur.receiveShadows = true;
            _fur.lightProbeUsage = _source.lightProbeUsage;
            _fur.enabled = false;
        }

        private void SetShells(int shells)
        {
            if (_shells == shells) return;
            var mesh = _sourceFilter.sharedMesh;
            FurMeshes cached;
            if (!Cache.TryGetValue(mesh, out cached))
            {
                cached = new FurMeshes();
                Cache[mesh] = cached;
            }
            Mesh furMesh;
            if (!cached.ByShells.TryGetValue(shells, out furMesh) || !furMesh)
            {
                furMesh = BuildFurMesh(mesh, shells);
                cached.ByShells[shells] = furMesh;
            }
            _furFilter.sharedMesh = furMesh;
            _shells = shells;
        }

        /// <summary>Rest-pose comb direction: away from the muzzle on the face, down and back on the body.</summary>
        private static Vector3[] CombDirections(Vector3[] v, Vector3[] n)
        {
            int V = v.Length;
            float maxY = float.MinValue;
            for (int i = 0; i < V; i++) maxY = Mathf.Max(maxY, v[i].y);
            var muzzle = Vector3.zero;
            float bestZ = float.MinValue;
            for (int i = 0; i < V; i++)
                if (v[i].y > 0.6f * maxY && v[i].z > bestZ) { bestZ = v[i].z; muzzle = v[i]; }
            float faceRadius = 0.45f * Mathf.Max(maxY, 0.05f);
            var bodyComb = new Vector3(0f, -1f, -0.35f).normalized;
            var comb = new Vector3[V];
            for (int i = 0; i < V; i++)
            {
                var away = v[i] - muzzle;
                float face = Mathf.Clamp01(1.3f - away.magnitude / faceRadius);
                var c = Vector3.Lerp(bodyComb, away.normalized, face);
                var nn = n[i];
                c -= nn * Vector3.Dot(c, nn);
                comb[i] = c.sqrMagnitude > 1e-6f ? c.normalized : Vector3.zero;
            }
            return comb;
        }

        /// <summary>Welds vertices by position: group id per vertex.</summary>
        private static int[] Weld(Vector3[] v, out int groups)
        {
            var map = new Dictionary<Vector3Int, int>();
            var id = new int[v.Length];
            for (int i = 0; i < v.Length; i++)
            {
                var k = new Vector3Int(Mathf.RoundToInt(v[i].x * 20000f), Mathf.RoundToInt(v[i].y * 20000f),
                                       Mathf.RoundToInt(v[i].z * 20000f));
                int g;
                if (!map.TryGetValue(k, out g)) { g = map.Count; map[k] = g; }
                id[i] = g;
            }
            groups = map.Count;
            return id;
        }

        private static Mesh BuildFurMesh(Mesh src, int shells)
        {
            var v = src.vertices;
            var n = src.normals;
            int V = v.Length;
            if (n.Length != V) { n = new Vector3[V]; for (int i = 0; i < V; i++) n[i] = Vector3.up; }
            var uv = new List<Vector2>();
            src.GetUVs(0, uv);
            if (uv.Count != V) { uv.Clear(); for (int i = 0; i < V; i++) uv.Add(Vector2.zero); }
            var tris = src.triangles;
            var comb = CombDirections(v, n);

            // smoothed normals across seams and hard edges (area weighted)
            int groups;
            var gid = Weld(v, out groups);
            var gn = new Vector3[groups];
            for (int t = 0; t < tris.Length; t += 3)
            {
                int a = tris[t], b = tris[t + 1], c = tris[t + 2];
                var fn = Vector3.Cross(v[b] - v[a], v[c] - v[a]);   // length = 2*area
                // match the orientation of the mesh's own normals
                if (Vector3.Dot(fn, n[a] + n[b] + n[c]) < 0f) fn = -fn;
                gn[gid[a]] += fn; gn[gid[b]] += fn; gn[gid[c]] += fn;
            }
            var smooth = new Vector3[V];
            for (int i = 0; i < V; i++)
            {
                var s = gn[gid[i]];
                smooth[i] = s.sqrMagnitude > 1e-12f ? s.normalized : n[i];
                // never lean further than ~60 degrees from the vertex's own normal
                if (Vector3.Dot(smooth[i], n[i]) < 0.5f) smooth[i] = (smooth[i] + n[i]).normalized;
            }

            // unique edges (by welded position) for the silhouette fins
            var edgeSet = new Dictionary<long, bool>();
            var edges = new List<int>();
            for (int t = 0; t < tris.Length; t += 3)
            {
                for (int e = 0; e < 3; e++)
                {
                    int a = tris[t + e], b = tris[t + (e + 1) % 3];
                    int ga = gid[a], gb = gid[b];
                    if (ga == gb) continue;
                    long key = ga < gb ? ((long)ga << 32) | (uint)gb : ((long)gb << 32) | (uint)ga;
                    if (!edgeSet.ContainsKey(key)) { edgeSet[key] = true; edges.Add(a); edges.Add(b); }
                }
            }
            int fins = PandaFurSettings.Fins ? edges.Count / 2 : 0;

            int shellVerts = V * shells;
            int total = shellVerts + fins * 4;
            var pv = new Vector3[total];
            var pn = new Vector3[total];
            var puv = new List<Vector2>(total);
            var pfin = new List<Vector2>(total);
            var pid = new List<Vector2>(total);
            var pcomb = new List<Vector3>(total);
            var psmooth = new List<Vector3>(total);
            var shellTris = new int[tris.Length * shells];
            for (int s = 0; s < shells; s++)   // innermost shell first: blending order = draw order
            {
                float h = (s + 1f) / shells;
                int o = s * V;
                for (int i = 0; i < V; i++)
                {
                    pv[o + i] = v[i];
                    pn[o + i] = n[i];
                    puv.Add(uv[i]);
                    pfin.Add(Vector2.zero);
                    pid.Add(new Vector2(i, h));
                    pcomb.Add(comb[i]);
                    psmooth.Add(smooth[i]);
                }
                int to = s * tris.Length;
                for (int t = 0; t < tris.Length; t++) shellTris[to + t] = tris[t] + o;
            }
            var finTris = new int[fins * 6];
            var rnd = new System.Random(1234);
            for (int f = 0; f < fins; f++)
            {
                int a = edges[2 * f], b = edges[2 * f + 1];
                float len = Vector3.Distance(v[a], v[b]);
                float seed = (float)rnd.NextDouble();
                int o = shellVerts + f * 4;
                int[] src4 = { a, b, a, b };
                float[] h4 = { 0f, 0f, 1f, 1f };
                float[] s4 = { 0f, len, 0f, len };
                for (int k = 0; k < 4; k++)
                {
                    int i = src4[k];
                    pv[o + k] = v[i];
                    pn[o + k] = n[i];
                    puv.Add(uv[i]);
                    pfin.Add(new Vector2(s4[k], seed));
                    pid.Add(new Vector2(i, h4[k]));
                    pcomb.Add(comb[i]);
                    psmooth.Add(smooth[i]);
                }
                int ft = f * 6;
                finTris[ft] = o; finTris[ft + 1] = o + 1; finTris[ft + 2] = o + 2;
                finTris[ft + 3] = o + 1; finTris[ft + 4] = o + 3; finTris[ft + 5] = o + 2;
            }

            var m = new Mesh { name = src.name + "_PandaFur" + shells, indexFormat = IndexFormat.UInt32 };
            m.vertices = pv;
            m.normals = pn;
            m.SetUVs(0, puv);
            m.SetUVs(1, pfin);     // TEXCOORD1
            m.SetUVs(2, pid);      // TEXCOORD2
            m.SetUVs(3, pcomb);    // TEXCOORD3
            m.SetUVs(4, psmooth);  // TEXCOORD4
            m.subMeshCount = fins > 0 ? 2 : 1;
            m.SetTriangles(shellTris, 0, false);
            if (fins > 0) m.SetTriangles(finTris, 1, false);
            var bounds = src.bounds;
            bounds.Expand(1.5f);   // vertex animation moves the panda far from its rest pose
            m.bounds = bounds;
            m.UploadMeshData(true);
            return m;
        }

        private void LateUpdate()
        {
            if (!_source)
            {
                if (_searchFrames++ > 300) { enabled = false; return; }
                if (!TryFindSource()) return;
                Build();
            }
            if (!_fur) return;

            var cam = Camera.main;
            bool visible = cam && _source.enabled && _source.isVisible && _source.gameObject.activeInHierarchy;
            float d = float.MaxValue;
            if (visible) d = Vector3.Distance(cam.transform.position, _source.bounds.center);
            _lastDistance = d;
            UpdateBudget();
            bool on = visible && d < PandaFurSettings.MaxDistance && d <= _budgetDistance;
            if (_fur.enabled != on) _fur.enabled = on;
            if (!on) { _hasPos = false; return; }

            SetShells(d < PandaFurSettings.LodDistance ? PandaFurSettings.NearShells : PandaFurSettings.FarShells);
            if (PandaFurSettings.Motion) UpdateMoveLag();

            var src = _source.sharedMaterial;
            var b = _block;
            b.Clear();
            b.SetFloat(AnimationTime, src.GetFloat(AnimationTime));
            b.SetFloat(AnimatedVertexCount, src.GetFloat(AnimatedVertexCount));
            b.SetFloat(FrameCount, src.GetFloat(FrameCount));
            b.SetFloat(Looped, src.GetFloat(Looped));
            b.SetFloat(AnimationEnabled, src.GetFloat(AnimationEnabled));
            SetTex(b, Offsets, src.GetTexture(Offsets));
            SetTex(b, Rotations, src.GetTexture(Rotations));
            SetTex(b, BaseMap, src.GetTexture(BaseMap));
            b.SetTexture(ContaminationDiffuse, Overlay(src, ContaminationDiffuse));
            b.SetTexture(InjuryDiffuse, Overlay(src, InjuryDiffuse));
            b.SetTexture(Outfit, Overlay(src, Outfit));
            if (src.HasProperty(TintColor)) b.SetColor(TintColor, src.GetColor(TintColor));
            if (src.HasProperty(TintEnabled)) b.SetFloat(TintEnabled, src.GetFloat(TintEnabled));
            if (src.HasProperty(Badwater)) b.SetFloat(Badwater, src.GetFloat(Badwater));
            if (src.HasProperty(WetFur)) b.SetFloat(WetFur, src.GetFloat(WetFur));
            float fade = 1f - Mathf.Clamp01((d - PandaFurSettings.FadeStart) /
                                            Mathf.Max(0.01f, PandaFurSettings.MaxDistance - PandaFurSettings.FadeStart));
            b.SetFloat(FurFade, fade);
            b.SetFloat(ShellBoost, (float)PandaFurSettings.ReferenceShells / _shells);
            b.SetFloat(LengthScale, _lengthScale);
            b.SetFloat(DensityScale, _densityScale);
            b.SetFloat(Clump, _clump);
            b.SetVector(MoveLag, _lag);
            _fur.SetPropertyBlock(b);
        }

        private static Texture Overlay(Material src, int id)
        {
            var t = src.HasProperty(id) ? src.GetTexture(id) : null;
            return t ? t : Clear();
        }

        private static void SetTex(MaterialPropertyBlock b, int id, Texture t)
        {
            if (t) b.SetTexture(id, t);
        }

        /// <summary>Fur trails behind when the panda walks or turns (world space, in fur lengths).</summary>
        private void UpdateMoveLag()
        {
            float dt = Time.deltaTime;
            var pos = _source.transform.position;
            if (!_hasPos || dt <= 0f)
            {
                if (!_hasPos) { _velocity = Vector3.zero; _lag = Vector4.zero; _hasPos = true; }
                _lastPos = pos;
                return;
            }
            var v = (pos - _lastPos) / dt;
            _lastPos = pos;
            if (v.sqrMagnitude > 400f) v = Vector3.zero;   // teleports (entering buildings etc.)
            _velocity = Vector3.Lerp(_velocity, v, 1f - Mathf.Exp(-dt * 6f));
            var lag = -_velocity * 0.35f;
            if (lag.sqrMagnitude > 1.2f * 1.2f) lag = lag.normalized * 1.2f;
            _lag = lag;
        }

        /// <summary>Once per frame: distance of the N-th closest visible panda (caps fur cost in huge colonies).</summary>
        private static void UpdateBudget()
        {
            if (_budgetFrame == Time.frameCount) return;
            _budgetFrame = Time.frameCount;
            int cap = PandaFurSettings.MaxFurryPandas;
            if (All.Count <= cap) { _budgetDistance = float.MaxValue; return; }
            Distances.Clear();
            foreach (var p in All) Distances.Add(p._lastDistance);
            Distances.Sort();
            _budgetDistance = cap > 0 ? Distances[cap - 1] : -1f;
        }
    }

    [Context("Game")]
    public class PandaFurConfigurator : Configurator
    {
        protected override void Configure()
        {
            Bind<PandaFurAttacher>().AsTransient();
            MultiBind<TemplateModule>().ToProvider(ProvideTemplateModule).AsSingleton();
        }

        private static TemplateModule ProvideTemplateModule()
        {
            var builder = new TemplateModule.Builder();
            builder.AddDecorator<BeaverSpec, PandaFurAttacher>();
            return builder.Build();
        }
    }
}
