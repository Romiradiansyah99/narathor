# The Narathor brief

From the product owner, with the content team.

## How content works today

Everyone watches shorts. Attention spans shorten, and most of that time is spent on things that leave nothing behind.

On the other side, there are thousands of hours of serious material already spoken by people worth hearing — on YouTube, in hour-long videos, by people who understand what they are talking about. That material almost never reaches the people who need it most, because its shape does not fit the way people watch today.

The distance between those two realities is the problem we want to solve. Not by making new content that is louder, but by **moving understanding** from where it is spoken to where it is needed.

## What we want

An engine that works on **the video library of one channel** — say 400 videos from a single channel — and produces whole short scripts, ready for production.

The engine must:

1. **Index** each video into meaningful segments, with timestamps.
2. **Combine** segments from **different** videos into one arc that forms a single thesis. Not cutting one moment, but stringing several together.
3. **Write the full script** — hook, sequence of lines, payoff, on-screen text, title, caption — in human language, not a stiff summary.
4. **Keep every fact traceable** to the timestamp where it was said.
5. **Judge its own work** and return what is not good enough, rather than passing it along.

The content direction is not set by the engine. It is set by us through the Narrative Brief, and the engine submits to that brief.

## Rules

- **The soul binds.** `SOUL.md` cannot be changed by brief, config, or flag. Any brief looser than the soul is rejected.
- **Facts must be traceable.** A script may be written in its own words, but every factual claim must carry a timestamp reference that actually exists in the transcript. A claim without a citation → the script is rejected.
- **The hook must be paid.** Whatever the opening promises must appear in the body. No delaying the payoff to hold viewers.
- **A combination of at least two videos.** With only one video it is a clip, not a work.
- **No clickbait, no paywall, no exploiting fear.**
- **No list of forbidden phrases.** Creativity is judged by three signature tests, not by a list of bans. What is forbidden is the intent to deceive, not a choice of words.
- **Content direction is set through `briefs/<id>.yaml`.** No theme, channel, or value may be planted in code.
- **The MVP output is scripts and timestamps.** Rendering video is not part of this build.

## What the team must be able to see

- The list of scripts with their thesis, one line each, ordered by score.
- For every script: which segments were used, from which video, at which second.
- Scripts that were returned, with which gate failed and why.
- Scripts rejected for a soul or citation violation, with the article violated.
- Run status: how many units finished, how many running, how many deferred.
- The evaluation summary: selection precision, citation violation rate, craft gate pass rate.

## Our data

`data/` holds the video library, transcripts, and channel metadata. Read-only. The engine seeds them into its own database and never writes back.

`data/eval/` holds the answer key — human judgement of which moments are worth using. **The agent must not open it.** Tests must not either. It is used only by `narathor eval` to measure, not to learn.

## Not for now

- Web dashboard.
- Video rendering, burned captions, 9:16 cropping.
- Auto-posting to platforms.
- Login and multi-user.
- Guaranteeing virality. What is guaranteed is compliance with known signals, not an outcome.

## How we will know this works

Not from the number of scripts produced. From three things:

1. A script that passes the gates can be read once and understood immediately.
2. Every fact inside it can be traced to the second in the original video.
3. Once produced, viewers stay longer than average — and more importantly, they do not regret watching it.
