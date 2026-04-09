# HCA Architecture: Upgraded Version (v5)

This document describes the upgraded architecture of the Hybrid Cognitive Agent (HCA), moving from a static stub-based implementation to a functional, stateful, and grounded cognitive runtime.

## Core Components

### 1. Global Workspace (`hca.workspace`)
The workspace acts as a shared, salience-driven blackboard for module interaction.
- **Admission Control**: Filters module proposals based on salience and confidence.
- **Recurrence**: Bounded recurrent passes resolve contradictions by pruning lower-confidence items.
- **Broadcast**: Distributes the contents of the workspace back to all modules.

### 2. Meta Monitor (`hca.meta`)
The monitor provides real-time oversight of the workspace.
- **Contradiction Detection**: Identifies conflicting action suggestions.
- **Information Gap Analysis**: Detects missing parameters for proposed actions.
- **Self-Model**: Checks proposed actions against the agent's known limitations.
- **Control Signals**: Issues signals like `proceed`, `ask_user`, or `replan` to the runtime.

### 3. Stateful Runtime (`hca.runtime`)
The runtime orchestrates the agent loop and manages persistence through an authoritative state machine.
- **Event Logging**: All transitions and actions are recorded in a deterministic event log with UTC timestamps.
- **State Enforcement**: The runtime validates all state transitions against an allowed transition matrix.
- **Pause/Resume**: Supports asynchronous human-in-the-loop approvals with token-based consumption.
- **Replay**: Can reconstruct the exact state of any run by replaying its event log from scratch.
- **Bounded Replanning**: The runtime supports a configurable replan budget to resolve contradictions without infinite loops.

### 4. Hardened Executor (`hca.executor`)
The executor is the single point of contact for external side effects.
- **Tool Registry**: Maintains metadata, input schemas, and policy constraints for all tools.
- **Policy Enforcement**: Checks for required approvals and risk levels before execution.
- **Artifact Management**: Automatically records files produced by tools.

### 5. Memory System (`hca.memory`)
A multi-store memory system for long-term knowledge and short-term context.
- **Episodic Store**: Records past actions and observations.
- **Semantic Store**: Holds general knowledge.
- **Contradiction Check**: Detects when new memories conflict with existing knowledge at retrieval time.
- **Staleness**: Decays the relevance of older information.
- **Consolidation**: Background process for summarizing and cleaning memory.

## Data Flow

1. **Perceive**: `TextPerception` interprets the raw goal into structured intents.
2. **Plan**: `Planner` formulates high-level strategies based on the perceived intent.
3. **Reason**: `ToolReasoner` selects specific tools to fulfill the plan.
4. **Critique**: `Critic` validates action candidates against the tool registry.
5. **Admit**: Workspace selects items based on salience and confidence.
6. **Recur**: Workspace resolves internal conflicts via bounded recurrence.
7. **Assess**: Meta-monitor evaluates the workspace and issues a control signal (e.g., `replan`).
8. **Select**: Runtime picks the best action candidate.
9. **Approve**: If risky or required by policy, the runtime pauses for user approval.
10. **Execute**: Executor runs the tool, enforcing safety policies and recording receipts.
11. **Observe**: Results are committed to episodic memory.
12. **Report**: Final summary is emitted to the user.

## Current Status (v5)
- **Self-Model & Missing Info**: Operationalized the `SelfModel` and `MissingInfo` modules for more robust meta-control.
- **Memory Consolidation**: Implemented background consolidation logic for cleaning and summarizing episodic memory.
- **Harden Replay & Approvals**: Stateful reconstruction handles approval denials, expirations, and richer snapshots.
- **Memory Staleness & Contradiction**: Retrieval now calculates staleness scores and flags contradictory records.
- **Operational Meta-Control**: Meta-monitor detects contradictions and stale memory, issuing real control signals like `replan` and `ask_user`.
- **Grounded Cognition**: Perception, Planner, and ToolReasoner use grounded logic responding to workspace broadcast.
- **Bounded Recurrence**: Workspace resolves internal conflicts via real module-based revision and confidence-based pruning.
- **Complete API**: FastAPI application exposes all internal capabilities including state reconstruction, approval management, and memory search.
