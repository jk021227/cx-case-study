# Assignment 3: Early Warning Process (EWP) — Design Document

> **Context:** This document designs an n8n-based Early Warning Process that
> continuously monitors customer complaint signals and fires graduated alerts
> before complaint surges become crises.

---

## 1. Goals

| Goal | Description |
|------|-------------|
| Early detection | Catch volume spikes within 15 minutes, not next-day reports |
| Theme awareness | Surface emerging complaint topics before manual review |
| Graduated response | Match alert urgency to signal severity (INFO → WARN → CRITICAL) |
| Human-in-the-loop | Require human acknowledgement for WARN/CRITICAL before auto-escalation |
| Audit trail | Log every signal, alert, and human action for compliance/review |

---

## 2. Signal Definitions

| Signal ID | Name | Description | Data Source |
|-----------|------|-------------|-------------|
| SIG-01 | Volume Spike | Total complaint count in rolling window exceeds baseline × multiplier | Complaint intake DB |
| SIG-02 | Theme Spike | A single theme's share jumps above its baseline percentage | Theme classification table |
| SIG-03 | Severity Escalation | High-severity complaint proportion exceeds threshold in window | Severity field on intake |
| SIG-04 | Channel Surge | One channel accounts for an anomalous share of complaints | Channel field on intake |
| SIG-05 | Keyword Alert | Critical keywords appear above frequency threshold in complaint text | Real-time text scan |
| SIG-06 | No-Data Alert | Complaint volume drops to near-zero (pipeline failure detection) | Intake count watchdog |

---

## 3. Baseline & Threshold Formulas

### 3.1 Volume Spike (SIG-01)

```
baseline_volume(t) = mean( daily_count[t-28 : t-1] )   # 28-day rolling mean
std_volume(t)      = std(  daily_count[t-28 : t-1] )

threshold_WARN     = baseline_volume(t) + 1.5 × std_volume(t)
threshold_CRITICAL = baseline_volume(t) + 3.0 × std_volume(t)
```

**Minimum floor:** WARN fires at ≥ 10 complaints/hour even if std-based threshold is lower.

### 3.2 Theme Spike (SIG-02)

```
baseline_theme_pct(theme, t) = mean( theme_share_daily[t-14 : t-1] )

spike_factor = current_theme_pct / baseline_theme_pct

threshold_WARN     = spike_factor > 1.5   # 50% above 14-day baseline
threshold_CRITICAL = spike_factor > 2.5   # 150% above 14-day baseline
```

### 3.3 Severity Escalation (SIG-03)

```
high_pct(t) = count(severity='high', window=4h) / count(all, window=4h)

threshold_WARN     = high_pct > 0.30   # >30% high severity
threshold_CRITICAL = high_pct > 0.50   # >50% high severity
```

### 3.4 Keyword Alert (SIG-05)

```
keyword_freq(kw, t) = count(kw in text, window=1h)

threshold_WARN     = keyword_freq > 5    per hour
threshold_CRITICAL = keyword_freq > 15   per hour
```

**Critical keywords:**
`fraud`, `unauthorized`, `breach`, `hack`, `lawsuit`, `CFPB`, `BBB`,
`attorney general`, `class action`, `regulator`, `escalate`

### 3.5 No-Data Alert (SIG-06)

```
# Fires if complaint intake drops to zero for more than:
threshold_WARN     = 2 continuous hours with 0 complaints
threshold_CRITICAL = 4 continuous hours with 0 complaints
```

---

## 4. Escalation Levels

| Level | Colour | Trigger | Response SLA | Notified Parties |
|-------|--------|---------|-------------|-----------------|
| **INFO** | 🔵 Blue | Signal detected but below WARN | 4 hours | CX Analytics team (dashboard update only) |
| **WARN** | 🟡 Amber | Any single signal crosses WARN threshold | 1 hour | CX Team Lead + Product Manager |
| **CRITICAL** | 🔴 Red | Any signal crosses CRITICAL threshold **OR** 2+ WARN signals simultaneously | 15 minutes | CX Director + VP Operations + On-call Engineer |

---

## 5. Human-in-the-Loop (HITL) Design

```
Alert fires
    │
    ▼
Slack message + email sent to on-call CX lead
    │
    ▼
┌─────────────────────────────────────────────┐
│  Human acknowledgement window               │
│  • CRITICAL: 15 min                         │
│  • WARN:     60 min                         │
│                                             │
│  Actions:  [Acknowledge] [False Positive]   │
│            [Investigating] [Resolved]        │
└─────────────────────────────────────────────┘
    │                        │
[Acknowledged]         [Timeout — no response]
    │                        │
Log outcome             Escalate to next tier
    │                   Page secondary on-call
    ▼                        │
Periodic status          Log escalation
updates every 30 min     to audit DB
```

**Implementation note:** Acknowledgement is triggered by a Slack button click
or a reply to the alert email. Both call the same n8n webhook endpoint.

---

## 6. n8n Workflow — Node Sequence

See `ewp_workflow.mmd` for the full Mermaid diagram.

### Node descriptions

| Step | n8n Node Type | Action |
|------|---------------|--------|
| 1 | Schedule Trigger | Runs every 15 minutes (configurable) |
| 2 | Postgres / HTTP | Fetches complaint counts from intake DB or API |
| 3 | Function | Computes SIG-01 to SIG-06 metrics |
| 4 | IF | Checks each signal against WARN / CRITICAL thresholds |
| 5 | Function | Determines escalation level and builds alert payload |
| 6 | Slack | Posts alert card to `#cx-alerts` (or `#cx-critical`) |
| 7 | Email | Sends HTML alert email to on-call distribution list |
| 8 | Wait | Waits for HITL webhook acknowledgement (with timeout) |
| 9 | IF | Checks if acknowledged within SLA |
| 10 | Slack / PagerDuty | Escalates if not acknowledged in time |
| 11 | Postgres | Logs every event to `ewp_audit_log` table |

---

## 7. Example JSON Alert Payload

```json
{
  "alert_id": "EWP-2024-03-28-0042",
  "generated_at": "2024-03-28T14:32:07Z",
  "level": "CRITICAL",
  "signal": {
    "id": "SIG-01",
    "name": "Volume Spike",
    "window_hours": 1,
    "current_value": 47,
    "baseline_value": 12.4,
    "threshold_critical": 37.2,
    "spike_factor": 3.79
  },
  "context": {
    "top_theme": {
      "theme_id": 2,
      "label": "App & Login Issues",
      "count_in_window": 23,
      "share_pct": 48.9
    },
    "top_channel": "mobile_app",
    "top_keywords": ["crash", "login", "error", "cannot access"],
    "example_complaint_ids": ["C022", "C026", "C030"]
  },
  "escalation": {
    "notified": [
      "cx-director@company.com",
      "vp-operations@company.com",
      "oncall-engineer@company.com"
    ],
    "slack_channel": "#cx-critical-alerts",
    "acknowledgement_required_by": "2024-03-28T14:47:07Z",
    "next_escalation_if_unacked": "2024-03-28T15:02:07Z"
  },
  "audit": {
    "workflow_run_id": "n8n-run-8829a1f",
    "data_source": "complaints_db.intake",
    "rows_evaluated": 47,
    "ewp_version": "1.2.0"
  }
}
```

> **PII note:** Example complaint texts are **not** included in the alert payload.
> Only complaint IDs are referenced. Full text requires role-based access to the DB.

---

## 8. Logging & Audit

### Audit log schema

```sql
CREATE TABLE ewp_audit_log (
    log_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type      TEXT NOT NULL,   -- see values below
    alert_id        TEXT,
    signal_id       TEXT,
    level           TEXT,            -- INFO | WARN | CRITICAL
    actor           TEXT,            -- 'system' or user email
    details         JSONB,
    workflow_run_id TEXT
);

-- event_type values:
-- WORKFLOW_RUN     — every 15-min execution (even if no alerts)
-- THRESHOLD_CHECK  — each signal evaluated
-- ALERT_FIRED      — alert created and sent
-- ALERT_ACKED      — human acknowledged
-- ALERT_ESCALATED  — timeout escalation fired
-- FALSE_POSITIVE   — human marked as false positive
-- ALERT_RESOLVED   — human marked as resolved
```

### Retention policy

| Log type | Retention |
|----------|-----------|
| Alert logs | 7 years (financial services regulatory requirement) |
| Workflow execution logs | 90 days |
| HITL interaction logs | 2 years |
| False-positive labels | Indefinite (used for threshold calibration) |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Threshold too tight → alert fatigue | Medium | Tune thresholds on 6 months of historical data; weekly review cadence |
| Threshold too loose → missed events | High | Hard minimum: CRITICAL always fires at 3σ volume spike |
| LLM hallucination in alert summaries | Medium | Alert includes only retrieved examples + IDs, not generated text; human reviews before action |
| Data pipeline failure (SIG-06) | High | Dedicated watchdog checks intake count every 5 min; escalates independently of main workflow |
| PII leak in Slack/email | High | Strip all free-text from alert payload; reference complaint IDs only; Slack channel is private |
| n8n outage | Critical | Health check endpoint monitored by external uptime service; backup cron script sends manual digest |
| False positives reducing trust | Medium | Track FP rate; auto-silence repeated FPs on same signal within 24 h; monthly calibration review |

---

## 10. Assumptions

1. A relational DB (PostgreSQL or equivalent) holds complaint intake with
   columns matching the sample schema: `complaint_id, date, channel,
   product_category, complaint_text, severity`.
2. Theme classification is pre-computed and stored in a `theme_labels` table
   (updated by a nightly batch running Assignment 1). For real-time classification,
   a lightweight keyword-based classifier can be substituted.
3. n8n is self-hosted (or n8n Cloud) with credentials configured for the DB,
   Slack workspace, email relay, and optionally PagerDuty.
4. The 28-day rolling baseline requires ≥ 4 weeks of historical data on first run.
   For cold-start, use a manually set baseline derived from domain expertise.
5. Severity labels are provided in the intake data (manual or from a classifier).
   If absent, SIG-03 is disabled and a note is logged.

---

_CX Case Study — Assignment 3 | EWP Design v1.0_
