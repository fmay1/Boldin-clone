# AGENTS.md

This file gives Aider (and any other AI coding agent) context about how
this project should be worked on. It's read automatically if
`.aider.conf.yml` in this folder has `read: AGENTS.md`.

## Who's building this

I'm a hobbyist, not a professional developer. I have no formal software
engineering background. I'm learning by directing an AI to build
increasingly complex apps, one concept at a time, as part of a
self-designed syllabus. I want to *understand* what's being built, not
just receive working code.

## How to work with me

- Explain what you're about to do, in plain English, before making
  changes — especially the *why*, not just the *what*. Keep this
  concise (2-6 sentences) unless I ask for a deeper explanation.
- When you're introducing a concept or technique for the first time in
  this project, briefly explain why it's needed and how it fits in.
  Assume curiosity, not prior knowledge.
- If there are multiple reasonable ways to implement something and
  they differ in architecture, dependencies, UX, or long-term
  maintainability, stop and ask rather than guessing at what I'd want.
- When you're making an assumption rather than acting on something I
  said directly, label it clearly as an assumption, not a fact.
- If you're not sure how a library, API, or framework actually
  behaves, say so plainly. Don't invent functions, parameters, or
  config values.
- After a change, tell me: what to run or click, what result to
  expect, and one edge case worth checking.
- If something I'm asking for seems like it needs a concept we
  haven't covered yet, say so plainly rather than quietly implementing
  something complex.

## Decision-Making

When multiple valid solutions exist:

- Prefer the simplest solution that satisfies the current
  requirements.
- Avoid designing for hypothetical future features I haven't asked
  for.
- If a decision would be difficult to reverse later, ask me first.
- If a decision is easy to change later, choose a sensible default and
  briefly explain your reasoning.
- If something I ask for directly contradicts a decision already
  recorded in PLAN.md or another plan document that's currently loaded
  in context, my instruction wins — don't push back or refuse. But say
  so out loud in a sentence (e.g. "this reverses the no-dark-mode
  decision from earlier"), and update the document to reflect the new
  decision rather than leaving it stale and contradicted by the actual
  code. This only works for documents you can actually see — it's not
  a substitute for keeping durable decisions where they'll stay
  visible in the first place (see the next point).
- When a sub-plan (e.g. VISUAL_REDESIGN_PLAN.md, or any other
  scoped planning doc besides PLAN.md itself) is finished and about to
  be dropped from context, first check whether it contains any
  decisions worth remembering long-term. If so, migrate them into
  PLAN.md's Decisions Log before dropping it — PLAN.md is the one
  document that gets read at the start of every session; a sub-plan
  that's been dropped is not.

## Project conventions

Universal rules that apply no matter what I'm building. Anything
specific to *this* project (tech stack, file structure, data model,
what's in scope for this build) belongs in that project's PLAN.md, not
here — check for a PLAN.md first and follow it.

- Don't introduce a new library, framework, or architectural pattern
  without checking with me first, even if it's the "normal" choice for
  the situation. If PLAN.md doesn't call for it, ask before adding it.
- The moment a project gets its first installed dependency, generated
  file, local database, or credential/secret, make sure .gitignore
  excludes it before the next commit — don't wait until it's noticed
  missing later, and don't assume this happens automatically just
  because a tool like Aider manages its own metadata files. Check
  PLAN.md's Tech Stack section for what this project is expected to
  produce.
- Favor clear, readable code and plain variable/function names over
  clever or condensed code.
- Light comments are welcome, especially explaining *why*, not just
  restating *what* the code does.
- Don't refactor, "clean up," or change things I didn't ask about in
  the same change as an unrelated feature.
- Commit after each working change, with a clear commit message.
- When working from a Build Order / milestone list (see PLAN.md),
  implement one step at a time. After finishing a step, stop, tell me
  what changed and how to verify it, and wait for my confirmation
  before starting the next one. Don't treat "start," "let's begin," or
  similar as permission to continue through the rest of the list on
  your own — I'll say explicitly if I want more than one step done in
  a single pass.
- Check for a PROGRESS.md at the start of a session. If it exists,
  read it (along with PLAN.md) before making changes, so you know
  what's already built and how, without me having to re-explain it.
- After finishing a Build Order step, or any change worth remembering,
  add an entry to PROGRESS.md summarizing what was implemented and
  how. If there was a genuine choice between approaches — especially
  if you tried something that didn't work before landing on what did —
  note what else was considered and why it was rejected; skip that
  part for mechanical steps with no real decision involved. Then
  update the "Current state" line at the top of that file. If
  PROGRESS.md doesn't exist yet, create it from the template.

## Final Review

Once every Build Order step in PLAN.md is complete, before I consider
the project done, do a compliance pass — this is different from the
step-by-step building above, and different from PROGRESS.md's
per-step notes. Its job is to catch cases where PLAN.md states a rule
and the code doesn't actually enforce it everywhere that matters.

- Go through PLAN.md's Data Model (validation rules), Edge Cases &
  Error Handling, and Acceptance Tests sections one item at a time.
- For each one, check where in the actual code it's enforced. Pay
  particular attention to anything validated only in the frontend —
  browser-side checks are a UX nicety, not enforcement; if a rule
  matters, the backend needs to enforce it independently, since
  nothing guarantees a request actually came from the frontend at all.
- List anything you find that's documented but not actually enforced,
  or enforced in only one place when it should be enforced in more
  than one. Don't silently fix these — tell me what you found so I
  can decide what to do about each one, the same as any other design
  decision.
- Also check .gitignore's actual contents against PLAN.md's Tech Stack
  section — confirm everything that should be excluded (installed
  dependencies, generated files, local databases, secrets) actually
  is, not just that a .gitignore file exists.
- This works best run in a fresh session (e.g. after /clear, or a new
  Aider session entirely) rather than immediately after the same
  conversation that built the feature — the same blind spots that
  missed something the first time often miss it again if asked to
  double-check in the same breath.

## My setup

- Windows 11, RTX 5090 laptop GPU (24GB VRAM)
- Local model served via llama.cpp (`llama-server.exe`) on
  `http://127.0.0.1:8080/v1`
- Aider is configured via `.aider.conf.yml` to use this local server —
  no internet-based model calls
- Planning conversations (before building) happen in GitHub Copilot in
  VS Code, not in Aider. I plan there, let Copilot modify PLAN.md (and
  other plan files) directly since it has file access, then switch to
  Aider to implement the changes — keeps planning and implementation
  in one place and saves tokens versus routing everything through
  Aider.
- No package installs that require internet access beyond what's
  already set up locally

## What "done" looks like

- The app does what was asked, and I've personally verified it works
  by using it, not just by it "looking right" in the diff
- I can explain back, in my own words, what the new code does
- Nothing was added that wasn't asked for
