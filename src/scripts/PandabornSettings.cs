// Pandaborn - in-game settings page (needs the "Mod Settings" mod by eMka).
// Shipped as Scripts/PandabornSettings.bin and only loaded by PandabornStarter when Mod Settings is installed,
// so Pandaborn keeps working without it (PandaFurSettings.txt is used instead).
using System.Collections.Generic;
using Bindito.Core;
using ModSettings.Common;
using ModSettings.Core;
using PandaColonistsV6;
using Timberborn.BlueprintSystem;
using Timberborn.FactionSystem;
using Timberborn.Modding;
using Timberborn.SettingsSystem;

namespace PandabornSettingsPage
{
    public class PandabornModSettings : ModSettingsOwner
    {
        private readonly ISpecService _specService;
        private readonly List<KeyValuePair<string, LimitedStringModSetting>> _factionSettings =
            new List<KeyValuePair<string, LimitedStringModSetting>>();

        public PandabornModSettings(ISettings settings, ModSettingsOwnerRegistry modSettingsOwnerRegistry,
                                    ModRepository modRepository, ISpecService specService)
            : base(settings, modSettingsOwnerRegistry, modRepository)
        {
            _specService = specService;
        }

        private static List<NonLocalizedLimitedStringModSettingValue> Looks(params string[] names)
        {
            var l = new List<NonLocalizedLimitedStringModSettingValue>();
            foreach (var n in names) l.Add(new NonLocalizedLimitedStringModSettingValue(n));
            return l;
        }

        public LimitedStringModSetting FolktailsLook { get; } = new LimitedStringModSetting(0,
            Looks("Giant panda", "Red panda"),
            ModSettingDescriptor.Create("Folktails are")
                .SetTooltip("Applies to colonists born or loaded from now on (reload the save to update everyone)."));

        public LimitedStringModSetting IronTeethLook { get; } = new LimitedStringModSetting(0,
            Looks("Red panda", "Giant panda"),
            ModSettingDescriptor.Create("Iron Teeth are")
                .SetTooltip("Applies to colonists born or loaded from now on (reload the save to update everyone)."));

        public LimitedStringModSetting OtherFactionsLook { get; } = new LimitedStringModSetting(0,
            Looks("Giant panda", "Red panda", "Faction colours"),
            ModSettingDescriptor.Create("Modded factions are")
                .SetTooltip("Default for faction mods (Emberpelts, Leaf Coats, ...). 'Faction colours' keeps the faction's own fur colours on the panda body."));

        protected override void OnBeforeLoad()
        {
            // one choice per installed modded faction
            try
            {
                foreach (var spec in _specService.GetSpecs<FactionSpec>())
                {
                    if (spec.Id == "Folktails" || spec.Id == "IronTeeth") continue;
                    var setting = new LimitedStringModSetting(0,
                        Looks("Same as modded factions", "Giant panda", "Red panda", "Faction colours"),
                        ModSettingDescriptor.Create("  " + spec.Id + " are"));
                    AddCustomModSetting(setting, "Faction." + spec.Id);
                    _factionSettings.Add(new KeyValuePair<string, LimitedStringModSetting>(spec.Id, setting));
                }
            }
            catch (System.Exception e)
            {
                UnityEngine.Debug.LogWarning("[Pandaborn] modded faction settings: " + e.Message);
            }
        }

        protected override string ModId => "JigglyPanda.Pandaborn";

        public override ModSettingsContext ChangeableOn => ModSettingsContext.All;

        public ModSetting<bool> FurEnabled { get; } = new ModSetting<bool>(true,
            ModSettingDescriptor.Create("Fur")
                .SetTooltip("Real see-through fur on pandas near the camera. Off = flat textured pandas."));

        public LimitedStringModSetting Quality { get; } = new LimitedStringModSetting(2,
            new List<NonLocalizedLimitedStringModSettingValue>
            {
                new NonLocalizedLimitedStringModSettingValue("Low"),
                new NonLocalizedLimitedStringModSettingValue("Medium"),
                new NonLocalizedLimitedStringModSettingValue("High"),
                new NonLocalizedLimitedStringModSettingValue("Ultra"),
            },
            ModSettingDescriptor.Create("Fur quality")
                .SetTooltip("How many fur layers, how many pandas get fur and how far away it is drawn."));

        public RangeIntModSetting FurDistance { get; } = new RangeIntModSetting(0, 0, 40,
            ModSettingDescriptor.Create("Fur distance (m, 0 = preset)")
                .SetTooltip("Pandas further than this from the camera have no fur. 0 uses the quality preset."));

        public RangeIntModSetting MaxFurryPandas { get; } = new RangeIntModSetting(0, 0, 150,
            ModSettingDescriptor.Create("Max furry pandas (0 = preset)")
                .SetTooltip("Only the closest pandas get fur. 0 uses the quality preset."));

        public RangeIntModSetting FurLength { get; } = new RangeIntModSetting(100, 50, 160,
            ModSettingDescriptor.Create("Fur length (%)"));

        public ModSetting<bool> Outlines { get; } = new ModSetting<bool>(true,
            ModSettingDescriptor.Create("Fuzzy outlines")
                .SetTooltip("Fine strands along every outline. Slightly faster when off."));

        public ModSetting<bool> Motion { get; } = new ModSetting<bool>(true,
            ModSettingDescriptor.Create("Fur motion")
                .SetTooltip("Fur trails behind moving pandas and sways in the breeze."));

        protected override void OnAfterLoad()
        {
            Apply();
            ModSettingChanged += (_, __) => Apply();
        }

        private void Apply()
        {
            PandaFurSettings.Load();   // text file first (advanced overrides), then the in-game values win
            PandaFurSettings.ApplyPreset(Quality.Value.ToLowerInvariant());
            PandaFurSettings.Enabled = FurEnabled.Value;
            PandaFurSettings.Fins = Outlines.Value;
            PandaFurSettings.Motion = Motion.Value;
            PandaFurSettings.LengthMultiplier = FurLength.Value / 100f;
            if (FurDistance.Value > 0)
            {
                float d = FurDistance.Value;
                PandaFurSettings.MaxDistance = d;
                PandaFurSettings.FadeStart = d * 0.75f;
                PandaFurSettings.LodDistance = d * 0.5f;
            }
            if (MaxFurryPandas.Value > 0) PandaFurSettings.MaxFurryPandas = MaxFurryPandas.Value;
            FactionLooks.Folktails = FactionLooks.Normalize(FolktailsLook.Value);
            FactionLooks.IronTeeth = FactionLooks.Normalize(IronTeethLook.Value);
            FactionLooks.Others = FactionLooks.Normalize(OtherFactionsLook.Value);
            foreach (var kv in _factionSettings)
                FactionLooks.PerFaction[kv.Key.ToLowerInvariant()] = FactionLooks.Normalize(kv.Value.Value);
            PandabornFactionSkins.Apply();
        }
    }

    [Context("MainMenu")]
    [Context("Game")]
    public class PandabornSettingsConfigurator : Configurator
    {
        protected override void Configure()
        {
            Bind<PandabornModSettings>().AsSingleton();
        }
    }
}
