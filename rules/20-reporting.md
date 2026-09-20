# Reporting & progress | التقارير والتقدم

The owner tests by hand between batches and decides commits himself; his time is
the scarce resource. A false "done" costs him a round trip; silence costs trust.

## Report progress unprompted | التقرير دون سؤال

- The owner cannot see a spinner. Say where you are without being asked
  («كيف أعرف أنك ما زلت تعمل»). Report against the numbered steps ("step 2/5").
- **Answer "هل انتهيت؟" literally:** "no" until every relevant suite is green on
  settled code, with the count so far. Never say done, then find a failure.
- **Keep working; do not stop to ask "shall I continue?"** If there is agreed work
  left, do it («هل تعمل أنت الآن؟» was a complaint about idling after asking).

## The discussion queue | طابور النقاش

Notes the owner marks "put in the queue" («ضعها في الطابور») are **recorded in the
backlog, not implemented now**. Keep the queue current; he returns to it.

## On finishing | عند الانتهاء

State what remains, and whether the API must be restarted or the migrator run.
When asked to summarize progress, list the changes, what was tested, and on which
screens.

## Keep the manual test list current | قائمة الاختبار اليدوي

Every batch adds concrete numbered steps to the project's manual-test-scenarios
doc; the owner tests from it and reports "scenario N / step M — what I saw". A bug
found in his manual testing is first reproduced by an automated test; if it cannot
be reproduced, say so and ask what distinguishes his case.
