# Secrets Rate Limits and Anomaly v1

This document freezes phase-A contract targets before implementation.

Planned v1 controls:
- Fixed-window request limiting by context and classification.
- Event emission for rate-limit denial.
- Basic anomaly signaling for suspicious request spikes.

Contract notes:
- Denial behavior must be fail-closed.
- No secret values may appear in telemetry.
- Reason codes remain stable once implemented.
