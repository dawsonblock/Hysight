from datetime import datetime, timezone
from hca.common.time import utc_now, to_iso, parse_iso
from hca.common.types import ApprovalDecisionRecord, ApprovalGrant, ApprovalConsumption
from hca.common.enums import ApprovalDecision

def test_time_helpers():
    now = utc_now()
    assert now.tzinfo == timezone.utc
    
    iso = to_iso(now)
    parsed = parse_iso(iso)
    assert parsed == now
    assert parsed.tzinfo == timezone.utc

def test_approval_models_split():
    # Decision Record
    dr = ApprovalDecisionRecord(
        approval_id="app-1",
        decision=ApprovalDecision.denied,
        reason="too risky"
    )
    assert dr.decision == ApprovalDecision.denied
    assert dr.decided_at.tzinfo == timezone.utc
    
    # Grant
    grant = ApprovalGrant(
        approval_id="app-1",
        token="secret-token"
    )
    assert grant.token == "secret-token"
    assert grant.granted_at.tzinfo == timezone.utc

if __name__ == "__main__":
    test_time_helpers()
    print("test_time_helpers passed")
    test_approval_models_split()
    print("test_approval_models_split passed")
