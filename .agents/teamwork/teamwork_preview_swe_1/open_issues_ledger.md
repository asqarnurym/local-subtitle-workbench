# Open Issues Ledger

Cumulative open-issues ledger maintained across all SWE Light refinement rounds.

## Open Items
- [Round 0 Implementer / Round 1 Reviewer / Round 2 Reviewer] Live ASR execution using real GPU / faster-whisper or MFA Kaldi binaries (deferred by design to Increments 2 and 4 per SDLC roadmap).
- [Round 0 Implementer / Round 1 Reviewer / Round 2 Reviewer] Non-English character sets (multilingual expansion is explicitly out-of-scope for Increment 1 English core).
- [Round 0 Implementer / Round 1 Reviewer / Round 2 Reviewer] Number parsing currently covers standard English formats (integers, thousands separators, decimals, and ordinals up to 10^12). Unconventional mixed alphanumerics without hyphens (e.g. "3D", "4K") are normalized as words rather than spelled out as digits.
- [Round 1 Reviewer / Round 2 Reviewer] Live acoustic alignment against noisy audio will require CTC/HMM alignment engines (scheduled for Increments 2 and 4).
- [Round 2 Reviewer / Resolved in Round 3] Extreme token-to-cue duration limits or zero-duration token sequences edge cases in WebVTT cue generation (resolved via _adjust_cue_timing enforcing monotonic non-overlapping boundaries, duration preservation, and millisecond rounding collapse prevention).

