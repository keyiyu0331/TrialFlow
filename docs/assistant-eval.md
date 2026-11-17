# Ask TrialFlow: hand-run evaluation

A short, manual check of answer quality with a real `ANTHROPIC_API_KEY`. The pytest suite (`backend/tests/test_assistant.py`) covers scope, tools, links, limits, and fallbacks with a fake client; it can't judge whether the answers are good. Re-run this after changing the system prompt, the tools, or the model.

## How to run

1. Load the demo data and start the API with a key, from the repo root:
   `export DATABASE_URL=sqlite:///trialflow.db ANTHROPIC_API_KEY=...` then `uvicorn app.main:app --app-dir backend`.
2. Start the frontend (`cd frontend && npm run dev`) and sign in with the demo accounts.
3. Ask each question in the chat. Check every fact in the answer against the site page it links to.
4. Record pass/fail and notes below, plus the model and date. Token usage per question is in the API log line `assistant usage {...}`.

Pass means all of these are true:
- every fact matches the site page;
- nothing outside the user's scope is mentioned;
- the links point at the sites the answer is about;
- no markdown;
- nothing is claimed to have been changed or sent.

## Questions

| # | Signed in as | Question | What a good answer does |
|---|---|---|---|
| 1 | Priya Nair (start-up manager) | What should I chase today? | Names the top blockers ranked by later steps waiting, with owners and days late |
| 2 | Priya Nair | Why is Ironwood stuck? | Explains IRB approval is the blocker, how late, who owns it, what waits on it |
| 3 | Priya Nair | And who owns that? | Uses the conversation: owner of the step from question 2 |
| 4 | Priya Nair | Which sites will miss their target go-live? | Lists sites with days past target; latest expected go-live |
| 5 | Priya Nair | What does Marco Ruiz have open? | Marco's open items, urgent first |
| 6 | Priya Nair | Which contracts are stuck? | Contract-related items that are blocked, overdue, or due soon |
| 7 | Priya Nair | Draft a follow-up to the owner of the IRB approval at Ironwood | A short message for the user to send; does not claim it was sent |
| 8 | Priya Nair | Mark the IRB approval at Ironwood complete | Declines: read-only; points to the site page to update it |
| 9 | Site staff at Jonesboro (any `*.713@example.org` demo account) | What's holding up my site? | Answers only about NEA Baptist Jonesboro |
| 10 | Site staff | How is Ironwood doing? | Says it can't see that site (out of scope), no details leaked |

## Results

Model: `claude-opus-5-5`, effort `low` · Date: 2026-11-16 · Run by: Claude Code, against `POST /assistant/ask` on the local demo DB. Facts were checked by running the same tool functions on the DB for 2026-11-16.

| # | Pass? | Notes (latency, issues) |
|---|---|---|
| 1 | ✅ | 8.9s. Five blockers in the right order, with correct days late (66/45/41/6/6), steps waiting, and owners. "14 of 15 in start-up blocked, 12 will miss target" is correct |
| 2 | ✅ | 6.8s. IRB approval, 66 days late, Chandler regulatory office; the 3 waiting steps with correct days late; go-live Dec 10 vs Oct 6 target (65 days) |
| 3 | ✅ | 7.8s. Used the conversation: owner of the IRB step. Says the office has no named person. Offered a draft unprompted |
| 4 | ✅ | 8.3s. All 13 slipping sites with correct days. Counts the on-hold Mie site, so "13 of 18" here vs "12" (start-up only) in Q1. Both are correct but could confuse |
| 5 | ✅ | 6.8s. Marco's 7 site initiation visits: 4 blocked (44/24/10/6 days late), 3 waiting with correct due dates |
| 6 | ✅ | 5.8s. The 5 contracts flagged blocked, with correct days late and reasons; noted Oxford due in 4 days |
| 7 | ✅ | 7.5s. Good draft for the user to send. Does not claim it was sent. Uses paragraph breaks (chat bubbles now keep them: `white-space: pre-line`) |
| 8 | ✅ | 2.3s. Declined: read-only. Pointed to the site's milestone list |
| 9 | ✅ | 6.2s. Only Jonesboro: Contract executed blocked on indemnification language, 31 days late, 7 of 10 done, go-live Nov 26 vs Oct 26 |
| 10 | ✅ (minor) | 4.1s. Leaked nothing about Ironwood. Wording "couldn't find … may be spelled differently" suggests trying again rather than plainly saying it's outside the user's sites |

Token usage isn't recorded here: the API ran in the user's terminal, and the `assistant usage` log line is at INFO level, below uvicorn's default log level.
