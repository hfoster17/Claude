# Elimination Changelog

Every candidate that reached human/agent review and was rejected, with the reason.
(Automated engine filters rejected ~4.56M raw candidates before this stage: length,
syllable count, awkward clusters, spelling-risk letters, dictionary words,
cross-language negative substrings, and confusability with ~600 existing brands
via edit-distance ≤1, shared 4-letter prefixes, and substring containment.)

## Round 1 — editorial screen of engine top ranks (pre-availability)

| Name | Reason rejected |
|---|---|
| mona | Real name (Mona Lisa); not invented; Mona-branded apps exist |
| rona | Pandemic slang ("the rona"); permanently tainted |
| lethe / lethi | Greek river of forgetfulness — fatal meaning for an education/memory brand |
| verona / perona | Real city / Juan Perón association; not invented |
| zazu | The Lion King character — Disney trademark conflict |
| zozo | ZOZOTOWN (major JP fashion brand) + ouija-demon meme association |
| kona | Hawaii region; HP Kona, Kona bikes, Hyundai Kona — crowded |
| kiku | Chrysanthemum in Japanese — funeral flower connotation in Japan |
| nolan | Real given name/surname (Christopher Nolan) |
| pito | Spanish slang for penis — linguistic screen failure |
| kulo | Homophone of Spanish/Italian "culo" (ass) |
| rabo | Portuguese slang (tail/backside); Rabobank |
| kapo | Mafia "capo"; concentration-camp guard term in German — fatal |
| rumi | The poet Rumi; also Rumi trademark usage |
| kiva | Kiva.org (major nonprofit) + Kiva Systems (Amazon Robotics) |
| lomu | Jonah Lomu (rugby icon) |
| yoma | 妖魔 = demon/specter in Japanese |
| topo | Real word ("mole" ES/IT); Topo Chico, Topo Athletic |
| lince | Real word (lynx in Spanish/Italian) |
| rondo | Real word (music form); Rajon Rondo |
| botica | Real word (pharmacy, Spanish) |
| tipo | Real word ("type/guy", Spanish/Italian); Fiat Tipo |
| pavo | Real word (turkey/peacock, Spanish) |
| mori | Latin "to die" (memento mori) — wrong valence for wellness |
| velen | World of Warcraft character |
| zima | Discontinued Coors drink; "winter" in Slavic languages (OK) but brand ghost |
| pete / meri / karo / sela | Read as real given names, not invented brands |
| akiro | Too close to Akira (Otomo) — confusion + cultural weight |
| pokiro / pokise | "Pok-" prefix reads as Pokémon-derivative |
| kodoma | Reads as kodama (Ghibli tree spirit) and half-echoes Kodak |
| picsa / pical | Echo of Picsart / "pical" reads as misspelled "pickle" |
| moni / mone / monin / monese | Money-adjacent; Monese is a real UK fintech |
| notoma / notica / notte / noodo | "Not-"/"no-" negative prefix or Notion echo |
| memie / memoni / memone | Read as "meme" derivatives — dates instantly |
| beedo | Minions "bee-doo" catchphrase (Universal) |
| moomo | Cute but reads babyish; fails "premium enough for adults" |
| goomo | Goomba echo (Nintendo); travel-tech brand Goomo existed |
| zele | Near "zeal/zealous" but reads as misspelling; Zele = Belgian town |
| minly | Suffix "-ly" reads as 2010s SaaS, not timeless |
| piflo / tiflo | "tiflo-" is the international prefix for blindness-related tech (tiflotecnia) |
| banmo / banmin / bance | "Ban" negative prefix in English |
| finte | "Feint/fake" in Italian/Portuguese — negative |
| tance / botomo / migoku / remon | Weak voice-test performers; "remon" reads as misspelled lemon; "migoku" echoes 地獄 (jigoku, hell) |

## Round 2 — automated availability pre-screen (App Store + domains)

115 names checked against the iTunes Search API and RDAP. Raw evidence per name
in `output/availability.json` (round 1) and `output/availability_round2.json`
(round 2). Names with 2+ exact App Store matches were dropped before deep
screening; the survivors form `output/top_50_after_prescreen.txt`.

## Round 3 — deep legal/linguistic screening, batch 1 (2-syllable names)

Fourteen names screened by parallel research agents. Zero CLEAR. Full evidence
with URLs in `output/deep_screen.json`.

| Name | Verdict | Reason |
|---|---|---|
| telu | HIGH_RISK | Live "Telu" AI companion app on iOS; one letter from TELUS (TELUS Health ships wellness apps); "scorpion" in Telugu |
| vene | HIGH_RISK | Live US mark VENE (Reg. 5425591) for SaaS/software development, class 42 — the exact space |
| pebi | HIGH_RISK | pebi.app — exact-name Estonian consumer app shipping; PEBI.AI in the AI space |
| teki | HIGH_RISK | Registered TEKI marks held by Guangzhou Lizhi Network Technology (NASDAQ: LIZI) |
| bele | HIGH_RISK | BELE Network education brand; exact-name education and wellness apps in stores; Beli collision |
| neli | HIGH_RISK | NELI (Nuffield Early Language Intervention) — institutional education program with apps |
| bazu | HIGH_RISK | Bazu Workout Tracker (iOS wellness); BAZU Company (UA) and Bazu Ltd (KE) in software |
| rillo | HIGH_RISK | rillo.ai live AI company; Rilla (~$79M raised) ships near-identical apps; US slang for a blunt wrap |
| bolio | MODERATE, dropped | Mexican slang (*bolillo*); pit-bull fighting bloodline dominates search; Bolio UI React library |
| kirone | MODERATE, dropped | Kiron Open Higher Education — same sector, near-identical phonetics |
| riona | MODERATE, dropped | Viral "Riona AI Agent" OSS project + riona.ai already operating |
| tioni | MODERATE, dropped | Tioni GmbH — German AI-transformation consultancy with a learning platform |
| veki | MODERATE, dropped | Identical-name chat/video app live on Google Play |
| kelu | MODERATE, dropped | "Kelu: Speak Locally" — Kannada language-learning app in the exact space |

## Round 4 — deep screening, batch 2 (3-syllable names)

Ten names screened. No HIGH_RISK results — the syllable-count hypothesis held.
Full evidence in `output/deep_screen_round2.json`. Six eliminated:

| Name | Verdict | Reason eliminated |
|---|---|---|
| kironi | MODERATE | Finnish *kironi* = "my curse" — inverts a wellness brand's promise; Kiron Campus education app one letter away |
| lumiri | MODERATE | lumiri.com held by a US surgical practice with an exact-match USPTO filing (Ser. 88929651); splits branded search permanently |
| manulo | MODERATE | manulo.pl — active Polish consumer research-panel brand with EU prior-use claim; .com held by a broker |
| bonaka | MODERATE | Bonaka Limited trading group (HK/Japan/USA) with a 2006 USPTO registration |
| mavade | MODERATE | THE MAVADE® London grooming brand owns mavade.com, @themavade on Instagram and TikTok, and a live UK holding company |
| pineze | MODERATE | PINOZE mark one vowel away; handles taken by Brazilian namesakes; stress ambiguous (PIE-neez vs pi-NEH-zeh) |
| naruke | MODERATE, 4th | One letter from NARUTO — Shueisha holds dense live class 9/41 marks and enforces aggressively via store IP complaints |
| merepi | MODERATE, 3rd | Best legal/domain position but English parses as "mere"+"pee"; reads as Merapi volcano in Indonesia; Picture Organic ski jacket owns the SERP |
| netimi | MODERATE, 2nd | NETOMI (~$217M-raised AI company) one internal vowel away in the same class; "net-" prefix reads semi-descriptive |
| **bukiro** | **MODERATE — WINNER** | No trademark, app, company, SaaS, or token anywhere; only cloud is the BUKI mark family |

## Round 5 — English-phonotactics pass (direction change)

Feedback on the round-4 winner (bukiro): "sounds Japanese and alien." Diagnosis
confirmed mechanically — bukiro decomposes as *bu-ki-ro*, three valid Japanese
morae in strict CV sequence. So do naruke, merepi, and kirone. The base engine's
open-CV structure was producing foreign-sounding names by construction.

Two new engines were built:

- `engine/generate_warm.py` — penalizes hard plosive onsets and Japanese-morae
  decomposability (2,000,000 raw → 148,640 survivors). Superseded by:
- `engine/generate_english.py` — rebuilds generation on English phonotactics:
  onset clusters (br-, fl-, thr-), codas (-ck, -nd, -mp, -tch), and native
  Anglo-Saxon endings (-le, -en, -er, -ow, -et, -ick). 3,000,000 raw → 436,692
  survivors. Also expands the namespace far beyond CVCV: these names return
  0–2 total App Store results vs. 15–25 for round-1 names.

### Eliminations

| Name | Reason |
|---|---|
| kinnel | **FATAL** — Northern English slang contraction of "fuckin' hell" ('kin 'ell). Confirmed in Green's Dictionary of Slang and Urban Dictionary |
| nindel | Existing brands: Nindel Immobilien (German real estate) and NINDEL (Japanese preserved-flower brand, Keinet Co.) |
| primm | Reads as *prim* (prudish/stiff) — inverts a warm brand; Primm, Nevada is a real casino-resort town; Primm is a Square Enix character in *Secret of Mana* |
| primmy | **Not invented** — the OED lists *primmy* as a real adjective meaning prim-ish, carrying the same prudish semantics. Also niche slang for "anarcho-primitivist." Positive read as a diminutive of Primrose ("first rose") does not outweigh these |
| rillar | Dropped pre-screen — too close to Rilla (~$79M-raised AI company), the same conflict that killed *rillo* in round 1 |

### Survivors pending full screening

grendy, tovell, mirrey, brigie, beamle, brelle — no company, app, or trademark
surfaced for grendy or tovell in initial checks.

### Note on screening depth

The round-5 deep screen could not be completed by parallel agents: the subagent
environment's permission handler stripped parameters from every tool call, so
all 10 agents failed before performing any research (`wf_059971c7-718`).
Findings above come from direct searches in the main loop and are **shallower
than the round-1/2 agent screens** — roughly 4 searches per name rather than
~15. Treat surviving names as pre-screened, not cleared.

## Round 6 — user-proposed names, screened directly

Hand-picked names bypass the engine's dictionary and surname screens, which is
why each collided. Recorded for the changelog:

| Name | Verdict | Reason |
|---|---|---|
| tovy | REJECT | Homophone of **Tovi** (tovi.app) — a live, shipping AI learning app on iOS and Android with personalized paths, lessons, quizzes, streaks, XP and an AI companion. Identical product category. Also Tovi International Preschool, Tovi Score, Tovi Games. tovy.com/.app/.ai all registered |
| grady | REJECT | **Grady Labs Inc.** (gradyai.com) is a live AI-assisted grading platform for higher education — AI + education + identical name. Also Grady Memorial Hospital (Atlanta), plus 24 App Store results incl. 6 exact (Grady GO!, Grady High School, Grady ISD, Grady EMC, Grady County Schools). .com/.app/.ai/.dev all registered |
| grendy | **PASS — screened clean** | See below |

### GRENDY — full screen, 2026-08-04

| Dimension | Finding |
|---|---|
| USPTO trademark | No registration found for GRENDY in any class |
| App Store | 2 total results, **0 exact** (Grundy Center Connect, GRI) |
| Google Play | No Grendy app found |
| Companies / SaaS / startups | None found |
| Surname | Vanishingly rare — ~14 bearers worldwide, mostly Chile (Forebears) |
| English slang | Urban Dictionary entries are benign personal nicknames; no derogatory, sexual, or drug sense |
| Other languages | No negative meaning found in ES, FR, DE, IT, PT |
| Social | TikTok @xgrendy is an active creator (56.5K followers) but holds the *x*-prefixed handle, not @grendy |

**Domains:** .app, .ai, .io, .co, .dev all AVAILABLE; getgrendy.com and
grendyapp.com available; grendy.com registered.

**Residual risks (not blockers):**
- *Grendel* (Beowulf monster) is the nearest cultural echo; Grendel-themed games
  exist (Grendel's Cave on Steam) but no Grendel mark surfaced in class 9
- *Grendene S/A* — Brazilian footwear giant (owner of MELISSA, class 25).
  Different class and different word; low but non-zero opposition risk
- *Grendi* (Norwegian village), *Grenda* (Polish surname, "perch/roost")

**Caveat:** screened via direct search in the main loop (~10 searches), not the
deeper agent pipeline used in rounds 1–2, which remains broken. A professional
knockout search is still required before filing.
