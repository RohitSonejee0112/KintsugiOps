# ADR 002: Process Mining with pm4py and Pandas for Gap Analysis

## Status
Accepted

## Context
The resume bullet asserts: *"Engaged with AI-assisted automation tooling to identify operational process gaps, proposing structural improvements."* To ground this claim in empirical, industry-standard science rather than superficial text generation, we needed algorithmic process discovery on event logs.

## Decision
We implemented event-log extraction adhering to the IEEE XES standard and integrated **pm4py** and **pandas**:
1. **Directly-Follows Graphs (DFG)**: Automatically discovers transition pathways between activities (`Created`, `Assigned`, `Reassigned`, `Resolved`).
2. **Transition Dwell Times**: Computes mean, median, and 95th-percentile durations between each lifecycle stage to locate exact queue bottlenecks.
3. **Ping-Pong Reassignment Detection**: Identifies tickets bouncing $\ge 2$ times across assignment groups and aggregates frequent bouncing team pairs.
4. **AI Structural Proposals**: Algorithmic metrics from pm4py are passed as evidence to the LLM/proposal generator, guaranteeing every structural proposal is backed by empirical data.

## Consequences
- Requires Pandas and pm4py.
- Produces rigorous, demonstrable audit reports that stand up to tough interviewer inspection.
