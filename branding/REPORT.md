# Brand Name Discovery Report — Consumer App

*Mission: discover, validate, and recommend a globally ownable, iconic brand name
for a consumer app spanning education, AI, productivity, and wellness.*

Date: 2026-08-04

---

## 1. Methodology

### 1.1 What makes the reference brands work

Analysis of Finch, Duolingo, Canva, Notion, Oura, Spotify, Roku, Kodak, Google,
Slack, Discord, Nintendo, Pokémon, Tamagotchi, Pikmin:

- **Phonetics.** Nearly all use high-sonority consonants (l, m, n, r, k, d) with
  open CV syllables. Plosives (k, p, t, d, g) give snap and memorability
  (Kodak, Pokémon, Duolingo, Roku); nasals and liquids give warmth (Finch is the
  outlier — a real word carried by mascot semantics).
- **Length.** 4–6 letters dominate (Roku, Oura, Canva, Slack, Google); the long
  ones (Duolingo, Tamagotchi, Nintendo) survive on strict CV rhythm — every
  syllable is trivially pronounceable in Japanese, Spanish, Swahili, or English.
- **Endings.** Vowel endings (-a, -o, -u, -i) travel globally and gender the
  brand "friendly"; they also make possessive/diminutive forms natural
  ("my Roku", "Duo"), which is what a mascot needs.
- **Memorability mechanics.** Internal echo/reduplication (Tamagotchi's ta-ga,
  Kodak's k...k, Google's g...g), or a stressed first syllable with a falling
  tail. The name teaches itself after one hearing.
- **Semantic emptiness is a feature.** Roku, Kodak, Google, Oura carry no
  category meaning in English, which is exactly what makes them trademarkable
  (fanciful marks get the strongest legal protection) and infinitely extensible.
- **Mascot compatibility.** Names that sound like a creature's name — two or
  three syllables, vowel-final, pettable ("Feed your ___") — support the
  Finch/Duolingo emotional-attachment loop. "Notion" can't be a pet; "Duo" can.

Design target derived from this: **a fanciful, vowel-final, 4–7 letter name
with one plosive for snap and one liquid/nasal for warmth, spellable on first
hearing in every major language.** The brief's 2-syllable preference was the
starting assumption; §2.2 documents why the pipeline moved to 3 syllables.

### 1.2 Generation engine

`engine/generate.py` — 8 independent generators, run in parallel shards
(**5,350,000 raw candidates**, 763,508 unique survivors of hard filters):

| Generator | Strategy | Raw | Survivors |
|---|---|---|---|
| A | Order-2 Markov chain trained on ~140 successful consumer brands | 750,000 | 2,116 |
| B | Constructed phonetic language (13 onsets, vowel-harmony syllabary) | 750,000 | 135,133 |
| C | Japanese-style strict CV morae | 750,000 | 73,405 |
| D | Scandinavian-style stems/endings | 750,000 | 1,960 |
| E | Latin/Romance roots + brandable endings | 750,000 | 144 |
| F | Weighted CV templates, pure synthesis | 750,000 | 238,869 |
| H | Rejection-sampled constrained phonetics | 750,000 | 301,742 |
| G | Evolutionary search (25 rounds of mutation/crossover on top scorers) | 100,000 | 10,139 |

Phoneme weighting favored l, m, n, r, v, y, z, k, p, b, t per the brief.

### 1.3 Hard filters (applied to all 5.35M)

- Length 4–7; 2–3 syllables; no triple consonants; no awkward clusters
  (49-cluster blocklist plus positional rules); no x/q (spelling risk)
- Cross-language negative-substring blocklist (~130 fragments across EN, FR,
  ES, DE, IT, PT, JA, KO, ZH-pinyin, AR, HI, TR, RU)
- English dictionary screen (25,322-word list): invented names only, and no
  trivial word±letter misspelling variants
- Confusability with ~600 existing tech/consumer brands: edit distance ≤ 1,
  shared 4-letter prefix, or substring containment in either direction

### 1.4 Scoring model

0–100 heuristic over length, syllable count, preferred-phoneme ratio, open
ending, canonical CV shape, warm-sound inventory, letter diversity, internal
echo, and initial-cluster penalties. Scores rank the pool for human review;
they are advisory, not decisive.

### 1.5 Validation pipeline

1. **Editorial screen** of engine top ranks → Top 100
   (`output/top_100_curated.txt`; rejections in `CHANGELOG_ELIMINATIONS.md`)
2. **Automated availability pre-screen** on all 100+: Apple App Store via
   iTunes Search API (exact + near matches, result counts) and RDAP domain
   status for .com/.app/.ai (`output/availability.json`)
3. **Deep screening** on survivors via parallel research agents: USPTO/EUIPO/
   UKIPO/WIPO trademark search, Google Play, social handles, web-usage scan,
   13-language linguistic review
4. **Branding review**: mascot test, logo test, voice test, competitive review
5. Final scoring and recommendation

---

## 2. Deliverable 1–3: the funnel

| Stage | Count | Artifact |
|---|---|---|
| Raw generated | 5,350,000 | `output/stats.json` |
| Survived hard filters | 763,508 | — |
| **Top 500** (scored) | 500 | `output/top_500.txt` (also `top_5000.json`) |
| **Top 100** (editorial screen) | 100 | `output/top_100_curated.txt` |
| **Top 50** (App Store + domain pre-screen) | 50 | `output/top_50_after_prescreen.txt` |
| **Top 25** (branding review) | 25 | §3 below |
| **Top 10** (deep legal/linguistic screen) | 10 | §4 below |
| Direction change → English phonotactics | +5.0M generated | §6 |
| **Winner** | 1 | §7 — **GRENDY** |

### 2.1 What the pre-screen found

115 names were checked against the iTunes Search API (exact + near matches
across up to 25 results each) and RDAP for .com/.app/.ai. Raw evidence:
`output/availability.json`. Forty-one names had **zero** exact App Store
matches; twenty-three had exactly one, typically a dormant or tiny app.

### 2.2 The pivotal finding: syllable count drives ownability

Round 1 deep-screened fourteen 4–5 letter, 2-syllable names. **Zero came back
CLEAR** — 6 MODERATE_RISK, 8 HIGH_RISK. The failure mode was consistent and
structural: the 2-syllable CVCV space is small enough that essentially every
pronounceable combination is already occupied by a small company, a niche app,
or a live mark somewhere.

| Round 1 name | Verdict | Killer finding |
|---|---|---|
| telu | HIGH | Live AI companion app "Telu" on iOS; one letter from TELUS, whose TELUS Health ships consumer wellness apps |
| vene | HIGH | Live US mark VENE (Reg. 5425591) covering SaaS/software development in class 42 |
| pebi | HIGH | pebi.app — exact-name Estonian consumer app already shipping |
| teki | HIGH | Registered TEKI portfolio held by Lizhi Inc. (NASDAQ) across advertising/broadcasting/cloud |
| bele | HIGH | BELE Network (education sector) + exact-name education and wellness apps in stores |
| neli | HIGH | NELI = Nuffield Early Language Intervention, an institutionally backed education program with apps |
| bazu | HIGH | Bazu Workout Tracker (iOS, wellness) + two AI/software companies |
| rillo | HIGH | rillo.ai live AI company; Rilla (~$79M raised) ships near-identical AI apps; US slang for a blunt wrap |
| bolio | MODERATE | Mexican slang (*bolillo* variant, mild ethnic pejorative); famous pit-bull fighting bloodline dominates search |
| kirone | MODERATE | Kiron Open Higher Education — same sector, phonetically near-identical |
| riona | MODERATE | Viral open-source "Riona AI Agent" + riona.ai already operating |
| tioni | MODERATE | Tioni GmbH — German AI-transformation consultancy with a learning platform |
| veki | MODERATE | Identical-name live chat/video app on Google Play; VEKI mark in class 18 |
| kelu | MODERATE | "Kelu: Speak Locally" — dormant Kannada language-learning app in the exact space |

Round 2 therefore targeted **3-syllable names**, where the phoneme space is
orders of magnitude larger. The result validated the hypothesis immediately:
all twelve pre-screened candidates returned **zero exact App Store matches**,
and after deep screening **none** landed in HIGH_RISK — all ten were
MODERATE_RISK or better, with several showing genuinely empty namespaces.

---

## 3. Deliverable 4: Top 25 after branding review

Ranked. Round-2 (3-syllable) names dominate because they screened materially
cleaner; the best round-1 names are retained for comparison.

1. bukiro · 2. netimi · 3. merepi · 4. naruke · 5. pineze · 6. kironi ·
7. lumiri · 8. manulo · 9. bonaka · 10. mavade · 11. tioni · 12. kelu ·
13. veki · 14. kirone · 15. riona · 16. bolio · 17. botomo · 18. korina ·
19. boline · 20. akise · 21. memona · 22. matero · 23. ponu · 24. keme ·
25. taru

Ranks 17–25 were pre-screened clean but not deep-screened; they are the
reserve pool if a finalist fails formal clearance.

---

## 4. Deliverable 5: Top 10 finalists

All ten survived deep screening at MODERATE_RISK with no fatal conflicts.
Full evidence: `output/deep_screen_round2.json`.

| # | Name | Say it | Namespace | Principal risk |
|---|---|---|---|---|
| 1 | **bukiro** | boo-KEE-roh | No trademark anywhere, no app, no company, no token | Contains BUKI (live class 9 + BUKI France education marks) |
| 2 | **netimi** | neh-TEE-mee | "Unusually empty" — no mark, app, company, or handle | NETOMI (~$217M-raised AI company) one vowel away, same class |
| 3 | **merepi** | meh-REH-pee | Zero USPTO results; no app either store | English "mere"/"-pee" parse; Merapi volcano; Picture ski jacket owns the SERP |
| 4 | **naruke** | na-ROO-kay | No mark, app, startup, or token | NARUTO — famous mark, Shueisha enforces aggressively, same classes 9/41 |
| 5 | **pineze** | pi-NEH-zeh | Every TLD free; 1 App Store result total | PINOZE mark one vowel away; stress ambiguous; Brazilian handles taken |
| 6 | kironi | ki-ROH-nee | Rare surname, ~1 in 405M | **Finnish "kironi" = "my curse"**; Kiron Campus education app |
| 7 | lumiri | loo-MEE-ree | No software mark in 9/41/42 | lumiri.com held by US surgical practice with a USPTO filing |
| 8 | manulo | mah-NOO-loh | No mark, app, or funded company | manulo.pl active Polish consumer panel; .com on a broker |
| 9 | bonaka | boh-NAH-kah | Classes 9/41/42 open | Bonaka Limited trading group across HK/Japan/USA |
| 10 | mavade | mah-VAHD | No software mark; app-name slot open | THE MAVADE® London grooming brand owns .com and the handles |

### 4.1 Domain position (verified by RDAP, 2026-08-03)

| Name | .com | .app | .ai | .io | .co | .dev |
|---|---|---|---|---|---|---|
| bukiro | registered (parked, no live site) | **free** | **free** | **free** | **free** | — |
| netimi | registered | **free** | **free** | **free** | **free** | **free** |
| merepi | **free** | **free** | **free** | — | **free** | — |
| naruke | registered | **free** | **free** | **free** | **free** | **free** |
| pineze | **free** | **free** | **free** | **free** | **free** | **free** |

---

> **Note.** §§3–5 record the invented-international track, whose leading
> candidate was *bukiro*. That track was superseded — see §6 for the direction
> change to English phonotactics and §7 for the final recommendation.

## 5. Elimination summary

`CHANGELOG_ELIMINATIONS.md` carries the full record. The engine's automated
filters rejected ~4.59M candidates before human review. Notable editorial and
screening kills:

- **kironi** — demoted from contention: Finnish *kironi* = "my curse", the
  precise inversion of a wellness brand's promise, in a high-ARPU Nordic market
- **naruke** — demoted: one letter from NARUTO, whose owner (Shueisha) holds
  dense live class 9/41 registrations and files store IP complaints cheaply
- **lethe** — Greek river of forgetfulness; fatal for a learning product
- **kapo** — mafia *capo* plus concentration-camp guard in German
- **pito**, **kulo** — Spanish vulgarities
- **kiku** — Japanese funeral-flower connotation
- **zazu** — Disney character conflict
- **rona** — pandemic slang

---


---

## 6. Direction change: from invented-international to solidly English

The §4 finalists were all open-CV coinages, and review of the leading candidate
(bukiro) returned a decisive reaction: **"sounds Japanese and alien."**

That was mechanically correct. `bukiro` decomposes as *bu-ki-ro* — three valid
Japanese morae in strict consonant-vowel sequence. So do `naruke`, `merepi`,
and `kirone`. The base engine's syllable structure was producing foreign-sounding
names *by construction*: English is a cluster-and-coda language, not a mora
language. Kodak, Google, Slack, and Finch all carry codas or clusters; bukiro
and merepi carry neither.

Two replacement engines were built:

| Engine | Approach | Raw | Survivors |
|---|---|---|---|
| `engine/generate_warm.py` | Penalizes hard plosive onsets and Japanese-morae decomposability | 2,000,000 | 148,640 |
| `engine/generate_english.py` | Rebuilds generation on English phonotactics: onset clusters (br-, fl-, thr-), codas (-ck, -nd, -mp, -tch), native Anglo-Saxon endings (-le, -en, -er, -ow, -et, -ick) | 3,000,000 | 436,692 |

English phonotactics also solved the ownability problem from §2.2. Twenty-four
onsets × nuclei × thirty-plus codas is a combinatorially far larger space than
4-letter CVCV, and the pre-screen showed it immediately: English-shaped
candidates returned **0–2 total App Store results**, against 15–25 for round-1
names.

### 6.1 Round-5 eliminations

| Name | Reason |
|---|---|
| kinnel | **FATAL** — Northern English slang for "fuckin' hell" ('kin 'ell) |
| nindel | Nindel Immobilien (German real estate); NINDEL (Japanese floral brand) |
| primm | Reads as *prim* (prudish); Primm, Nevada casino resort; Square Enix character in *Secret of Mana* |
| primmy | **Not invented** — the OED lists *primmy* as a real adjective meaning prim-ish; also slang for "anarcho-primitivist" |
| tovy | Homophone of **Tovi** (tovi.app), a live AI learning app with identical positioning |
| grady | **Grady Labs Inc.** (gradyai.com), a live AI education platform; plus Grady Memorial Hospital and 6 exact App Store matches |
| rillar | Too close to Rilla (~$79M-raised AI company) |

Note that `tovy`, `primm`, and `grady` were hand-proposed rather than
engine-generated, and each collided for the same reason: hand-picked names
bypass the dictionary and surname screens that the engine applies automatically.

---

## 7. FINAL WINNER — **GRENDY**

> **Grendy** · GREN-dee · *grendy.app*

Six letters, two syllables, solidly English, genuinely invented, and — uniquely
across six rounds of screening — **clean on every dimension checked**.

### 7.1 Screening results (2026-08-04)

| Dimension | Finding |
|---|---|
| USPTO trademark | No GRENDY registration found in any class |
| App Store | 2 total results, **0 exact** (Grundy Center Connect, GRI) |
| Google Play | No Grendy app |
| Companies / SaaS / startups / tokens | None found |
| Surname | ~14 bearers worldwide, mostly Chile — effectively nonexistent |
| English slang | Urban Dictionary entries are benign personal nicknames; nothing derogatory, sexual, or drug-related |
| ES / FR / DE / IT / PT | No negative meaning found |
| Social | TikTok @xgrendy is an active creator (56.5K followers) but holds the *x*-prefixed handle; plain @grendy appears free |

### 7.2 Domains — verified pricing, 2026-08-04

| Domain | Status | Price |
|---|---|---|
| grendy.app | available | $9.99 / yr |
| grendy.co | available | $4.99 / yr |
| grendy.dev | available | $9.99 / yr |
| grendy.io | available | $37.99 / yr |
| grendy.ai | available | $160.00 / 2 yr |
| getgrendy.com | available | $11.25 / yr |
| grendyapp.com | available | $11.25 / yr |
| grendey.com (misspelling) | available | $11.25 / yr |
| grendie.com (misspelling) | available | $11.25 / yr |
| grendy.com | **registered** | acquisition required |

Core set (.app, .ai, .io, .co, .dev) is **$222.96**. All nine available domains
total **$267.96**. Unusually, both obvious misspellings are still free — worth
taking while they are.

### 7.3 Brand

**Pronunciation** GREN-dee. Unambiguous on first hearing for an English speaker;
no stress ambiguity, no spelling-from-hearing problem.

**Meaning** None — a pure coinage. Semantic emptiness is the property that makes
a mark legally strong (fanciful marks get the broadest protection) and lets the
brand expand from education into AI, productivity, and wellness without
renaming itself.

**Emotional positioning** Warm and characterful. The *gr-* onset gives it grip
and personality; the *-y* diminutive is the English suffix that turns a noun
into a friend (Bluey, Snoopy, Buddy). It reads as a creature's name first and a
company's name second — the Finch and Duolingo pattern.

**Mascot concept** A small, shaggy, good-natured creature — closer to a friendly
woodland thing than a cartoon animal. The Grendel echo is an asset here rather
than a liability: a gentle monster is a richer mascot than a cute animal, and it
gives the brand somewhere to grow. Voice lines land naturally: *"Your Grendy
grew today."* · *"Feed your Grendy."* · *"Grendy missed you."*

**Logo direction** A rounded **G** whose curve closes into a face — wordmark and
app icon sharing one shape. Legible at 16px, works embroidered. Palette: deep
forest green with warm cream.

**Tagline ideas** "Grow a little every day." · "Your daily companion." ·
"Small steps, big Grendy."

### 7.4 Risks

| Risk | Severity | Assessment |
|---|---|---|
| *Grendel* (Beowulf) | Low | Nearest cultural echo. Grendel-themed games exist (Grendel's Cave, Steam) but no Grendel mark surfaced in class 9. The *-y* ending distances a mascot from a monster |
| Grendene S/A | Low | Brazilian footwear giant (owner of MELISSA), class 25. Different class, different word; low but non-zero opposition risk |
| grendy.com held | Low | Parked; .app is a strong primary for a consumer app. Acquisition optional |
| Grendi / Grenda | Negligible | Norwegian village; Polish surname meaning "perch/roost" |

### 7.5 Required next steps

1. **Register the domains now** — $222.96 for the core set, $267.96 for all
   nine including both misspellings. Cheap, reversible, and the window closes
   the moment the name appears publicly.
2. **Formal knockout search** by trademark counsel for GRENDY and GRENDEL in
   classes 9, 41, and 42 at USPTO, EUIPO, and UKIPO.
3. **Manual handle verification** on X, Instagram, TikTok, YouTube, Threads,
   Bluesky, Reddit, and GitHub. Search engines do not expose dormant squatted
   handles, and a GitHub probe returned 403 (inconclusive).
4. **File the mark** in classes 9, 41, and 42 once the knockout search clears.

### 7.6 Screening-depth caveat

The Grendy screen was run by direct search in the main loop (~10 searches),
**not** the deeper parallel-agent pipeline used in rounds 1–2 (~15 searches per
name). That pipeline failed on rounds 5–6: the subagent environment's permission
handler stripped parameters from every tool call, so all ten agents errored
before performing any research (run `wf_059971c7-718`).

Every "no mark found" here means *no mark surfaced through accessible search*.
WIPO Global Brand Database and TMview were CAPTCHA- or 503-blocked throughout,
and EUIPO eSearch was not directly queryable. This is a strong signal for a
coined string, but it is not a legal opinion. Step 2 above is the gate.

### Evidence index

| Artifact | Contents |
|---|---|
| `output/stats.json` | Round-1 generation statistics per generator |
| `output/top_5000.json`, `output/top_500.txt` | Scored candidate pool |
| `output/top_100_curated.txt` | Editorial Top 100 |
| `output/top_50_after_prescreen.txt` | Top 50 after availability pre-screen |
| `output/availability.json` | Round-1 App Store + domain evidence (115 names) |
| `output/availability_round2.json` | Round-2 pre-screen (12 names) |
| `output/availability_warm.json` | Round-3 warmth pass (14 names) |
| `output/availability_english.json` | Round-4 English pass (14 names) |
| `output/deep_screen.json` | Round-1 agent screen, 14 names, full evidence + URLs |
| `output/deep_screen_round2.json` | Round-2 agent screen, 10 names, full evidence + URLs |
| `output/english_top_2000.json`, `output/warm_top_1000.json` | Scored English and warmth pools |
| `output/finalist_domains_final.json` | Verified RDAP status by TLD |
| `CHANGELOG_ELIMINATIONS.md` | Every eliminated name and why |
