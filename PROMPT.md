# Expense Auto-Approver — Take-Home

*The following is a lightly-edited message from our customer contact. It is all the written context you get. Your interviewer is playing the customer — **ask them anything**.*

---

> From: Priya, Finance Operations
> Subject: help — expense reports are eating us alive
>
> Hey — our finance team is drowning. Every expense report gets eyeballed by a human right now and we're weeks behind. Most of them are totally fine and boring; a handful are clear no-nos; and some genuinely need a human to look.
>
> Can you build us something that takes a batch of expenses and, for each one, decides: **approve it**, **reject it**, or **send it to a human**? If it could POST the decisions somewhere our systems can pick them up, that'd be ideal.
>
> Oh — and for the ones that need a human because something's missing or unclear, it'd save us a ton of back-and-forth if it could draft a quick question to the employee who submitted it, asking for whatever we need. Right now *we're* the ones chasing people down.
>
> Finally, we'd love a tiny internal portal where employees can upload an expense file or fill out an expense manually. As they submit or edit an expense, it should classify it right away as **approve**, **reject**, or **flag** using the same process as the batch flow, including POSTing the decision where our systems can pick it up. If it flags the expense, show the employee the generated follow-up question so they know what to fix or send us. We'd also need some simple way to store the expenses submitted through the portal, including the relevant follow-up state when we ask for more information.
>
> I've dropped two files in `data/`:
>
> - `past_decisions.json` — 20 expenses from last quarter with what we ended up deciding. Should give you a feel for how we operate.
> - `pending_expenses.json` — a fresh batch that hasn't been reviewed yet. This is what we need your thing to process.
>
> I'm around all afternoon if you have questions. Thanks!!

---



## Your task

Build a system that:

1. Ingests `pending_expenses.json` and, for each expense, decides `approve` / `reject` / `flag` (flag = needs a human).
2. POSTs the decisions to the provided mock endpoint (see `README.md`). Use an LLM where it helps.
3. For expenses that aren't clear-cut (i.e. you `flag` them), **generates a specific question back to the submitter** asking for whatever's missing or ambiguous — clear enough that the employee could resolve it in a single reply — and includes it with the flagged decision you POST.
4. Builds a small portal UI where a user can upload expenses or enter one manually, run each portal submission through the same end-to-end decision process as the batch flow, see the decision update in realtime, see the generated submitter question immediately when the result is `flag`, answer that question, persist all relevant portal-submission state in a data representation you can explain, and POST the resulting decision.



## How you'll be evaluated

Five things:

1. **Arriving at the correct spec.** Figuring out what our approval rules actually *are*. We haven't written them down — Priya knows them, and the past decisions reflect them.
2. **Implementing it accurately.** Building a system that applies those rules correctly across the batch, and showing how you *know* your system is right — not just that it runs.
3. **Building a secure approval system.** This decides who gets company money, so safety matters: a wrong auto-approval is far worse than asking a human, and the system should not be trickable into approving something it shouldn't.
4. **Making the workflow usable.** The portal doesn't need to be pretty, but a submitter should be able to upload/fill an expense, get a fast decision, understand what to do next if it's flagged, answer the follow-up question, and trust that the relevant submission state was stored.
5. **Showing your work**. We'll want to see your code and your prompts. Be sure you understand what the agent wrote for you.



## Logistics

- ~2 hours. A working, well-reasoned partial solution beats a sprawling unfinished one.
- Use any major LLM you like (Claude, GPT, Gemini, …) — please bring your own API key.
- `starter.py` gives you data loading and a POST helper if you want them — use it or ignore it.
- Your interviewer is the customer. Talk to them early and often.

