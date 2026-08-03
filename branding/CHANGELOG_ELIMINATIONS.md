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

See `output/availability.json` for raw evidence per name. Rejections recorded in REPORT.md §4.

## Round 3 — deep legal/linguistic screening (agents)

Rejections recorded in REPORT.md §5–6.

## Round 2 — deep legal/linguistic screening, batch 1 (2-syllable names)

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

## Round 3 — deep screening, batch 2 (3-syllable names)

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
