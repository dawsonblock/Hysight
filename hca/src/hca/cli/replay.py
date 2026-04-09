"""Replay CLI for the hybrid cognitive agent."""

import argparse
import json
from hca.runtime.replay import reconstruct_state
from hca.storage.event_log import iter_events

def main() -> None:
    parser = argparse.ArgumentParser(description="Replay and reconstruct run state.")
    parser.add_argument("run_id", help="ID of the run to replay")
    parser.add_argument("--events", action="store_true", help="Show raw events instead of state summary")
    args = parser.parse_args()
    
    if args.events:
        print(f"--- Raw Events for Run {args.run_id} ---")
        for event in iter_events(args.run_id):
            print(json.dumps(event, indent=2))
    else:
        state = reconstruct_state(args.run_id)
        print(f"--- Reconstructed State for Run {args.run_id} ---")
        print(f"Current State: {state['state']}")
        print(f"Transition History: {' -> '.join(state['transition_history'])}")
        print(f"Workspace Count: {state['workspace_count']}")
        
        selected_action = state.get('selected_action')
        if selected_action:
            print(f"Selected Action: {selected_action.get('kind')} (ID: {selected_action.get('action_id')})")
            
        pending_approval_id = state.get('pending_approval_id')
        if pending_approval_id:
            print(f"Pending Approval ID: {pending_approval_id}")
            
        last_approval_decision = state.get('last_approval_decision')
        if last_approval_decision:
            print(f"Last Approval Decision: {last_approval_decision}")
            
        latest_receipt_id = state.get('latest_receipt_id')
        if latest_receipt_id:
            print(f"Latest Receipt ID: {latest_receipt_id}")
            
        artifacts = state.get('artifacts', [])
        if artifacts:
            print(f"Artifacts Produced: {len(artifacts)}")
            for art_id in artifacts:
                print(f"  - {art_id}")
        
        print(f"Memory Counts: {state['memory_counts']}")
        print(f"Events Replayed: {state['events_replayed']}")
        print(f"Reconstructed via: {state['reconstructed_at']}")

if __name__ == "__main__":
    main()
