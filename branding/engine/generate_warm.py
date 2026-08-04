#!/usr/bin/env python3
"""
Warmth-optimized generation pass (round 3).
==========================================
Round 2 established that 3-syllable names are far more legally ownable than
2-syllable ones. But the winning candidate (bukiro) drew a "sounds Japanese and
alien" reaction in review. This pass keeps the 3-syllable ownability advantage
while explicitly optimizing for warmth and familiarity to an English ear.

Three changes vs. the base engine:

1. SOFT ONSETS. Word-initial hard plosives (b, k, p, t, g, d) read blunt and
   foreign in English (buk-, tak-, pok-). Sonorant and fricative onsets
   (l, m, n, r, v, s, h, y, w) open warm — Luna, Miro, Nova, Rivia, Vela.
   Round-2 finalists that drew the complaint all had plosive onsets.

2. ANTI-MORAE. The specific complaint is a Japanese read. A name whose every
   syllable is a valid Japanese mora in strict CV sequence *will* read Japanese
   (bu-ki-ro, na-ru-ke, me-re-pi, ki-ro-ne all decompose perfectly). Names that
   break the pattern somewhere — a consonant coda, a diphthong, a cluster
   Japanese lacks — do not. Full decomposability is penalized hard.

3. ENGLISH-FAMILIAR SHAPES. Reward the vowel and ending patterns that read
   native-adjacent in the English brand space (-a, -o, -ia, -ana, -ella) as in
   Canva, Figma, Miro, Vercel, Sonos.
"""

import random, re, sys, json, os
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import passes_hard_filters, syllable_count, VOWELS, wchoice

random.seed(70714)

# Complete Japanese mora inventory (for the anti-morae penalty)
MORAE = set("""
ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no
ha hi fu he ho ma mi mu me mo ya yu yo ra ri ru re ro wa wo
ga gi gu ge go za ji zu ze zo da de do ba bi bu be bo pa pi pu pe po
kya kyu kyo sha shu sho cha chu cho nya nyu nyo hya hyu hyo
mya myu myo rya ryu ryo gya gyu gyo ja ju jo bya byu byo pya pyu pyo
""".split())

def morae_decomposable(name):
    """True if the whole name parses as a strict Japanese mora sequence."""
    def walk(i):
        if i == len(name):
            return True
        if name[i:i + 1] == "n" and i == len(name) - 1:
            return True                       # syllabic final n
        for ln in (3, 2):
            if name[i:i + ln] in MORAE and walk(i + ln):
                return True
        return False
    return walk(0)

# Warm onsets: sonorants + soft fricatives. Deliberately excludes b/k/p/t/g/d.
WARM_ONSET = {"l": 18, "m": 16, "n": 14, "r": 12, "v": 10, "s": 8,
              "h": 5, "y": 5, "w": 4, "f": 4}
# Interior consonants may include soft plosives — the issue is word-initial.
MID_CONS = {"l": 14, "m": 12, "n": 12, "r": 12, "v": 8, "s": 7, "d": 6,
            "t": 6, "b": 5, "c": 4, "k": 4, "g": 3, "z": 3, "p": 3, "f": 3}
V_WARM = {"a": 30, "o": 22, "i": 18, "e": 16, "u": 8}

# Codas and clusters Japanese phonotactics lacks — these break the morae read.
CODAS = ["l", "r", "n", "m", "s", "v"]
ENDINGS = ["a", "a", "a", "o", "o", "ia", "ea", "ina", "ana", "ella", "ora",
           "una", "eva", "ova", "ala", "ela", "ari", "eri", "oli", "eli"]

def gen_warm_cvcv(n):
    """Soft onset + interior + warm ending."""
    out = []
    for _ in range(n):
        name = wchoice(WARM_ONSET) + wchoice(V_WARM)
        if random.random() < 0.45:
            name += random.choice(CODAS)      # coda breaks the CV morae chain
        name += wchoice(MID_CONS) + random.choice(ENDINGS)
        out.append(name)
    return out

def gen_warm_liquid(n):
    """Liquid-heavy: l/r/m/n skeletons, the warmest consonant class."""
    liquids = ["l", "r", "m", "n"]
    out = []
    for _ in range(n):
        name = random.choice(liquids) + wchoice(V_WARM)
        for _ in range(random.choice([1, 1, 2])):
            name += random.choice(liquids + ["v", "s", "d", "t"]) + wchoice(V_WARM)
        if random.random() < 0.3:
            name += random.choice(["n", "a", "o", "s"])
        out.append(name)
    return out

def gen_warm_romance(n):
    """Romance-shaped: familiar to English ears via Italian/Spanish exposure."""
    starts = ["lu", "li", "la", "le", "ma", "mi", "mo", "me", "na", "ni", "no",
              "ra", "ri", "ro", "va", "vi", "ve", "so", "se", "au", "el", "or",
              "am", "an", "ar", "al", "en", "in", "on", "um"]
    mids = ["m", "n", "l", "r", "v", "s", "nd", "nt", "rn", "ll", "mb", "ri",
            "li", "ni", "vi", "si", "d", "t", "c"]
    out = []
    for _ in range(n):
        out.append(random.choice(starts) + random.choice(mids) + random.choice(ENDINGS))
    return out

def gen_warm_vowelstart(n):
    """Vowel-initial names read open and inviting (Oura, Alma, Aura, Ora)."""
    out = []
    for _ in range(n):
        name = wchoice(V_WARM) + wchoice(MID_CONS) + wchoice(V_WARM)
        if random.random() < 0.5:
            name += wchoice(MID_CONS) + random.choice(["a", "o", "ia", "e", "i"])
        else:
            name += random.choice(CODAS + ["a", "o"])
        out.append(name)
    return out

GENS = {"W1_soft": gen_warm_cvcv, "W2_liquid": gen_warm_liquid,
        "W3_romance": gen_warm_romance, "W4_vowel": gen_warm_vowelstart}

HARD_PLOSIVES = ("b", "k", "p", "t", "g", "d", "c", "q", "j")

def warmth_score(name):
    """0-100, weighted toward warmth and English familiarity."""
    s = 45.0
    L = len(name)
    s += {5: 14, 6: 16, 7: 12, 4: 8}.get(L, 0)
    syl = syllable_count(name)
    s += 12 if syl == 3 else (6 if syl == 2 else 0)   # 3 syllables = ownable

    if name[0] in HARD_PLOSIVES:
        s -= 18                                        # the bukiro problem
    elif name[0] in "lmnr":
        s += 14                                        # warmest onsets
    elif name[0] in VOWELS:
        s += 11                                        # open, inviting
    elif name[0] in "vswhyf":
        s += 8

    if morae_decomposable(name):
        s -= 22                                        # reads Japanese
    sonorant = sum(1 for c in name if c in "lmnraeiou") / L
    s += sonorant * 20                                 # warmth correlates here
    if name[-1] in "ao":
        s += 10                                        # Canva/Figma/Miro shape
    elif name[-1] in "ie":
        s += 5
    if re.search(r"(ll|nn|mm|rr)", name):
        s += 4
    if re.search(r"[aeiou]{2}", name):
        s += 3                                         # diphthong breaks CV chain
    if re.search(r"[bcdfghjklmnpqrstvwz]{2}", name):
        s += 3                                         # a cluster Japanese lacks
    if len(set(name)) < L - 2:
        s -= 5
    return round(min(100.0, max(0.0, s)), 1)

def run(args):
    tag, n, seed = args
    random.seed(seed)
    out = {}
    for name in GENS[tag](n):
        if name in out or not passes_hard_filters(name):
            continue
        out[name] = warmth_score(name)
    return tag, n, out

if __name__ == "__main__":
    PER = int(sys.argv[1]) if len(sys.argv) > 1 else 500_000
    jobs = [(t, PER // 4, 900 + i * 13) for t in GENS for i in range(4)]
    alln, stats = {}, defaultdict(int)
    with Pool() as pool:
        for tag, raw, survivors in pool.imap_unordered(run, jobs):
            stats[tag] += raw
            for k, v in survivors.items():
                if k not in alln or v > alln[k][0]:
                    alln[k] = (v, tag)
    ranked = sorted(alln.items(), key=lambda kv: kv[1][0], reverse=True)
    os.makedirs("branding/output", exist_ok=True)
    with open("branding/output/warm_top_1000.json", "w") as f:
        json.dump([{"name": n, "score": s, "generator": g}
                   for n, (s, g) in ranked[:1000]], f, indent=1)
    print(f"raw       : {sum(stats.values()):,}")
    print(f"survivors : {len(alln):,}")
    print("top 60:", ", ".join(n for n, _ in ranked[:60]))
