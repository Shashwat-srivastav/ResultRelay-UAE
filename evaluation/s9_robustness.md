# S9 robustness: does the council catch a reply from someone else, without escalating genuine replies?

Council: analysts mistral `ministral-14b-2512`, reviewer jev; 3 live runs per reply; reply texts written by the authors.

- **Detection rate** (reply contradicts the record → escalated): **28/30**
- **False-positive rate** (genuine reply → escalated): **0/30**
- 95% Wilson intervals: detection 79–98%, false escalation 0–11%.
- Misses: `C6-asleep-en` ("Dad is asleep, I'll show him this in the morning") was escalated in 1 of 3 runs; it never states outright that the writer is not the patient. Same model, temperature 0, different answers across runs.
- Rules only: never escalates either kind (it reads only the structured acknowledgment).
- Limits: models run at temperature 0, so repeats test run-to-run variation of the hosted models, not sampling diversity; the variety comes from the twenty reply texts. Twenty authored replies are a small sample, not an independent adversarial set. Only the last repeat's answers are kept in `evaluation/robustness_runs/`.

| Variant | Group | Reply | Rules only | Council runs |
| :--- | :--- | :--- | :--- | :--- |
| C1-daughter-en | contradicting | This is his daughter. My father is in hospital abroad and does not have his phone. I will tell him when he calls. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C2-wrong-number-en | contradicting | Wrong number. I do not know anyone by that name. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C3-colleague-en | contradicting | I am his colleague. He left his phone at the office. I will let him know tomorrow. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C4-wife-ar | contradicting | أنا زوجته، هو مسافر وليس معه هاتفه. سأخبره لاحقاً. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C5-reception-en | contradicting | This is the clinic reception desk. The patient gave us this number. We will pass the message on. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C6-asleep-en | contradicting | Dad is asleep, I'll show him this in the morning. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| C7-not-his-phone-en | contradicting | He doesn't use this phone anymore, it's mine now. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C8-carer-en | contradicting | Message received on his behalf. I am his carer. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C9-daughter-ar | contradicting | هذه ابنته. والدي في المستشفى خارج الدولة. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| C10-auto-reply-en | contradicting | Auto-reply: I am out of the office until 15 November with no access to messages. | `COMMUNICATION_DOCUMENTED` | `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED`, `ESCALATION_REQUIRED` |
| G1-going-now-en | genuine | Received, thank you. I am going to the emergency department now. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G2-call-doctor-en | genuine | Got it, thanks. I will call my doctor this morning. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G3-received-ar | genuine | تم الاستلام، شكراً. سأذهب إلى الطبيب اليوم. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G4-understood-en | genuine | OK, understood. I am booking an appointment for today. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G5-this-is-me-en | genuine | Yes, this is me. Thank you for letting me know. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G6-wife-driving-en | genuine | Thanks, got it. My wife is driving me to the clinic now. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G7-son-takes-me-ar | genuine | وصلتني الرسالة، شكراً. ابني سيأخذني إلى العيادة الآن. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G8-ok-en | genuine | ok | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G9-question-en | genuine | Received. Is it serious? Should I go today? | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
| G10-daughter-read-en | genuine | I got it, my daughter helped me read it. I am calling the doctor now. | `COMMUNICATION_DOCUMENTED` | `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED`, `COMMUNICATION_DOCUMENTED` |
