# ✨ KintsugiOps: Enterprise ITSM Platform Walkthrough & Demonstration Guide

This guide walks you through every section of **KintsugiOps** — an enterprise AI-assisted ITSM automation, conformance checking, and process mining portal. It explains **what actions to take**, **how the RBAC delegation & audit trail operates**, **what results you will observe**, and **unbeatable technical interview talking points**.

---

## 🚀 How to Launch the Portal

In your project root (`e:\ticketing project`), start the Streamlit portal:

```powershell
& .venv\Scripts\streamlit.exe run src/dashboard/app.py
```

Open your browser to: **`http://localhost:8501`**

---

## 👤 Left Sidebar: RBAC Persona Switcher & Portal Navigation

### 1. Concept & Multi-Role Architecture
Unlike a simple dashboard, this platform functions as a full-fledged **Enterprise ITSM Portal** featuring **Role-Based Access Control (RBAC)**:
- **`Sarah Connor` (Dispatcher / Triage Lead)**: `dispatcher@corp.com` — Triages incoming incidents, reviews AI evidence, delegates tickets to engineers according to ITIL seniority rules, and tracks live status feeds.
- **`David Miller` (ERP Systems Lead)**: `david.miller@corp.com` — Enterprise ERP & SAP Lead. Automatically pre-selected as the default assignee for all ERP/SAP tickets.
- **`Alice Cooper` (Desktop Support Lead)**: `tech-alice@corp.com` — Hardware team lead. Automatically pre-selected as the default assignee for Hardware tickets.
- **`Bob Martinez` (IAM Specialist / Lead)**: `tech-bob@corp.com` — Identity team lead. Automatically pre-selected as default assignee for Access/IAM tickets.
- **`Carol Danvers` (Network Operations Lead)**: `specialist-carol@corp.com` — Network team lead. Automatically pre-selected as default assignee for Network tickets.
- **`Allison Hill` (End-User Employee)**: `allison.hill@corp.com` — Submits service requests and tracks resolution progress.
- **`Elena Vance` (Service Delivery Lead / Auditor)**: `elena.auditor@corp.com` — Audits ITIL conformance, process mining bottlenecks, and SharePoint structural proposals.

### 2. Actions to Take
1. Look at the **User Profile Card** at the top of the sidebar.
2. Click **"👤 Switch Authenticated Persona"** to switch between **Dispatcher (Sarah Connor)**, **ERP Lead (David Miller)**, **Desktop Support (Alice Cooper)**, **IAM Lead (Bob Martinez)**, **Network Lead (Carol Danvers)**, **End-User (Allison Hill)**, or **Auditor (Elena Vance)** in 1 click.
3. Use the **Clickable Portal Navigation** buttons on the left to move between views:
   - `🎯 Live Triage Console`
   - `📥 Operational Inbox & Delegation Tracker`
   - `🔍 Process Mining & ITIL Audit`
   - `📋 SharePoint Governance & Proposals`
   - `📊 Simulation & ROI Benchmark`

---

## 🎯 View 1: Live Triage Console

### 1. Purpose & Concept
Real-time ticket intake, **security guardrails (PII redaction & prompt injection defense)**, **Split Conformal Prediction** (statistically bounded $< 5\%$ error rate), **Vector Semantic Caching & Outage Storm Clustering**, **Tiered Seniority Delegation Engine (20 Engineers Across 4 Domains)**, and **Audit Dossier Exporting**.

### 2. Tiered Seniority Delegation Matrix (20 Support Engineers)
The portal features exactly 20 support engineers distributed across 4 technical domains (5 members per domain):

| Domain / Type | Operational Group | Team Lead (P1, P2, P3, P4) ⭐ Preferred Default | Senior Engineers (P2, P3, P4) | Junior Engineers (P3, P4 only) |
|---|---|---|---|---|
| **Type 1: ERP / SAP** | `Enterprise-ERP-Support` | **David Miller** (`david.miller@corp.com`) | Kavita Patel, Marcus Vance | Siddharth Rao, Chloe Bennett |
| **Type 2: Hardware** | `Desktop-Support-L2` | **Alice Cooper** (`tech-alice@corp.com`) | James Wilson, Rachel Green | Lucas Scott, Maya Lin |
| **Type 3: Network** | `Network-Infrastructure-Ops` | **Carol Danvers** (`specialist-carol@corp.com`) | Vikram Malhotra, Samantha Cole | Ethan Hunt, Priya Sharma |
| **Type 4: Access / Identity** | `IAM-Identity-Operations` | **Bob Martinez** (`tech-bob@corp.com`) | Fatima Zahra, Liam O'Connor | Noah Clark, Zara Ahmed |

#### ITIL Delegation Rules Enforced:
- **Strict Category Isolation**: Only engineers of that specific ticket category appear in the dropdown. E.g., an ERP ticket will *never* show Hardware or Network staff.
- **Priority 1 (Critical Outage)**: Restricted strictly to the **Team Lead / Manager** (exactly 1 engineer shown).
- **Priority 2 (High Priority)**: Restricted to **Lead + Senior Engineers** (exactly 3 engineers shown; Juniors excluded).
- **Priority 3 / 4 (Standard / Low)**: Open to **all 5 members** (1 Lead + 2 Seniors + 2 Juniors).
- **Automatic Pre-Filled Preferred Default**:
  - When an ERP ticket is generated, **David Miller is automatically pre-selected** by default.
  - Dispatcher **Sarah Connor has full authority to change the assignee** to any other eligible member in the dropdown before dispatching.

### 3. Actions to Take
1. Click **"🎲 Generate Realistic Random Ticket"** to populate realistic enterprise scenarios.
2. Inspect the **PII Guardrail** alert: emails and IPs are automatically sanitized before model inference.
3. Review the **Conformal Calibration Status**:
   - If singleton ($|\Gamma| = 1$), a green badge confirms statistical safety ($\le 5\%$ error, $95\%$ coverage).
   - Click **"ℹ️ Conformal Calibration & Statistical Theory Details"** for in-depth mathematical notes.
4. **Inspect the Tiered Delegation Section**:
   - Notice the ITIL protocol badge highlighting eligible seniority tiers for the ticket's priority.
   - For an ERP ticket, notice **David Miller** is pre-filled as default assignee!
   - Expand the dropdown: observe that only ERP engineers are shown (1 member for P1, 3 members for P2, 5 members for P3).
   - If desired, change the assignee (e.g. choose `Kavita Patel [SENIOR]`).
   - Click **"📤 Assign & Dispatch Ticket to Engineer"**.
   - Notice the confirmation toast: the assignment is persisted in SQLite with `assigned_to`, `assigned_by`, and an audit event log!
5. **Download Dossier**:
   - Click **"📥 Download JSON Dossier"** or **"📄 Download Markdown Dossier"** to export the complete audit record.
6. Click **"⚡ Execute Auto-Runbook"** on Access tickets for instant self-service resolution.

---

## 📥 View 2: Operational Inbox & Delegation Tracker

### 1. Purpose & Concept
Demonstrates real-world multi-user ticket lifecycle tracking. Whatever ticket you route or assign is tracked in SQLite, with live activity feeds showing updates when tickets are worked on or resolved.

### 2. Actions to Take
1. Switch personas in the sidebar to **`Alice Cooper (Support Engineer L2)`**.
2. Click **"📥 Operational Inbox & Delegation Tracker"**.
3. Under **"📥 My Assigned Inbox"**, you will see tickets delegated to Alice!
   - Click **"▶️ Start Working (In Progress)"** $\to$ updates ticket state in the database.
   - Enter resolution notes and click **"✅ Mark as Resolved"** $\to$ marks ticket resolved, logs timestamp, and updates audit trail.
4. Switch personas in the sidebar back to **`Sarah Connor (Dispatcher / Triage Lead)`**.
5. Click **"📤 Delegated by Me (Tracking)"**:
   - View all tickets you assigned to Alice or other engineers.
   - Review the **⚡ Live Delegation Activity Feed** showing real-time updates:
     `🕒 [2026-10-16 10:45] tech-alice@corp.com performed Resolved on Ticket INC...`
6. Switch to **"👤 My Submitted Requests"** (when logged in as Allison Hill) to see end-user tracking.
7. Switch to **"🌐 Enterprise Ticket Register"** for full SQLite database querying.

---

## 🔍 View 3: Process Mining & ITIL Conformance Audit

### 1. Purpose & Concept
Uses **`pm4py`** and **IEEE XES** event logs to analyze process health: detecting stage bottlenecks, ping-pong loops, **Inductive Petri Net Conformance Checking (Token-Based Replay)**, and **Social Network Mining (Handover of Work)**.

### 2. Actions to Take
1. Click **"🔍 Process Mining & ITIL Audit"**.
2. Review top KPI cards: Total Events, Unique Cases, Avg Hops, and Ping-Pong Bounce Rate.
3. Inspect **Stage Bottlenecks & Mean Dwell Time**: identifies where tickets sit idle in queues.
4. Review **Top Reassignment Bouncing Loops**: highlights teams ping-ponging tickets (e.g. `ServiceDesk-L1 ➔ Enterprise-ERP-Support`).
5. Scroll down to **📐 Petri Net Conformance Checking & Token-Based Replay**:
   - Inspect Average Trace Fitness (e.g., `98.5%`), Precision Score (`88.4%`), F1 Process Score, and Compliant Case Count.
   - Review the **🚨 Detected ITIL Protocol Deviations Table**: identifies unauthorized direct resolution bypasses and escalation breaches.
6. Review the **🌐 Social Network Mining: Handover of Work Network** table showing cross-team handoffs.

---

## 📋 View 4: SharePoint Governance & Proposals

### 1. Purpose & Concept
Backs the resume bullet: **"proposing structural improvements and documenting the outcomes in SharePoint"**. Generates data-backed structural initiatives grounded in process mining, persisting to SharePoint Lists via Microsoft Graph API (with local offline JSON store).

### 2. Actions to Take
1. Click **"📋 SharePoint Governance & Proposals"**.
2. Note the clear storage indicator: `./local_sharepoint/lists/improvement_tracker.json`.
3. In any proposal card, change **Update Status** to `In Implementation` or `Approved`.
   - The status updates immediately in the SharePoint JSON list and logs an audit event in SQLite recording `actor = current_user`.
4. Click **"🔄 Synthesize Process Proposals"** to generate fresh proposals from latest pm4py metrics.
5. Click **"📄 Export Executive Process Mining Audit Report"** and **"📥 Download Report (Markdown)"**.

---

## 📊 View 5: Simulation & ROI Benchmark

### 1. Purpose & Concept
Backs the resume bullet: **"drastically improving response times for service requests"**. Runs a dual-layer quantitative simulation:
1. **Discrete-Event Monte Carlo Simulation**: Compares **Manual Human Baseline** vs. **AI Treatment** across thousands of tickets.
2. **Queueing Theory Realism ($M/M/c$ Queues & Kingman's Heavy-Traffic Formula)**: Explains the non-linear mathematical phenomenon of why shaving 38% of tier-1 tickets produces an exponential **90%+ reduction in queue backlog delay**.

### 2. Actions to Take
1. Click **"📊 Simulation & ROI Benchmark"**.
2. Adjust simulation sliders (Volume, Manual Triage Delay, Runbook Coverage).
3. Click **"🚀 Run Monte Carlo Simulation"**.
4. Review the **🏆 Resume Quantitative Numbers Summary**:
   - Numbers and units are uniformly formatted in bold orange (`3.5 hours`, `1.8 minutes`, `68.6% improvement`).
5. Scroll down to **📈 Queueing Theory Realism: Kingman's Law & Peak Saturation Dynamics**:
   - Inspect the comparative analysis:
     - Manual Traffic Intensity: $\rho = 0.94$ (Queue Saturation Risk) $\to$ $6.3$ hours backlog delay.
     - AI-Augmented Traffic Intensity: $\rho = 0.58$ (Optimal Linear Regime) $\to$ $0.56$ hours backlog delay.
     - **91.1% reduction in queue wait time** ($11.2\times$ faster queue clearance).
   - Expand **"📊 View Kingman Queue Hyper-Saturation Curve ($\rho$ vs $W_q$)"** to see the asymptotic explosion curve.

---

## 💡 Quick Interview Demonstration Script (2-Minute Demo)

1. **Start on Left Sidebar & Tab 1**:
   > *"This platform is built as an enterprise ITSM portal with role-based personas. As Sarah, our Dispatcher, I can review incoming tickets in the Live Triage Console. The platform redacts PII, applies Split Conformal Prediction to statistically bound false-positive risk under 5% before zero-touch execution, and clusters outage storms via Semantic Caching. I can delegate this ticket directly to Alice Cooper in Desktop Support, persisting the assignment to our SQLite audit log."*

2. **Switch to Tab 2 (Inbox & Delegation Tracker)**:
   > *"When I switch my persona to Alice Cooper, I immediately see the ticket in 'My Assigned Inbox'. When I mark it In Progress or Resolve it with remediation notes, our SQLite event log records the transition, and Sarah's Dispatcher feed receives a live real-time update."*

3. **Switch to Tab 3 (Process Mining & ITIL Audit)**:
   > *"To uncover operational gaps, Tab 3 runs process mining using pm4py over our event logs. Beyond basic DFGs, we run Inductive Petri Net discovery and Token-Based Replay to compute process fitness and precision, catching exact ITIL protocol violations like unauthorized bypasses."*

4. **Switch to Tab 4 (SharePoint Governance)**:
   > *"In Tab 4, those quantitative process mining metrics are synthesized into structural proposals synchronized to SharePoint via Microsoft Graph API, with interactive status tracking and executive audit reports."*

5. **Switch to Tab 5 (Simulation & Kingman's Law)**:
   > *"Finally, in Tab 5, our Monte Carlo simulation proves a 99% MTTA reduction and 68% MTTR reduction. We explain this using Kingman's formula for queueing theory: support queues operate near saturation during peak hours ($\rho \approx 0.94$). Shaving 38% of tier-1 tickets drops utilization to 0.58, preventing hyper-exponential queue backlog and cutting human queue delay by over 91%."*
