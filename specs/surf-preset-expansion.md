# Surf Preset Expansion

Expand the `surf` group in `~/marketplace-scout/config.json` from 9 saved searches to the full shaper/style list Jacob provided on July 9, 2026.

## Requirements

1. **Config-only change.** Edit `config.json` only — no changes to `scout.py`. The file must remain valid JSON (verify with `python3 -m json.tool`).
2. **Add the new presets below** to the `presets` object. Follow the existing key style (lowercase, no spaces) and query style (shaper/brand name + `surfboard`, except where noted).
3. **Add every new preset key to `groups.surf`**, keeping the existing 9 members (`longboard`, `midlength`, `egg`, `retro`, `skipfrye`, `holly`, `seagull`, `daneperlee`, `christenson`) in place.
4. **Add the same new keys to `groups.all`**, which mirrors surf + paddle.
5. **Do not duplicate existing presets.** These items from Jacob's list are already saved and must NOT be re-added: skip frye (`skipfrye`), christenson / chris christenson / eric christenson (`christenson`), longboard, egg, retro. Internal duplicates in the raw list (ryan lovelace, ryan burch, tyler warren, vintage, glider, hynson, liddle, g&s vs gordon and smith) collapse to one preset each.
6. Every preset key referenced in `groups.surf` and `groups.all` must exist in `presets` (no dangling keys).

## New presets (key → query)

| key | query |
|---|---|
| andreini | andreini surfboard |
| linden | linden surfboard |
| joeltudor | joel tudor surfboard |
| michaelmiller | michael miller surfboard |
| hynson | hynson surfboard |
| caster | caster surfboard |
| gatoheroi | gato heroi surfboard |
| harbour | harbour surfboard |
| waynelynch | wayne lynch surfboard |
| takayama | takayama surfboard |
| nuuhiwa | nuuhiwa surfboard |
| ryanlovelace | ryan lovelace surfboard |
| kookbox | kookbox surfboard |
| bing | bing surfboard |
| gerrylopez | gerry lopez surfboard |
| shrosbree | shrosbree surfboard |
| hobie | hobie surfboard |
| hapjacobs | hap jacobs surfboard |
| lancecarson | lance carson surfboard |
| pavel | pavel surfboard |
| hansen | hansen surfboard |
| moonlight | moonlight glassing |
| bonzer | bonzer surfboard |
| campbellbrothers | campbell brothers surfboard |
| mast | mast surfboard |
| mctavish | mctavish surfboard |
| gregnoll | greg noll surfboard |
| dano | dano surfboard |
| junod | junod surfboard |
| mandala | mandala surfboard |
| yater | yater surfboard |
| jimphillips | jim phillips surfboard |
| shortboard | shortboard |
| richardkenvin | richard kenvin surfboard |
| vintage | vintage surfboard |
| eaton | eaton surfboard |
| noserider | noserider |
| joshhall | josh hall surfboard |
| johnpeck | john peck surfboard |
| tylerwarren | tyler warren surfboard |
| ryanburch | ryan burch surfboard |
| stewart | stewart surfboard |
| tomwegener | tom wegener surfboard |
| glider | glider surfboard |
| infinity | infinity surfboard |
| thirdworldexotic | third world exotic |
| larrymabile | larry mabile surfboard |
| mitsven | mitsven surfboard |
| philedwards | phil edwards surfboard |
| micahwood | micah wood surfboard |
| fineline | fineline surfboard |
| bahne | bahne surfboard |
| stukenson | stu kenson surfboard |
| aipa | aipa surfboard |
| griffin | mike griffin surfboard |
| hull | hull surfboard |
| liddle | liddle surfboard |
| speedshape | speed shape surfboard |
| gs | g&s surfboard |
| gordonandsmith | gordon and smith surfboard |

## Interpretation notes (raw list → preset)

- "hanes" → **hansen** (Hansen Surfboards, Encinitas — "hanes" assumed typo)
- "knoll" → **gregnoll** (Greg Noll — "knoll" assumed typo; "knoll surfboard" alone would match nothing)
- "shrosbee" → **shrosbree** (Shrosbree shaping family — corrected spelling)
- "gerry shrosbee ... lopez" → **gerrylopez** + **shrosbree**
- "tyler stewart" → **stewart** (Stewart Surfboards) + tylerwarren already covered
- "magic" (trailing "g&s gordon and smith magic") → the G&S Magic model; covered by the `gs` query, no standalone preset
- "moonlight glassing" → query kept as brand phrase (boards are listed "glassed by Moonlight", not "moonlight surfboard")
- "nose rider" → **noserider**, query without "surfboard" so it matches both "noserider" and "nose rider 9'6" titles
