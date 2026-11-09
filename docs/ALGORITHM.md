# Algorithm

Research on YouTube Shorts and TikTok distribution signals. **Dated** — this document must be reviewed every quarter.

**Research date:** 9 November 2026
**Next review:** February 2027

---

## 1. Confidence levels

Not every claim below is equal. Each section names its level:

- **High** — stated by the platform itself through documentation or its representatives.
- **Medium** — third-party analysis of large aggregate data.
- **Low** — numbers from vendors selling engagement services. Direction only, not law.

Mixing the three without labels is the most common way to make an algorithm document untrustworthy.

---

## 2. YouTube Shorts signals — high confidence

From YouTube documentation and statements by Todd Sherman (product lead, YouTube Shorts).

| Signal | Role | Implication |
|---|---|---|
| **Viewed vs. Swiped Away** | The first and most decisive test | The hook must win in the first frame. No intro. |
| **Average View Duration / % Viewed** | High | The payoff must arrive fast. |
| **Satisfaction** (like, dislike, post-watch survey) | High, explicit | High retention without satisfaction still fails. |
| **Watch history & topic interest** | High | One channel must hold a consistent niche. |
| **Sounds** | Medium | The script must be ready for voice-over or popular audio. |
| Competition & seasonality | Medium | Schedule and topic matter. |

**Not signals** — myths to reject:

- Subscriber count. The feed is designed to surface channels you have not followed.
- Posting frequency. There is no minimum; posting more often only adds chances.
- Cross-posting to TikTok/Instagram/Facebook. It brings outside traffic, but is not counted by the ranking system.
- Hashtag density. Hashtags contribute under 1% of views.

**The "view" definition change (31 March 2025):** every play or replay counts as a view. The big number on the dashboard is reach, not watching. "Engaged views" is the stricter number and the one that counts for monetisation. So 2026 view numbers are not comparable to 2025.

---

## 3. Hook archetypes — medium/low confidence

Data from vendor analysis of ~12,400 TikTok posts. **The vendor sells engagement services — treat it as direction, not truth.**

| Archetype | Median watch time | Median like rate | 2-second retention |
|---|---|---|---|
| Confession | 14.8s | 6.8% | 84% |
| Counter-intuitive claim | 13.1s | 5.4% | 81% |
| Specific number | 12.5s | 4.9% | 79% |
| Mid-action cold open | 11.9s | 4.4% | 77% |
| Generic sales opener | 7.2s | 2.7% | 61% |
| Trend-audio-only | 6.4s | 2.1% | 58% |

Operational findings:

- The first scroll decision happens around **second 2**.
- The first word must be audible **before second 1**.
- Storytelling beats a sales hook by about **1.9×** on like rate.

**How Narathor uses this table:** the top four archetypes are **inspiration**, not mandatory rules. There is no forbidden phrase list. The Critic judges whether the chosen archetype *works on this script*, not whether that archetype is on a list.

The bottom two archetypes are banned not for their names, but for their consequences: both perform worst **and** place the product in clickbait territory. A double ban, not a compromise.

---

## 4. Duration — the finding that changed the design

**An analysis of 35 billion Shorts views** found Shorts perform best at **13 seconds** or **60 seconds** — two peaks, not a flat spectrum.

**Metricool 2026** (799,718 videos, 71,177 accounts) measured average watch time falling to **~16 seconds**, from ~0.79 minutes a year earlier.

Conclusion: **a 30-second montage is a dead zone.** It loses the payoff before the viewer leaves, and is not long enough to build three-act structure.

Narathor's rule:

| Duration | Status | Structure |
|---|---|---|
| 13–20 seconds | **Default** | One thesis, direct hook, payoff before second 16, no acts |
| 60 seconds | Supported | Three acts: claim → evidence/story → consequence |
| 30 seconds | `--experimental` | Comparison tests only, never production |

**Hard rule:** `payoff_at_s < 16` for the 13–20s target. For the 60s target, the first payoff must still appear before second 16, with the main payoff in the second half.

---

## 5. The structural advantage of educational content

Metricool 2026, on the lifespan of a Short:

> A Short does most of its work early. The first day carries a large share of views. The first three days are the strongest window. After that it slows without stopping — YouTube keeps showing the Short to new audiences.
>
> *"one with a solid topic can keep picking up views for months at a quieter pace. That kind of shelf life is rare in short-form video. It rewards Shorts built around topics that still matter after the trend fades."*

Educational content **inherently has a long shelf life**. This is a competitive advantage aligned with the soul, not a compromise against it. It belongs in distribution strategy, not just technical optimisation.

Consequence for the `Critic`: the gate **"worth watching six months from now"** is not idealism. It is a long-term predictor backed by data.

---

## 6. The finding that confirms the soul

YouTube places **Satisfaction** as an explicit signal. Metricool puts it this way:

> *"A Short can hold attention and still leave people feeling like they wasted their time. The system is built to spot the difference."*

YouTube policy (July 2025) also bans monetisation of **mass-produced repetitive** content — identical templates, the same slideshow, repeated voice-over.

**The conclusion that binds this product:** in 2026 the algorithm **punishes** clickbait without payoff and **rewards** real value. Optimising for empty retention is not only unethical — it is no longer effective.

Narathor optimises **satisfaction-weighted retention**. That choice is both morally right and metrically right. If the two ever conflict, this document will say so — but as of November 2026 they align.

---

## 7. Distribution behaviour worth knowing

From Metricool 2026:

- **The Shorts feed accounts for 61.5%** of organic views. Subscribers 11.3%, search 8.8%.
- Small accounts grow fastest. Accounts over 1M subscribers lose 74% of views per Short.
- Best per-post performance at **2–4 posts per week**. Higher volume lowers the per-post number slightly but adds to the total.
- Posting Shorts **does not hurt** long-form. Not posting Shorts actually correlates with below-average long-form views.

Implication for briefs: `sources.channels` should be one niche. Jumping topics splits the audience signal.

---

## 8. Limits of honesty

What must be read before using this document:

1. **The platform does not publish weights.** Every relative number is inference.
2. **TikTok numbers come from an engagement vendor.** Treatment: direction, not target.
3. **All numbers change.** The research date is stated above; quarterly review is mandatory.
4. **Narathor does not promise virality.** What is guaranteed is compliance with known signals.
5. **Correlation is not cause.** Channels that post Shorts have higher long-form views — that could mean Shorts help, or it could mean those channels are simply more active.

A document that hides these limits is more dangerous than no document.

---

## 9. Review rhythm

| Quarter | What is checked |
|---|---|
| Q1 2027 | Has the engaged view definition changed? Has the optimal duration shifted? |
| Q2 2027 | Is the satisfaction signal still explicit? Have AI content policies changed? |
| Q3 2027 | Is the archetype table still relevant, or has the vendor changed methodology? |

A change to this document **does not** change the soul. What changes: rubric weights, duration targets, and the contents of `CRAFT.md`.

---

## Sources

- [vidIQ — How Does the YouTube Shorts Algorithm Work in 2026?](https://vidiq.com/blog/post/youtube-shorts-algorithm/)
- [Metricool — YouTube Shorts Algorithm Explained + Tips to Grow in 2026](https://metricool.com/youtube-shorts-algorithm/)
- [SMMNut — TikTok Hook Strategy 2026 (engagement vendor; direction only)](https://smmnut.com/blog/tiktok-hook-strategy/)
