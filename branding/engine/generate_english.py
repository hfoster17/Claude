#!/usr/bin/env python3
"""
English-phonotactics generation pass (round 4).
==============================================
Direction change: the name must read as solidly English — native to an English
ear, not Japanese, Romance, or synthetic-international.

Rounds 1-3 all generated open CV syllables (bu-ki-ro, me-re-pi, ni-le-va).
That structure is why they read foreign: English is a cluster-and-coda language,
not a mora language. Its brand-name texture comes from Anglo-Saxon and Middle
English shapes — onset clusters (br-, fl-, thr-), closed syllables, and native
suffixes (-le, -en, -er, -ow, -et, -ick).

Compare: Kodak, Google, Slack, Finch, Wispr all have codas or clusters.
Bukiro, Merepi, Nileva have neither.

The cluster inventory also fixes ownability. Round 1 showed the 4-letter CVCV
space is exhausted — every pronounceable combination is taken. English onsets
(24 of them) times nuclei times codas (30+) is a combinatorially larger space,
so 6-8 letter English-shaped coinages are far less crowded than 4-letter CVCV.

Names remain invented — the dictionary screen from the base engine still
rejects real English words, per the brief's "invented brand, not a keyword."
"""

import random, re, sys, json, os
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import (NEGATIVE_SUBSTRINGS, DICT_WORDS, confusable_with_existing,
                      syllable_count)

random.seed(31415)

# --- English phonotactic inventory -----------------------------------------

# Onsets legal at English word start, weighted toward the warm/bright end.
ONSET = {
    "b": 10, "br": 9, "bl": 7, "p": 7, "pr": 6, "pl": 6, "t": 6, "tr": 8,
    "d": 6, "dr": 6, "k": 5, "c": 6, "cr": 6, "cl": 6, "g": 4, "gr": 5,
    "gl": 4, "f": 6, "fr": 5, "fl": 7, "th": 4, "thr": 3, "s": 6, "st": 6,
    "sp": 5, "sk": 3, "sl": 5, "sn": 5, "sw": 4, "sh": 5, "ch": 5,
    "m": 11, "n": 8, "l": 8, "r": 6, "w": 7, "wh": 3, "wr": 2, "h": 4,
    "v": 4, "y": 3, "j": 3, "qu": 1, "tw": 3,
}

NUCLEUS = {"a": 18, "e": 16, "i": 18, "o": 16, "u": 8, "oo": 5, "ee": 5,
           "ea": 4, "ai": 3, "ou": 3, "ow": 3, "ie": 2, "oa": 2}

# Codas that close a syllable the way English does.
CODA = {"": 14, "n": 12, "m": 8, "l": 10, "r": 8, "ck": 7, "sh": 5, "st": 5,
        "nd": 6, "nt": 5, "mp": 4, "sk": 3, "ft": 3, "tch": 3, "ll": 6,
        "b": 3, "d": 4, "g": 2, "p": 3, "t": 5, "s": 4, "ng": 4, "rn": 3,
        "rl": 3, "lt": 3, "lm": 2, "ss": 4, "ff": 3, "zz": 2, "dge": 3}

# Native English second-syllable endings — the Anglo-Saxon brand texture.
ENDING = {
    "le": 14, "en": 12, "er": 11, "ow": 9, "et": 8, "in": 8, "on": 8,
    "y": 10, "ey": 6, "ie": 5, "ell": 7, "ick": 6, "ock": 5, "ip": 5,
    "ub": 3, "am": 5, "om": 4, "an": 6, "el": 6, "ot": 4, "it": 5,
    "um": 4, "up": 3, "ar": 5, "or": 5, "ish": 4, "ock": 4, "ade": 3,
    "ade": 3, "ove": 4, "ine": 5, "ale": 4, "ope": 3, "ide": 3, "ake": 3,
}

LINK = {"b": 6, "d": 7, "g": 4, "k": 5, "l": 10, "m": 9, "n": 9, "p": 6,
        "r": 8, "s": 6, "t": 8, "v": 5, "w": 4, "z": 3, "ck": 5, "dd": 4,
        "ff": 3, "ll": 7, "mm": 5, "nn": 5, "pp": 5, "rr": 4, "tt": 6,
        "mb": 4, "nd": 6, "nk": 5, "st": 5, "sk": 3, "ndl": 4, "mbl": 4,
        "ttl": 4, "ckl": 4, "ppl": 3, "ffl": 3, "zzl": 3, "stl": 3, "ngl": 3}

def wpick(d):
    ks = list(d); ws = [d[k] for k in ks]
    return random.choices(ks, weights=ws)[0]

# --- generators -------------------------------------------------------------

def gen_E1_disyllable(n):
    """Onset + nucleus + link + native ending — the core English brand shape."""
    return [wpick(ONSET) + wpick(NUCLEUS) + wpick(LINK) + wpick(ENDING)
            for _ in range(n)]

def gen_E2_closed(n):
    """Closed first syllable then ending: Brindle, Wicket, Tumbler."""
    return [wpick(ONSET) + wpick(NUCLEUS) + wpick(CODA) + wpick(ENDING)
            for _ in range(n)]

def gen_E3_monosyllable(n):
    """Punchy one-syllable coinages: the Slack/Finch/Roku register."""
    out = []
    for _ in range(n):
        name = wpick(ONSET) + wpick(NUCLEUS) + wpick(CODA)
        if random.random() < 0.35:
            name += random.choice(["y", "o", "er", "le", "ie"])
        out.append(name)
    return out

def gen_E4_diminutive(n):
    """Diminutive/pet-name register — the mascot sweet spot (Bluey, Poppet)."""
    stems = ["bram", "brim", "brin", "bub", "bun", "chip", "clem", "dob",
             "dun", "fen", "fig", "flin", "flum", "fro", "gil", "hob", "jem",
             "lin", "lum", "mab", "mig", "mil", "mim", "mop", "mun", "nib",
             "nim", "nob", "nol", "nud", "pem", "pip", "plum", "pod", "pom",
             "pud", "quil", "rob", "rud", "shim", "skip", "snug", "sprig",
             "tam", "tib", "tob", "trin", "tud", "tum", "wid", "win", "wob",
             "wren", "yob", "bod", "bil", "dil", "gob", "hud", "jib", "kit"]
    ends = ["by", "ley", "ly", "kin", "let", "et", "o", "s", "ers", "sy",
            "sey", "ton", "don", "bo", "po", "in", "ie", "y", "el", "en"]
    return [random.choice(stems) + random.choice(ends) for _ in range(n)]

GENS = {"E1_disyllable": gen_E1_disyllable, "E2_closed": gen_E2_closed,
        "E3_mono": gen_E3_monosyllable, "E4_diminutive": gen_E4_diminutive}

# --- filters ----------------------------------------------------------------

ILLEGAL = re.compile(
    r"([bcdfghjklmnpqrstvwxz]{4})"          # 4+ consonant run
    r"|([aeiou]{3})"                        # 3+ vowel run
    r"|(.)\3\3"                             # triple letter
    r"|(^(ng|dg|tch|zz|rr|ll|nn|mm|pp|tt|ff|ss|dd|ck))"   # illegal onsets
    r"|(qu?[^aeiou])|q$|j$|v$|h$"           # illegal finals
)
UGLY = ("uu", "ii", "yy", "jj", "hh", "wq", "zx", "xz", "gj", "dj", "tj",
        "vk", "vt", "vp", "vd", "vb", "vg", "fk", "fp", "bk", "gk", "kg",
        "shsh", "chch", "thth", "ckck", "sks", "zsh", "shz", "ngn", "mbm")

def passes_english(name):
    if not (4 <= len(name) <= 8):
        return False
    if syllable_count(name) not in (1, 2, 3):
        return False
    if ILLEGAL.search(name) or any(u in name for u in UGLY):
        return False
    if any(s in name for s in NEGATIVE_SUBSTRINGS):
        return False
    if name in DICT_WORDS:
        return False
    if len(name) >= 5 and (name[:-1] in DICT_WORDS or name[1:] in DICT_WORDS):
        return False
    if not re.search(r"[aeiouy]", name):
        return False
    if confusable_with_existing(name):
        return False
    return True

# --- scoring ----------------------------------------------------------------

ENGLISH_END = ("le", "en", "er", "ow", "et", "in", "on", "y", "ey", "ie",
               "ell", "ick", "ock", "ip", "am", "an", "el", "it", "ar", "or")
BRIGHT = set("bplmnrwfk")

def score_english(name):
    s = 45.0
    L = len(name)
    s += {5: 15, 6: 18, 7: 14, 4: 10, 8: 6}.get(L, 0)
    syl = syllable_count(name)
    s += {2: 16, 1: 8, 3: 6}.get(syl, 0)
    if name.endswith(ENGLISH_END):
        s += 14                                     # native English cadence
    if name[0] in BRIGHT:
        s += 7
    if re.match(r"^[bcdfgpst][rl]", name):
        s += 8                                      # English onset cluster
    if re.search(r"(ck|ll|tt|pp|mm|nn|dd|ff)", name):
        s += 6                                      # doubled medial: very English
    if re.search(r"(nd|nt|mp|st|nk|mb|ng)", name):
        s += 5                                      # native coda cluster
    vowels = re.findall(r"[aeiou]+", name)
    if vowels and all(len(v) == 1 for v in vowels):
        s += 4                                      # crisp, unambiguous spelling
    if len(set(name)) >= L - 1:
        s += 3
    if re.search(r"[aeiou]{2}", name):
        s -= 3                                      # digraphs invite misspelling
    if name.endswith(("ly", "ify", "ate")):
        s -= 10                                     # dated SaaS cadence
    return round(min(100.0, max(0.0, s)), 1)

def run(args):
    tag, n, seed = args
    random.seed(seed)
    out = {}
    for name in GENS[tag](n):
        if name not in out and passes_english(name):
            out[name] = score_english(name)
    return tag, n, out

if __name__ == "__main__":
    PER = int(sys.argv[1]) if len(sys.argv) > 1 else 750_000
    jobs = [(t, PER // 4, 500 + i * 17) for t in GENS for i in range(4)]
    alln, stats = {}, defaultdict(int)
    with Pool() as pool:
        for tag, raw, sur in pool.imap_unordered(run, jobs):
            stats[tag] += raw
            for k, v in sur.items():
                if k not in alln or v > alln[k][0]:
                    alln[k] = (v, tag)
    ranked = sorted(alln.items(), key=lambda kv: kv[1][0], reverse=True)
    os.makedirs("branding/output", exist_ok=True)
    with open("branding/output/english_top_2000.json", "w") as f:
        json.dump([{"name": n, "score": s, "generator": g}
                   for n, (s, g) in ranked[:2000]], f, indent=1)
    print(f"raw       : {sum(stats.values()):,}")
    print(f"survivors : {len(alln):,}")
    print("top 80:", ", ".join(n for n, _ in ranked[:80]))
