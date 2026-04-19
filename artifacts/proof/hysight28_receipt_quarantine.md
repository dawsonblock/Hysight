# Hysight-main 28 receipt quarantine ledger

## Fresh receipts counted for classification
- pipeline.json
- backend-baseline.json
- contract.json
- baseline.json
- autonomy-optional.json
- live-sidecar.json
- frontend.json

## Fresh supporting transcripts counted for classification
- hysight28_receipt_env.txt
- hysight28_prereq.log
- hysight28_baseline_receipt_refresh.log
- hysight28_autonomy.log
- hysight28_sidecar.log
- hysight28_sidecar_no_fallback.txt
- hysight28_sidecar_service.log
- hysight28_frontend.log

## Historical artifacts present but not counted
- integration.json
- live-mongo.json
- optional_env_facts.txt
- sidecar_live.log
- every hysight27_* artifact under artifacts/proof

## Reconciliation notes
- The bundled backend-baseline count observed before refresh was 96.
- The fresh clean-copy rerun produced 98 passed, 1 deselected.
- Classification for Hysight-main 28 uses only the refreshed receipt set above.
