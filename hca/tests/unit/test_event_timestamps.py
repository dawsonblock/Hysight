import time
from datetime import datetime, timezone
from hca.common.types import RunContext
from hca.storage.event_log import append_event, iter_events
from hca.common.enums import EventType

def test_event_timestamps_are_fresh_and_aware():
    run = RunContext(goal="test timestamps")
    # Initial updated_at is set at creation
    initial_updated_at = run.updated_at
    
    # Wait a bit to ensure time moves
    time.sleep(0.1)
    
    append_event(run, EventType.run_created, "test", {"msg": "first"})
    time.sleep(0.1)
    append_event(run, EventType.run_created, "test", {"msg": "second"})
    
    events = list(iter_events(run.run_id))
    assert len(events) == 2
    
    ts1 = datetime.fromisoformat(events[0]["timestamp"])
    ts2 = datetime.fromisoformat(events[1]["timestamp"])
    
    # Assert timestamps are timezone-aware (not None)
    assert ts1.tzinfo is not None
    assert ts2.tzinfo is not None
    
    # Assert timestamps are fresh (greater than initial_updated_at)
    assert ts1 > initial_updated_at
    assert ts2 > ts1
    
    print("Event timestamp test passed!")

if __name__ == "__main__":
    test_event_timestamps_are_fresh_and_aware()
