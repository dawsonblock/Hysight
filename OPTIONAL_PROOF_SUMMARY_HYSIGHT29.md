# Hysight-main 29 optional proof summary

## Classification
optional lanes freshly proved in the release-seal run

## Freshly proved in this seal
| Surface | Fresh result | Evidence |
| --- | --- | --- |
| Bounded autonomy optional | 50 passed, 0 skipped | `artifacts/proof/autonomy-optional.json` |
| Live Rust sidecar | 13 passed, 2 skipped | `artifacts/proof/live-sidecar.json` and `artifacts/proof/release_sidecar.log` |
| Sidecar no-fallback | explicit fail-closed `MemoryConfigurationError` | `artifacts/proof/release_sidecar_no_fallback.txt` |
| Frontend proof | 20 passed, 0 skipped | `artifacts/proof/frontend.json` and `artifacts/proof/release_frontend.log` |

## Historical and ignored
| Surface | Status in this report |
| --- | --- |
| Backend integration proof | historical receipt present but not counted |
| Live Mongo proof | historical receipt present but not counted |
| Older Hysight 27/28/29 optional artifacts | historical only |

## Honesty note
This summary counts only the optional surfaces rerun during the 2026-04-19 clean-tree release seal.
