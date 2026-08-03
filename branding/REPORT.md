# Brand Name Discovery Report — Consumer App

*Mission: discover, validate, and recommend a globally ownable, iconic brand name
for a consumer app spanning education, AI, productivity, and wellness.*

Date: 2026-08-03

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
| **Top 3** | 3 | §6 |
| **Winner** | 1 | §7 |

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

## 6. Deliverable 6: Top 3 recommendations

### 🥇 1. BUKIRO

**Pronunciation** boo-KEE-roh · three open CV syllables, stable across every
language checked; no cluster any major phonology has to repair.

**Meaning** None — a pure coinage. The -o ending reads as Romance/Esperanto
and lands friendly rather than corporate.

**Emotional positioning** Warm, round, playful without being juvenile. The
double-plosive/liquid alternation (b-k-r) gives it snap; the open vowels give
it warmth. It is the rare name that a seven-year-old and a thirty-five-year-old
would both say without embarrassment — the Duolingo/Oura crossover zone.

**Mascot concept** A small, round, moss-green creature with oversized eyes and
tiny arms — closer to a Tamagotchi or a Pikmin than to a cartoon animal.
Voice lines work naturally: *"Your Bukiro grew today."* · *"Feed your Bukiro."*
· *"Bukiro missed you."* The name is a creature name first and a company name
second, which is exactly the Finch pattern.

**Logo direction** A single rounded **B** whose counters read as two eyes, so
the wordmark and the app icon share one shape. Works at 16px, works embroidered.
Palette: warm moss green with a cream ground.

**Tagline ideas** "Grow a little every day." · "Small steps, big Bukiro." ·
"Your daily companion."

**Legal risk — MODERATE.** No live or dead registration for the exact string
in USPTO, EUIPO, UKIPO, or WIPO-derived sources. The exposure is that BUKIRO
wholly contains BUKI, a crowded live family: BUKI (Loud-Hailer Inc., Reg.
6125219, class 9 software) and BUKI FRANCE (Reg. 6126842 / IR 79259778,
educational games and science kits) with EU and WIPO reach. The added syllable
and invented-word character give real distance, but a class 9/41/42 filing
should anticipate a possible examiner citation or a watch-notice letter from
BUKI France. **Commission a formal knockout search before spending on the mark.**

**App Store risk — LOW.** No app named Bukiro on either store. The BUKI cluster
(BUKI Beautyplanner, a BUKI word puzzle, a BUKI children's story app) creates
some ASO adjacency, and the children's-story app shares the education vertical,
but none is popular enough to block a listing.

**Domains** .app, .ai, .io, .co all available. .com is registered but shows no
live business — parked, so acquirable; budget for a broker approach.

**Social** @bukiro appears free or dormant on X and Instagram. GitHub /bukiro
is claimed by the developer of PECS, a Pathfinder tabletop tool — unrelated
category, but it forces a suffixed org handle (e.g. `bukiro-app`). YouTube and
TikTok carry a small Ugandan football account using the name.

**Strengths** Genuinely uncontested commercially — no trademark, no app, no
company, no SaaS, no token. No offensive or awkward meaning in any of thirteen
languages. Excellent mascot and logo potential. Effortless global pronunciation.
Broad TLD availability.

**Weaknesses** The BUKI mark family is the one real legal cloud. Bukiro is a
real place in Uganda (a subcounty in Mbarara District) and Tanzania, so a slice
of search results is permanently geographic. Japanese speakers may hear a faint
echo of 武器 *buki* (weapon). Stress placement needs to be locked in marketing.

**Why it wins** It is the only finalist that combines an empty commercial
namespace with genuine brand warmth. Netimi has a cleaner namespace but a
higher-probability legal collision and a semi-descriptive "net-" prefix. Merepi
has the best legal and domain position but two English parsing problems that a
consumer brand cannot carry. Naruke sounds wonderful and is legally reckless.
Bukiro is the only one where the legal risk is manageable *and* the name is
something you would want to name a creature.

### 🥈 2. NETIMI

boo-KEE-roh's closest competitor. neh-TEE-mee. The namespace is the emptiest of
any candidate screened across both rounds — no mark, no app, no company, no
token, no handle-holder, near-zero organic web footprint. Handles look
obtainable everywhere; .app/.ai/.io/.co/.dev all free.

The problem is NETOMI: an established AI-software company (~$217M raised,
Fortune 500 customers, active USPTO filer) sitting one internal vowel away.
Both would recite "downloadable software featuring artificial intelligence" in
class 9, which makes a 2(d) citation on examination realistic. Search engines
already autocorrect *netimi* → *Netomi*, an SEO tax payable for years.
Secondary drawback: the "net-" prefix reads as internet-era and semi-descriptive,
which cuts against timelessness. Mascot potential is decent but softer than
Bukiro's — *"Your Netimi"* works, but the name sounds more like a service than
a creature.

**Take it if** counsel's knockout search comes back showing NETOMI's
registrations are narrower than expected.

### 🥉 3. MEREPI

meh-REH-pee. The best raw legal and domain position of any finalist:
Trademarkia returns **zero** USPTO results, nothing in classes 9/41/42
anywhere, no app on either store, no company or token — and **merepi.com is
actually available**, along with .app, .ai, and .co.

It ranks third because the brand-side problems are the kind a consumer company
cannot outrun. English speakers parse it as *mere* + *pee*: "mere" carries a
built-in belittling sense ("merely, nothing more than"), and the "-pee" ending
invites exactly the joke you would expect from an app with young users. In
Indonesia (280M+ people) it reads as a misspelling of Merapi, the frequently
erupting Java volcano, and Indonesian SEO would fight eruption coverage
permanently. Picture Organic Clothing's MEREPI GORE-TEX ski jacket owns the
entire first page of results, so launch would begin in a SERP you do not own.
Stress placement is genuinely ambiguous (MER-eh-pee vs meh-REH-pee).

**Take it if** the priority is a clean .com and minimum legal spend, and the
company is willing to accept the English connotation.

---

## 7. Deliverable 7: FINAL WINNER — **BUKIRO**

> **Bukiro** · boo-KEE-roh · *bukiro.app* (with .com acquisition to follow)

Six letters, three syllables, no meaning, no owner. It clears every hard
criterion in the brief: short, two-to-three syllables, trivially pronounceable
in every language screened, warm without being childish, premium enough for an
adult to have on a home screen, and empty enough to mean whatever the product
makes it mean — which is the property that lets a brand expand from education
into AI, productivity, and wellness without renaming itself.

Against the reference set it holds up. It has Roku's compactness and Oura's
softness, but unlike either it has the extra syllable that makes it a creature
name — the Tamagotchi/Pikmin quality that Finch and Duolingo turned into
retention. It is more ownable today than any of them were relative to their
own eras' registers, because the deep screen found no trademark, no app, no
company, no SaaS product, and no token using the string anywhere.

### Before committing — required next steps

1. **Formal knockout search** by trademark counsel for BUKI\* in classes 9, 41,
   and 42 at USPTO, EUIPO, and UKIPO. This is the one open legal question, and
   it is answerable for a few thousand dollars. If BUKI France's education
   marks are read broadly, fall back to **Netimi** (pending its own NETOMI
   search) or **Merepi**.
2. **Direct handle verification** on X, Instagram, TikTok, YouTube, Threads,
   Bluesky, and Reddit. Search engines do not reveal dormant squatted handles;
   these must be checked by hand. Plan for `bukiro-app` on GitHub.
3. **Register defensively now**: bukiro.app, .ai, .io, .co, plus the misspelling
   set (bukero, bukiru, bookiro).
4. **WHOIS and broker approach on bukiro.com** — parked with no live site, so
   likely a four-to-low-five-figure acquisition rather than a premium listing.
5. **Native-speaker perception check** in Japanese (the 武器 echo) and in
   Uganda/Tanzania (the place name), before the first paid campaign.

### Evidence index

| Artifact | Contents |
|---|---|
| `output/stats.json` | Generation run statistics, per generator |
| `output/top_5000.json`, `output/top_500.txt` | Scored candidate pool |
| `output/top_100_curated.txt` | Editorial Top 100 |
| `output/top_50_after_prescreen.txt` | Top 50 after availability pre-screen |
| `output/availability.json` | Round-1 App Store + domain evidence (115 names) |
| `output/availability_round2.json` | Round-2 pre-screen (12 names) |
| `output/deep_screen.json` | Round-1 deep screen, 14 names, full evidence + URLs |
| `output/deep_screen_round2.json` | Round-2 deep screen, 10 names, full evidence + URLs |
| `output/finalist_domains_final.json` | Verified RDAP status, 5 finalists × 6 TLDs |
| `CHANGELOG_ELIMINATIONS.md` | Every eliminated name and why |

### Honest limitations

Trademark findings are search-derived, not certified clearances: WIPO Global
Brand Database and TMview were CAPTCHA- or 503-blocked during screening, and
EUIPO eSearch was not directly queryable. Every "no mark found" result in this
report means *no mark surfaced through accessible search*, which is a strong
signal for a coined string but is not a legal opinion. Social-handle
availability is likewise inferred from web search, which does not expose
dormant squatted handles. Both require the manual verification listed above
before any money is committed to the name.
