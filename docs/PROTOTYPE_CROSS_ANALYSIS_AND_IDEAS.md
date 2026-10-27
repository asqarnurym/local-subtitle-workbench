# Cross-Project Analysis: Publication 1 Commitments, Prototype Backlog Audit & Synthesis

**Project:** Local Subtitle Alignment Workbench  
**Author:** Askar Nurym  
**Source Cross-Reference:** `C:\Users\nurym\Desktop\Prototype`  
**Target Repository:** `local-subtitle-workbench`  
**Status:** Strategic Roadmap Analysis

---

## 1. Context & Objectives

The predecessor project (`Prototype`, authored during Trimesters 2–3) resulted in:
1. **Publication 1:** Conference paper titled *«Design of a Multimodal Pipeline for Accessibility in E-Learning Content»* (presented at the IEEE 3rd International Student Conference on Digital Generation, October 2026, Astana, Kazakhstan).
2. **Prototype Codebase:** Python FastAPI service integrating Whisper ASR, PySceneDetect visual scene extraction, hosted Google Cloud Vertex AI (Gemini 2.5 Flash), and Google Neural TTS.
3. **Engineering Backlog:** Detailed in `Prototype/TODO.md`.

This document performs a **rigorous cross-project audit**:
- Identifies commitments made in Publication 1 and determines their current status.
- Filters out obsolete, cloud-dependent, or superseded tasks.
- Synthesizes high-value engineering and architectural concepts to integrate into the workbench roadmap.

---

## 2. Audit of Commitments in Publication 1 (`paper.tex`)

In Section 6 (*Threats to Validity*) and Section 7 (*Conclusion & Future Work*) of Publication 1, several explicit research commitments were recorded:

```
                            PUBLICATION 1 COMMITMENT AUDIT
┌───────────────────────────────────────┬─────────────────┬───────────────────────────────────────────────────────┐
│ Stated Commitment / Limitation        │ Status in 2026  │ Resolution / Current Treatment                        │
├───────────────────────────────────────┼─────────────────┼───────────────────────────────────────────────────────┤
│ 1. "Manual validation of caption      │ SUPERSEDED &    │ Dismissed as unscientific on uncurated video. Replaced│
│ accuracy (WER/CER) is left for future │ RESOLVED        │ by DARPA/NIST TIMIT Core Test & Buckeye Gold Standard │
│ work."                                │                 │ evaluating millisecond-level Word & Phone MAE.       │
├───────────────────────────────────────┼─────────────────┼───────────────────────────────────────────────────────┤
│ 2. "ASR confidence does not indicate  │ RESOLVED        │ Switched from confidence proxies to exact millisecond │
│ actual transcription accuracy."       │                 │ boundary evaluation (MAE, Acc@20ms).                  │
├───────────────────────────────────────┼─────────────────┼───────────────────────────────────────────────────────┤
│ 3. "A larger test corpus with source  │ RESOLVED        │ Adopted recognized benchmark standards (LDC93S1,      │
│ links and license metadata..."        │                 │ Buckeye) with immutable SHA-256 manifest audit trails.│
├───────────────────────────────────────┼─────────────────┼───────────────────────────────────────────────────────┤
│ 4. "Timestamp refinement using forced │ DELIVERED       │ Fully implemented in Increment 4 via dual-engine      │
│ alignment (WhisperX, CrisperWhisper)" │                 │ facade: Kaldi GMM-HMM (MFA) and TorchAudio MMS_FA CTC.│
├───────────────────────────────────────┼─────────────────┼───────────────────────────────────────────────────────┤
│ 5. "Verification of positive impact   │ PLANNED         │ Retained for Master's Thesis empirical evaluation     │
│ on learners with disabilities"        │ (Trimester 6)   │ (human-subject user study / pedagogical testing).     │
└───────────────────────────────────────┴─────────────────┴───────────────────────────────────────────────────────┘
```

### Critical Elimination of Obsolete Commitments:
> [!IMPORTANT]
> **Why manual WER/CER on arbitrary videos is eliminated:**  
> Manual transcript annotation on raw YouTube/auditorium video is error-prone ($\sigma_{\text{human}} \approx 10\text{--}35$ ms) and lacks phonetic ground truth. Attempting manual WER/CER calculation without phonetic time-codes provides zero insight into acoustic synchronization. In `local-subtitle-workbench`, this limitation was decisively resolved by adopting the **DARPA/NIST TIMIT Core Test standard**, where hand-aligned word (`.wrd`) and phonetic (`.phn`) labels were established by MIT phoneticians.

---

## 3. Critical Audit of `Prototype/TODO.md`

`Prototype/TODO.md` contained 7 active pipeline improvement tasks and candidate ideas. We evaluate each critically against our offline synchronization mandate:

| Item in `Prototype/TODO.md` | Core Description | Critical Verdict | Rationale for Verdict |
| :--- | :--- | :---: | :--- |
| **Item 1: Transcription-anchored scene sampling** | Anchor scenes at ASR sentence ends and long pauses. | **ACCEPTED -> TRANSFER TO BENCHMARK** | Natural pause anchoring ($\tau \ge 0.4$ s via Silero-VAD) directly reinforces our macro-chunking and DTW boundary stability. |
| **Item 2: Content-adaptive PySceneDetect thresholds** | Tuning visual change thresholds (27 for screencast, 18 for talking-head). | **OUT OF SCOPE** | Purely a visual heuristic for video scene cuts; irrelevant to audio-to-text forced alignment. |
| **Item 3: Few-shot prompting for Gemini** | Adding examples to suppress generic LLM descriptions. | **REJECTED** | Specific to hosted Google Vertex AI; our workbench is 100% local, private, and deterministic. |
| **Item 4: Content-aware blank frame detection** | Skipping static slide frames (<2% pixel difference). | **OUT OF SCOPE** | Computer vision preprocessing; unrelated to speech synchronization. |
| **Item 5: Scene-to-transcript contextual alignment** | Enriching visual scenes with nearest spoken text. | **VALUABLE CANDIDATE** | Enriches accessibility artifacts: aligning WebVTT karaoke tokens with visual slide transitions in JSON-LD media fragments. |
| **Item 6 & 7: Vertex AI rate-limits & location routing** | Retrying 429 errors and selecting `europe-west1`. | **REJECTED** | Cloud-dependent latency artifact. Our architecture operates entirely offline on local student hardware. |

---

## 4. Candidate Ideas Selected for the Workbench Roadmap

From the cross-analysis, three high-value architectural ideas are extracted to enrich the `local-subtitle-workbench` engineering backlog:

### Idea 1: Interactive Demonstration UI (Gradio / Web Karaoke Player)
- **Origin:** Prototype interaction layer (`static/` and `api/` media player).
- **Value for Workbench:** While the CLI and REST API provide robust automation, demonstrating the millisecond-level precision of the algorithm to academic committees, supervisors, and conference attendees requires a visual interface.
- **Formulation:**
  - Option A: A lightweight **Gradio Web UI** (`scripts/demo_gradio.py`) allowing audio upload, engine selection (`mfa` vs `ctc`), and immediate interactive playback with word highlight sync.
  - Option B: A static standalone HTML5/JS video player reading `subtitles.vtt` and applying CSS karaoke animations on `<c.word>` tags.
- **MoSCoW Status:** **SHOULD HAVE** (Prioritized for demonstration milestones).

### Idea 2: Pause-Anchored Structural Chaptering
- **Origin:** `Prototype/TODO.md` Item 1 & Item 5.
- **Value for Workbench:** Educational lectures naturally divide into conceptual segments around extended lecturer pauses ($\tau > 1.5$ s) and slide changes. By integrating Silero-VAD pause detection with JSON-LD chapter markers, the workbench can automatically emit structured table-of-contents markers alongside word timestamps.
- **MoSCoW Status:** **COULD HAVE**.

### Idea 3: Asynchronous Queue & Docker-Compose Wrapper
- **Origin:** Prototype dual-write persistence and batch scaling.
- **Value for Workbench:** For long-form lecture processing (30–60 minutes), synchronous HTTP requests risk client timeouts. Packaging FastAPI with an asynchronous background task queue (Celery or ARQ with Redis) and an all-in-one `docker-compose.yml` provides a production-grade educational microservice.
- **MoSCoW Status:** **SHOULD HAVE**.
