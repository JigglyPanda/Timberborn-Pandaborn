#!/usr/bin/env bash
# Compile the mod's runtime DLLs against the game's own assemblies.
# usage: tools/build_dlls.sh "<path to Timberborn>/Timberborn_Data/Managed"
# Needs a .NET SDK (any recent one works; Roslyn's csc.dll is used with -nostdlib so the game's
# mscorlib/netstandard are referenced instead of the SDK's).
set -euo pipefail
MANAGED="${1:?path to Timberborn_Data/Managed}"
CSC=$(find "$(dirname "$(command -v dotnet)")"/.. -name csc.dll -path "*Roslyn/bincore*" 2>/dev/null | head -1)
[ -n "$CSC" ] || CSC=$(find / -name csc.dll -path "*Roslyn/bincore*" 2>/dev/null | head -1)
REFS=$(ls "$MANAGED"/*.dll | grep -vE "Mono\.Security|System\.EnterpriseServices" | sed 's/^/-r:/' | tr '\n' ' ')
OUT="$(dirname "$0")/../mod/Pandaborn/Scripts"
mkdir -p "$OUT"
dotnet "$CSC" -nologo -nostdlib -target:library -optimize -langversion:9 \
  -out:"$OUT/PandaColonistsFurV6.dll" $REFS "$(dirname "$0")/../src/scripts/PandaColonistsFur.cs"
dotnet "$CSC" -nologo -nostdlib -target:library -optimize -langversion:9 \
  -out:"$OUT/PandaReskin.dll" $REFS "$(dirname "$0")/../src/scripts/PandaReskin.cs"
echo "built into $OUT"
