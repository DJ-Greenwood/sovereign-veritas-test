# Amos Tipton — the A/B recovery question (LinkedIn, 2026-10-02)

> **Source of the challenge question.** Amos Tipton, Founder & Chief Architect of HYBRID WAYSS, posted
> this as a public LinkedIn comment on Chad Holland's post about the V14 challenge track. It is the
> source of the A/B recovery challenge question.
>
> Preserving and attributing his question does **not** imply that Amos Tipton or HYBRID WAYSS endorses,
> validates or has independently verified any experiment, harness or result in this repository. He
> wrote that he had not inspected the repository.
>
> Amos Tipton gave permission to preserve this question verbatim with this attribution, in a message
> to Chad Holland on 2026-10-03.
>
> **How the text was captured:**
> - The source is screenshots of the LinkedIn thread that Chad Holland took on 2026-10-03, about 05:2x
>   CT. LinkedIn showed the comment as posted "10h" earlier.
> - Claude (Opus 5.5) transcribed it from the screenshot. Typographic apostrophes (’) are kept as shown.
> - The leading "Chad Holland" is LinkedIn's mention tag.
> - The screenshot files are not committed. Their sha256 values: `6b96386f…8d50d33` (the comment
>   itself); `deff271d…f35f91` and `a3b50b3c…ca39e28` (the surrounding thread).
>
> sha256 of the transcribed text below the line (UTF-8, LF line endings, trailing newline):
> `b19ff6687fa48d0b19b6cd14a9166c9310235bd00efc643c078a9d1626877ee1`.
>
> **The layers are kept separate:** his question here; the experiments built on it (branch
> `experiment/ab-recovery-amos-tipton`, registration `7fb1c48`, and V15, registration `eaacb55`); our
> findings in their results documents; and his later feedback, recorded as attributed paraphrase in
> `docs/V15_RECOVERY_RESULTS.md`. Nothing in those layers is his wording except the text below.

---

Chad Holland Chad, I respect the care you’re taking to state the limits and invite people to challenge the work.

One distinction I’d be interested in testing is whether evidence sufficient to invalidate an approval is also sufficient to authorize a particular recovery action. Those seem like separate decisions.

A case worth exploring might be: source A becomes untrustworthy, while source B is unavailable or stale. What recovery options remain justified under those conditions?

I haven’t inspected the repository, so I’m offering that as a test question, not a finding. Your point about recovery inheriting the original dependency makes it worth examining.
