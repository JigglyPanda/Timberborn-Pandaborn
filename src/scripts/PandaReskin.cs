// Panda Reskin - runtime support for modded factions.
// Vanilla Folktails / Iron Teeth already use the panda textures shipped as asset overrides.
// Any other (modded) faction keeps the panda body but would otherwise get its own beaver-coloured fur;
// this component re-applies panda markings for those factions, after the game's own BeaverTextureSetter.
using System;
using Bindito.Core;
using Timberborn.AssetSystem;
using Timberborn.BaseComponentSystem;
using Timberborn.Beavers;
using Timberborn.Characters;
using Timberborn.EntitySystem;
using Timberborn.GameFactionSystem;
using Timberborn.TemplateInstantiation;
using UnityEngine;

namespace PandaReskin
{
    public class PandaModdedFactionTextureSetter : BaseComponent, IPostInitializableEntity
    {
        private static readonly int BaseMapId = Shader.PropertyToID("_BaseMap");
        private static readonly System.Random Rng = new System.Random();
        private static readonly string[] AdultPaths =
        {
            "Materials/Beavers/Folktails/Adult/BeaverAdult1.Folktails",
            "Materials/Beavers/Folktails/Adult/BeaverAdult2.Folktails",
            "Materials/Beavers/Folktails/Adult/BeaverAdult3.Folktails",
            "Materials/Beavers/Folktails/Adult/BeaverAdult4.Folktails",
            "Materials/Beavers/Folktails/Adult/BeaverAdult5.Folktails",
        };
        private static readonly string[] ChildPaths =
        {
            "Materials/Beavers/Folktails/Child/BeaverChild1.Folktails",
            "Materials/Beavers/Folktails/Child/BeaverChild2.Folktails",
            "Materials/Beavers/Folktails/Child/BeaverChild3.Folktails",
        };

        private readonly FactionService _factionService;
        private readonly IAssetLoader _assetLoader;

        public PandaModdedFactionTextureSetter(FactionService factionService, IAssetLoader assetLoader)
        {
            _factionService = factionService;
            _assetLoader = assetLoader;
        }

        public void PostInitializeEntity()
        {
            try
            {
                var faction = _factionService.Current;
                if (faction == null) return;
                var id = faction.Id ?? string.Empty;
                if (id == "Folktails" || id == "IronTeeth") return;   // vanilla: handled by texture overrides
                var modifier = GetComponent<CharacterMaterialModifier>();
                if (!modifier) return;
                var isChild = (bool)GetComponent<Child>();
                var paths = isChild ? ChildPaths : AdultPaths;
                var tex = _assetLoader.LoadSafe<Texture2D>(paths[Rng.Next(paths.Length)]);
                if (tex) modifier.SetTexture(BaseMapId, tex);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[PandaReskin] could not apply panda texture: " + e.Message);
            }
        }
    }

    [Context("Game")]
    public class PandaReskinConfigurator : Configurator
    {
        protected override void Configure()
        {
            Bind<PandaModdedFactionTextureSetter>().AsTransient();
            MultiBind<TemplateModule>().ToProvider(ProvideTemplateModule).AsSingleton();
        }

        private static TemplateModule ProvideTemplateModule()
        {
            var builder = new TemplateModule.Builder();
            builder.AddDecorator<BeaverSpec, PandaModdedFactionTextureSetter>();
            return builder.Build();
        }
    }
}
