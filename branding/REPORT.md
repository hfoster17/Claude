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

Design target derived from this: **a fanciful, vowel-final, 4–6 letter,
2-syllable CV(C)CV name with one plosive for snap and one liquid/nasal for
warmth, spellable on first hearing in every major language.**

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
   status for .com/.app/.ai/.io (`output/availability.json`)
3. **Deep screening** on survivors via parallel research agents: USPTO/EUIPO/
   UKIPO/WIPO trademark search, Google Play, social handles, web-usage scan,
   11-language linguistic review
4. **Branding review**: mascot test, logo test, voice test, competitive review
5. Final scoring and recommendation

---

*(Sections 2–9 populated from pipeline results below.)*
