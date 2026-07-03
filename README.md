# vyges-tools/pdk-catalog

The Vyges **open-PDK catalog** — a single, quickly-readable index of the PDKs the Vyges
stack knows how to present, plus the full descriptor for each. It is to PDKs what
[`vyges-ip/vyges-ip-catalog`](https://github.com/vyges-ip/vyges-ip-catalog) is to IP: one
generated `index.json` for fast lookup, with each row pointing at the full manifest.

```
pdk-catalog/
  index.json                    # the aggregated index (quick lookup + version index)
  descriptors/<name>.vyges-pdk.json   # the full PDK descriptors (schema: vyges.com/schema/v1/vyges-pdk.schema.json)
```

## index.json

Schema `vyges-pdk-catalog/index-v1`. One row per PDK — a lightweight summary plus pointers:

| field | meaning |
|---|---|
| `name` `node` `foundry` | identity |
| `design_types` | `digital` / `analog` / `mixed-signal` / `rf` capability tags |
| `source` | `ciel` (open registry) · `local` (mirror / on-disk) · `nda` |
| `latest` / `versions[]` | the **version index** — newest known release + all known releases |
| `descriptor_url` | raw URL of the full `*.vyges-pdk.json` (the "manifest_url") |
| `mirror` | the Vyges data mirror, when one exists |
| `content_hash` | sha256 of the descriptor (lets a client detect changes on refresh) |

`latest` + `versions[]` are what let a client show "↑ vX.Y available" **without a live
query** — the catalog *is* the version index.

## Regeneration

`scripts/gen_index.py` regenerates `index.json` from the PDK mirror repos Vyges
maintains: it refreshes `versions[]` / `latest` from each dedicated mirror's git tags,
recomputes every `content_hash`, and stamps `generated_at` / `generated_sha` (the catalog
HEAD at generation). `.github/workflows/update-index.yml` runs it **daily** (06:00 UTC,
plus `workflow_dispatch`) and commits any change — the same pattern as vyges-ip-catalog.

The shared [`open_pdks`](https://github.com/vyges-tools/open_pdks) builder is not used to
version sky130/gf180 (its tags are build-system releases, not PDK versions), so those two
stay hand-maintained.

## The PDKs

| PDK | node | foundry | source | mirror |
|---|---|---|---|---|
| `sky130a` | 130nm | SkyWater | local | [open_pdks](https://github.com/vyges-tools/open_pdks) builder |
| `gf180mcu` | 180nm | GlobalFoundries | local | [open_pdks](https://github.com/vyges-tools/open_pdks) builder |
| `ihp_sg13g2` | 130nm SiGe BiCMOS | IHP | local | [ihp-open-pdk](https://github.com/vyges-tools/ihp-open-pdk) |
| `nangate45` | 45nm | Nangate | local | [nangate45](https://github.com/vyges-tools/nangate45) |
| `asap7` | 7nm (predictive) | ASU | local | [asap7](https://github.com/vyges-tools/asap7) |
| `icsprout55` | 55nm | icsprout | local | [icsprout55](https://github.com/vyges-tools/icsprout55) |

Vyges mirrors the non-Ciel open PDKs under `github.com/vyges-tools/` for reproducibility,
availability, and a consistent data home. sky130 and gf180 are built from the mirrored
[`open_pdks`](https://github.com/vyges-tools/open_pdks) builder (origin
[rtimothyedwards/open_pdks](https://github.com/rtimothyedwards/open_pdks)) and installed
under `$PDK_ROOT`.

> **`icsprout55`** — the most advanced open node (55nm; ICsprout + College of IC, Zhejiang University + CAS/ECOS). The descriptor is now **fully enriched**: 3 std-cell Vt flavors (RVT/HVT/LVT, H7C) with LEF/GDS/Verilog + a **7-corner NLDM Liberty** set (tt/ss/ff × cworst/rcworst/cbest/rcbest) and the IO library — **13 corners, 4 libraries**, `verify`-clean → **place + STA-sign-off-able**. The large `.lib`/`.gds` are release assets materialized by `make unzip` into `$ICSPROUT55_PDK` (the git mirror carries LEF/CDL/Verilog + the fetch mechanism). Still upstream-pending: SPICE/RC models + DRC/LVS decks, so extraction/DRC/LVS remain gated.

## Consuming it

`vyges pdk-store` ships a cached snapshot of `index.json` compiled into the binary and
refreshes it from here on connectivity, so `list` works offline and stays current online.
The full descriptor for any PDK is fetched on demand via its `descriptor_url`.

---
© Vyges 2026. All Rights Reserved. PDK descriptors describe third-party PDKs; each PDK
remains under its own upstream license.
