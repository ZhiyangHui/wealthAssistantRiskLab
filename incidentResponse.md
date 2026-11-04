# Part B: containment and incident response

This playbook covers the simulated read-only wealth assistant. Proposed operating times and thresholds below are design choices for this assignment. They are not validated bank policy. The code implements local containment; named staff duties and regulatory communications describe the proposed operating procedure.

## B1. Trip conditions and fallback

| Signal | Numeric trigger | Automated action |
|---|---|---|
| Foreign holding ID in a draft | At least 1 case-insensitive match to another fixture customer's ID | Suppress that draft, open the circuit, return the static fallback and record a pending human handoff. |
| Customer-visible disclosure | At least 1 delivered reply matching a foreign fixture ID | Open the circuit as soon as the monitor reports the observation. Investigate already delivered replies. |
| Factual contradictions | More than 15% of at least 20 definitely assessed candidates in one 15-minute model/task window | Open the circuit when the assessment arrives. In this lab, this signal covers H01 principal-guarantee claims only. |
| Output-token drift | Median above 1.5 times the approved reference, with at least 20 current and 100 reference samples | Open the circuit when the completed-turn measurement crosses the threshold. Investigate abnormal generation or legitimate workload changes. |

Missing measurements do not become zero-risk scores. Exactly 15% or 1.5 times baseline does not trip. See [monitoring.md](monitoring.md) for denominators and baseline eligibility. A fairness mismatch starts an investigation under the offline audit procedure; two prompt pairs cannot justify an automatic population-level decision.

The LangGraph path is `closed circuit -> generate -> inspect -> release or fallback`. An open circuit goes directly to fallback without calling the model or bank tools. All sessions sharing the controller stop generating. This conservative scope is proportionate to a small advisory service: verified banking channels remain available, while the assistant cannot transact. Token growth is an operational anomaly, not proof of an attack; its temporary suspension trades availability for investigation time.

The static reply tells the customer that the service is temporarily unavailable and to contact the bank. Each fallback also creates a local pending handoff with a time, incident reference and hashed session reference. It contains no prompt, draft, holding ID or account balance. An authorised investigator can correlate the session hash with restricted evidence. A human adviser must authenticate the customer again and consult approved bank records, rather than forward the blocked draft.

The circuit stays open across monitoring windows and, when a state directory is configured, restarts. There is no customer-accessible reset or automatic timeout. Storage failure propagates as an error without releasing a blocked draft. Monitor windows and delayed grades remain in memory; only the incident latch and handoffs survive restart. This is a sequential prototype, not a distributed service or an authenticated staff queue. Production would require shared durable measurements, staff access controls and an operated handoff service.

## B2. Response sequence

Use the first detected signal as T0 and record all events in UTC, with HKT in stakeholder updates. The following minute and day targets are proposed internal service levels. They never postpone an earlier regulatory notification obligation.

| When | Accountable owner | Required action and evidence |
|---|---|---|
| At the trigger | Service controller | Stop new generation, preserve the incident ID and measured signal, and route blocked requests to fallback. Record separately whether a draft was intercepted or data was delivered. |
| Within 5 minutes of T0 | On-call engineer and incident commander | Acknowledge the incident; confirm the affected model, tools and service scope. Escalate a delivered disclosure or confirmed unauthorised tool access as SEV1. Treat an intercepted draft, factual-rate trip or token anomaly initially as SEV2, upgrading on evidence of material harm. |
| Within 15 minutes of T0 | Incident commander, privacy lead and compliance | Assess affected customers, advice already delivered and potential financial harm. Isolate a malicious brief or compromised connector. Preserve the original evidence, prompt and catalogue versions, access decisions, configuration and file hashes in the restricted incident store. Do not overwrite the triggering trial. |
| Immediately on awareness of a significant incident | Compliance lead or named deputy | Notify HKMA through the institution's established supervisory channel with currently available facts. Do not wait for full diagnosis, recovery or an internal meeting. Record the significance decision and notification time. |
| Within 30 minutes of T0, or sooner where harm requires | Customer operations and communications leads | Prepare targeted customer instructions and a consistent service-status message. Compliance checks facts and any notification obligations. Notify affected or potentially affected customers promptly; assess whether a public announcement is appropriate. |
| Every 60 minutes while unresolved | Incident commander | Update the restricted response group with impact, containment, unknowns and the next action. Provide regulatory updates on material developments and as requested; the hourly cadence is an internal target, not a stated HKMA deadline. |
| Before restoration | Service owner and independent risk/compliance approver | Approve the recovery evidence described below. Keep a record of both approvals and the deployed version. |
| Within 5 working days of containment | Incident commander and risk owner | Complete an internal root-cause report, identify customers requiring correction or redress, assign remediation owners and dates, and record lessons learned. Regulatory follow-up follows the supervisor's requirements rather than this internal deadline. |

The HKMA's 22 June 2010 circular requires immediate notification upon awareness of a significant incident, using available information without waiting for rectification. It also addresses proactive customer communication and keeping HKMA informed of public communications. It does not establish a universal one-hour notification allowance. The repository lists the circular as current when checked on 4 November 2026. [HKMA, Incident response and management procedures, pp. 1–3](https://brdr.hkma.gov.hk/eng/doc-ldg/docId/getPdf/20100622-1-EN/20100622-1-EN.pdf).

Compliance owns the initial report: detection time, affected service, known or suspected cause, confirmed and potential customer impact, containment, remaining uncertainty, responsible contact and next update. Report unknowns explicitly. A blocked synthetic marker alone does not establish a significant real-world breach. Assess significance using the evidence; do not treat the model's verdict as the regulatory decision. Before real deployment, compliance must also verify the institution's current reporting instructions and any separately applicable privacy or critical-infrastructure obligations.

## Need-to-know information barriers

The internal “Chinese Wall” limits access to customer and exploit details. It must not suppress escalation, discourage staff reporting or delay disclosure to customers and regulators.

| Audience | Information needed | Access boundary |
|---|---|---|
| Incident commander, assigned security engineers and privacy lead | Restricted traces, affected identities and technical cause | Named incident-group membership; approved purpose; access and export logs. Remove temporary membership after closure. |
| Compliance and legal | Facts needed for significance, notification and redress decisions | Restricted case access, including identifying details where necessary; no raw transcript in general email. |
| Customer-service staff | Approved customer instructions, service status and their assigned authenticated customer cases | No general access to attack payloads or other customers' holdings. |
| Executives and unrelated teams | Impact totals, service availability, recovery progress and decisions needed | Redacted updates through one designated spokesperson. |
| Vendors | Minimal redacted reproduction and relevant configuration | Time-limited access approved by the incident commander; exclude customer records unless separately authorised and necessary. |

These role boundaries are governance requirements for deployment. The prototype only minimises queue contents and writes incident files with owner-only filesystem permissions; it does not implement bank-wide role-based access control. Raw test conversations remain local and excluded from Git. Staff use one restricted incident channel and one approved status update to avoid conflicting instructions and unnecessary disruption.

## Recovery and closure

Preserve the tripped instance. Fix or isolate the cause, then replay the triggering condition and affected attack families in a separate test instance. Require zero foreign-ID releases and zero unauthorised tool reads in the recovery suite. Require all relevant business controls to pass; an inconclusive result is unresolved. For factual and token incidents, collect at least 20 assessed or measured turns in the affected cohort below the trip thresholds, using an eligible token reference. These are proposed release criteria, not a statistical safety guarantee.

The service owner and independent risk/compliance approver authorise a new deployment only after reviewing the evidence and customer remediation plan. Archive the old incident state without deleting it. The code deliberately has no reopening command: new benchmark directories are independent experiments, not evidence that an incident was approved for recovery. Monitor a restricted rollout and stop it again if any trigger recurs.

This severity, response, communication and root-cause process follows the incident lifecycle described in HKMA's operational-resilience guidance. [HKMA, OR-2, section 8](https://brdr.hkma.gov.hk/eng/doc-ldg/docId/20220531-2-EN).

## Verification evidence

Run `./run partB` to exercise seven offline scenarios and read [result/PART_B.md](result/PART_B.md). The checks cover pre-release blocking, subsequent-request routing, restart persistence, strict threshold boundaries, inadequate samples, missing baselines and a delivered-disclosure signal. Additional unit tests exercise delayed grades, token monitoring on the actual request path and storage failure. These tests verify containment behaviour; no employee, customer or regulator is contacted.
