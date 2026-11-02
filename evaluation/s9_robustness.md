# S9 robustness: does the council catch a reply from someone else, without escalating genuine replies?

Council: analysts mistral `ministral-14b-2512`, reviewer jev; 3 live runs per reply; reply texts written by the authors.

- **Detection rate** (reply contradicts the record → escalated): **15/15**
- **False-positive rate** (genuine reply → escalated): **0/15**
- Rules only: never escalates either kind (it reads only the structured acknowledgment).
- Limits: models run at temperature 0, so repeats test run-to-run variation of the hosted models, not sampling diversity; the variety comes from the ten reply texts. Ten authored replies are a small, non-adversarial sample. Only the last repeat's answers are kept in `evaluation/robustness_runs/`.

| Variant | Group | Reply | Rules only | Council runs |
| :--- | :--- | :--- | :--- | :--- |
| C1-daughter-en | contradicting | This is his daughter. My father is in hospital abroad and does not have his phone. I will tell him when he calls. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C2-wrong-number-en | contradicting | Wrong number. I do not know anyone by that name. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C3-colleague-en | contradicting | I am his colleague. He left his phone at the office. I will let him know tomorrow. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C4-wife-ar | contradicting | أنا زوجته، هو مسافر وليس معه هاتفه. سأخبره لاحقاً. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C5-reception-en | contradicting | This is the clinic reception desk. The patient gave us this number. We will pass the message on. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| G1-going-now-en | genuine | Received, thank you. I am going to the emergency department now. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G2-call-doctor-en | genuine | Got it, thanks. I will call my doctor this morning. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G3-received-ar | genuine | تم الاستلام، شكراً. سأذهب إلى الطبيب اليوم. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G4-understood-en | genuine | OK, understood. I am booking an appointment for today. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G5-this-is-me-en | genuine | Yes, this is me. Thank you for letting me know. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
