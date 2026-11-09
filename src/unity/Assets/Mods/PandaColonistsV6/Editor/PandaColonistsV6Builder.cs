// Unity editor helper for Panda Colonists v6.
// Lives in the Unity project at Assets/Mods/PandaColonists. menu: Panda Colonists > Build v6 Fur Bundle
// (or batch mode: Unity.exe -batchmode -quit -projectPath <project> -executeMethod PandaColonistsV6Builder.Build)
// The bundle is written straight to Documents/Timberborn/Mods/Pandaborn/AssetBundles (the Pandaborn mod folder).
using System;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class PandaColonistsV6Builder
{
    private const string Root = "Assets/Mods/PandaColonistsV6/AssetBundles/Resources/PandaFur6";
    private const string BundleName = "pandacolonistsv6_win";

    [MenuItem("Panda Colonists/Build v6 Fur Bundle")]
    public static void Build()
    {
        AssetDatabase.Refresh();
        var shaderPath = Root + "/PandaShellFur.shader";
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(shaderPath);
        if (shader == null) throw new Exception("PandaShellFur.shader not found at " + shaderPath);
        foreach (var m in ShaderUtil.GetShaderMessages(shader))
            Debug.Log("[PandaFur] shader " + m.severity + ": " + m.message + " (line " + m.line + ")");
        if (ShaderUtil.ShaderHasError(shader)) throw new Exception("PandaShellFur.shader has compile errors - see Console");

        ConfigureMask(Root + "/FurMaskAdult.png");
        ConfigureMask(Root + "/FurMaskChild.png");
        var adult = EnsureMaterial("PandaFurAdult", shader, Root + "/FurMaskAdult.png", 0.014f, 520f, 1.0f, 0.85f, 0.32f, 900f);
        var child = EnsureMaterial("PandaFurChild", shader, Root + "/FurMaskChild.png", 0.013f, 600f, 0.95f, 0.7f, 0.28f, 1300f);
        AssetDatabase.SaveAssets();

        var docs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        var outDir = Environment.GetEnvironmentVariable("PANDAFUR_OUT");
        if (string.IsNullOrEmpty(outDir))
            outDir = Path.Combine(docs, "Timberborn", "Mods", "Pandaborn", "AssetBundles");
        Directory.CreateDirectory(outDir);

        var build = new AssetBundleBuild
        {
            assetBundleName = BundleName,
            assetNames = new[]
            {
                shaderPath,
                Root + "/FurMaskAdult.png",
                Root + "/FurMaskChild.png",
                AssetDatabase.GetAssetPath(adult),
                AssetDatabase.GetAssetPath(child),
            }
        };
        var manifest = BuildPipeline.BuildAssetBundles(outDir, new[] { build }, BuildAssetBundleOptions.None,
                                                       BuildTarget.StandaloneWindows64);
        if (manifest == null) throw new Exception("Asset bundle build failed - see Console");
        // the builder also writes a folder-named manifest bundle the game doesn't need
        var extra = Path.Combine(outDir, Path.GetFileName(outDir));
        if (File.Exists(extra)) File.Delete(extra);
        if (File.Exists(extra + ".manifest")) File.Delete(extra + ".manifest");
        Debug.Log("[PandaFur] Built " + Path.Combine(outDir, BundleName));
        if (!Application.isBatchMode)
            EditorUtility.DisplayDialog("Panda Colonists v6", "Fur bundle built:\n" + Path.Combine(outDir, BundleName), "OK");
    }

    private static void ConfigureMask(string path)
    {
        var imp = (TextureImporter)AssetImporter.GetAtPath(path);
        if (imp == null) throw new Exception("Missing " + path);
        imp.sRGBTexture = false;
        imp.mipmapEnabled = true;
        imp.wrapMode = TextureWrapMode.Clamp;
        imp.textureCompression = TextureImporterCompression.Uncompressed;
        imp.SaveAndReimport();
    }

    private static Material EnsureMaterial(string name, Shader shader, string maskPath, float length, float density,
                                           float thickness, float comb, float rootDarken, float finStrands)
    {
        var path = Root + "/" + name + ".mat";
        // always start from the shader's current defaults (an old material keeps stale values)
        if (AssetDatabase.LoadAssetAtPath<Material>(path) != null) AssetDatabase.DeleteAsset(path);
        var mat = new Material(shader);
        AssetDatabase.CreateAsset(mat, path);
        mat.shader = shader;
        mat.SetTexture("_FurMask", AssetDatabase.LoadAssetAtPath<Texture2D>(maskPath));
        mat.SetFloat("_FurLength", length);
        mat.SetFloat("_FurDensity", density);
        mat.SetFloat("_FurThickness", thickness);
        mat.SetFloat("_CombStrength", comb);
        mat.SetFloat("_RootDarken", rootDarken);
        mat.SetFloat("_FinStrands", finStrands);
        mat.renderQueue = -1;   // use the shader's queue
        mat.enableInstancing = false;
        EditorUtility.SetDirty(mat);
        return mat;
    }
}
