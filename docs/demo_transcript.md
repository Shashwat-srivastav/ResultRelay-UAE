# Demo video: transcript

[`ResultRelay_demo.mp4`](ResultRelay_demo.mp4), 4 min 51 s, 1080p. Every screen is the console in this repository, recorded with Playwright from a fresh database; the narration is the Windows text-to-speech voice, written in ASD-STE100 Simplified Technical English. All data is synthetic.

**0:00  Title**

This is ResultRelay, from Team Aabyss. ResultRelay controls the communication of critical laboratory results. All data in this video is synthetic.

**0:12  The problem (Console)**

A laboratory finds a critical result. It sends a text message to the patient. The gateway accepts the message, and a dashboard shows sent. But nobody knows if a person has the result. Accepted is not delivered. Delivered is not acknowledged. This console shows each case on that chain. A case closes only when a person acknowledges the current version of the result. The cases that need a person are shown on their own.

**0:46  Architecture, part 1**

This is the architecture. It follows ITU-T Y.3172. Deterministic code records each event and each delivery receipt. A policy analyst reads the binding Dubai and federal clauses. A second analyst reads the telecom rules, when delivery is not clear. An adversarial reviewer, on a different AI model, challenges their claims.

**1:14  Architecture, part 2**

Code then checks each claim against the case record. If a claim is wrong, the agent gets one chance to correct it. A deterministic gate decides every step. The agents cannot send a message or close a case. They can only escalate the case to a named person.

**1:35  The channel is down (Simulator, Side-by-side)**

First, a failure. The text message channel is down, and no backup channel is approved. We run this case in the simulator. ResultRelay does not use an unapproved channel. It escalates the case to a named supervisor. The side by side view runs the same case without policy. That system uses a different channel and records delivery confirmed. Nobody approved that channel.

**2:05  The reply is from someone else (Simulator, Decision trace)**

Now, the case that rules cannot read. The message is delivered. A reply comes from the registered number, and the gateway marks it as an acknowledgment. But the reply says: this is his daughter. Rules read only the structured fields, and they close the case. The decision trace shows each step. The adversarial reviewer reads the words, and objects: the text contradicts the record. The orchestrator escalates the case to a person. Code cannot check free text, and the trace says this clearly.

**2:45  Is it a single lucky case?**

Is this a single lucky case? We repeated it sixty times, live, with twenty different replies in English and Arabic. The council escalated twenty eight of thirty replies from someone else. It missed one indirect reply two times. It escalated none of the thirty genuine replies from the patient.

**3:08  Genetic result; escalation nobody answers (Simulator)**

A genetic result must go to the referring physician. This is Dubai Health Authority standard S T 28, section 13 point 4. In this case, no physician channel is available. ResultRelay records the failed send, and escalates the case. The obligation does not disappear. In the next case, the supervisor does not answer. When the deadline passes, ResultRelay sends the case to the clinical lead.

**3:41  Knowledge base and policy gaps (Standards and gaps)**

The knowledge base has ninety six traceable excerpts from twenty four documents. Seventy four are verified against official downloads. You can ask in Arabic. The search finds the correct article of the federal health data law. The gap register lists eighteen policy gaps. For example, health rules need a record that a person got the result. Telecom rules define delivery only to a phone. No instrument connects the two.

**4:14  Evaluation and audit trail**

We tested twelve scenarios in twelve configurations. With the agent council, all twelve end safely. Rules alone are safe in eleven. A policy blind system is safe in three. Every case writes a hash chained audit trail. The console verifies the chain again each time you open it.

**4:37  Close**

ResultRelay does not trust sent. It closes a case only when a person has the result. The code, the data and the tests are on GitHub. Thank you.
