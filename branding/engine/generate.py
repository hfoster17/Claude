#!/usr/bin/env python3
"""
Brand Naming Engine
===================
Generates millions of candidate brand names via 8 independent strategies,
applies hard linguistic/legal-risk filters, scores survivors on brand-quality
heuristics, and emits a ranked shortlist for downstream availability checks.

Generators:
  A  Markov chain trained on successful consumer/startup brand names
  B  Artificial phonetic language (constructed syllabary, harmony rules)
  C  Japanese-inspired phonetics (strict CV morae)
  D  Scandinavian-inspired phonetics
  E  Latin/Romance-inspired roots and endings
  F  Completely synthetic weighted CV templates
  G  Evolutionary search (mutation + crossover on high scorers)
  H  Random constrained phonetics (rejection sampling)
"""

import random
import re
import itertools
from collections import defaultdict
from multiprocessing import Pool

random.seed(20260803)

# ---------------------------------------------------------------- corpora ---

BRAND_CORPUS = [
    # trained-on exemplars: successful consumer brands (used for Markov + collision blocking)
    "finch", "duolingo", "canva", "notion", "oura", "spotify", "roku", "kodak",
    "google", "slack", "discord", "nintendo", "pokemon", "tamagotchi", "pikmin",
    "zelda", "kirby", "yoshi", "mario", "sonos", "vevo", "hulu", "venmo",
    "zynga", "miro", "figma", "loom", "bolt", "vercel", "replit", "strava",
    "calm", "headspace", "forest", "habitica", "noom", "lumo", "elevate",
    "peak", "brilliant", "photomath", "quizlet", "kahoot", "seesaw", "remini",
    "lensa", "picsart", "vsco", "bandlab", "smule", "yousician", "simply",
    "tandem", "memrise", "busuu", "drops", "beelinguapp", "mondly", "lingokids",
    "khanmigo", "socratic", "brainly", "byju", "yuka", "flo", "fabulous",
    "shine", "sanvello", "youper", "wysa", "replika", "woebot", "daylio",
    "moodfit", "happify", "balance", "breethe", "rootd", "clarity", "opal",
    "onesec", "jomo", "freedom", "blinkist", "audm", "curio", "imprint",
    "arlo", "eero", "wyze", "anker", "sonix", "otter", "krisp", "grain",
    "mem", "craft", "bear", "things", "todoist", "ticktick", "akiflow",
    "sunsama", "amie", "cron", "rise", "loona", "moshi", "pzizz", "endel",
]

EXISTING_BRANDS_BLOCK = set(BRAND_CORPUS) | {
    # broader tech/consumer brand universe for confusability blocking
    "apple", "amazon", "meta", "tesla", "uber", "lyft", "waymo", "nvidia",
    "adobe", "intuit", "oracle", "cisco", "zoom", "webex", "asana", "trello",
    "jira", "linear", "airtable", "coda", "quip", "evernote", "obsidian",
    "roam", "logseq", "tana", "reflect", "supernotes", "remnote", "anki",
    "netflix", "disney", "paramount", "peacock", "tubi", "plex", "sling",
    "tiktok", "snap", "pinterest", "reddit", "twitch", "kick", "rumble",
    "shazam", "pandora", "deezer", "tidal", "qobuz", "audible", "libby",
    "kindle", "nook", "kobo", "wattpad", "medium", "substack", "ghost",
    "wix", "squarespace", "webflow", "framer", "carrd", "gumroad", "etsy",
    "shopify", "klarna", "affirm", "chime", "revolut", "monzo", "wise",
    "plaid", "stripe", "square", "block", "cashapp", "zellepay", "paypal",
    "wealthfront", "betterment", "acorns", "stash", "robinhood", "coinbase",
    "kraken", "gemini", "ledger", "trezor", "brave", "opera", "vivaldi",
    "arc", "sigma", "penpot", "sketch", "procreate", "affinity", "pixelmator",
    "lightroom", "darkroom", "halide", "retrica", "huji", "dispo", "beeb",
    "bereal", "poparazzi", "locket", "noteit", "widgetsmith", "carrot",
    "flighty", "fantastical", "spark", "superhuman", "missive", "front",
    "intercom", "drift", "crisp", "tawk", "olark", "hotjar", "amplitude",
    "mixpanel", "posthog", "segment", "braze", "iterable", "klaviyo",
    "duolingo", "babbel", "pimsleur", "lingoda", "italki", "cambly",
    "preply", "verbling", "hellotalk", "speaky", "bilingua", "toucan",
    "clozemaster", "lingvist", "glossika", "chatterbug", "fluent", "elsa",
    "praktika", "speak", "loora", "talkpal", "univerbal", "gliglish",
    "siri", "alexa", "cortana", "bixby", "claude", "gemini", "copilot",
    "perplexity", "poe", "pi", "grok", "mistral", "llama", "qwen", "kimi",
    "luma", "runway", "pika", "sora", "midjourney", "ideogram", "krea",
    "suno", "udio", "eleven", "descript", "veed", "capcut", "inshot",
    "picsart", "canva", "kittl", "recraft", "playground", "leonardo",
    "civitai", "flux", "imagen", "veo", "genie", "gato", "gemma", "phi",
    "lovable", "cursor", "windsurf", "zed", "warp", "fig", "raycast",
    "alfred", "spotlight", "launchbar", "hazel", "keka", "bartender",
    "cleanmymac", "onyx", "istat", "little", "snitch", "lulu", "santa",
    "yoto", "tonies", "lunii", "storypod", "epic", "homer", "abcmouse",
    "prodigy", "splashlearn", "dreambox", "zearn", "ixl", "aleks",
    "photomath", "gauthmath", "symbolab", "mathway", "desmos", "geogebra",
    "wolfram", "chegg", "coursehero", "studocu", "scribd", "grammarly",
    "quillbot", "wordtune", "jasper", "copyai", "writesonic", "rytr",
    "sudowrite", "novelai", "dreamily", "caveduck", "janitor", "character",
    "talkie", "chai", "moemate", "kajiwoto", "paradot", "nomi", "kindroid",
    "wellue", "withings", "whoop", "eightsleep", "levels", "lumen",
    "zoe", "inside", "tracker", "cronometer", "macros", "lifesum",
    "fooducate", "yazio", "lose", "fastic", "zero", "simple", "bodyfast",
    "gentler", "streaks", "productive", "habitify", "strides", "loop",
    "everyday", "momentum", "beeminder", "stickk", "forfeit", "focusmate",
    "flown", "caveday", "flow", "session", "centered", "sukha", "lifeat",
    "brainfm", "noisli", "coffitivity", "rainymood", "mynoise", "defonic",
    "tide", "meditopia", "insight", "smiling", "waking", "tenpercent",
    "buddhify", "unplug", "aura", "breathwrk", "othership", "opensignal",
    "airbnb", "vrbo", "hopper", "kayak", "expedia", "booking", "agoda",
    "gopro", "insta360", "polaroid", "fujifilm", "leica", "hasselblad",
    "lego", "playmobil", "hotwheels", "barbie", "furby", "hatchimals",
    "bluey", "peppa", "cocomelon", "sesame", "khan", "outschool",
    "roblox", "minecraft", "fortnite", "amongus", "hayday", "wordle",
    "sudoku", "twodots", "monument", "alto", "limbo", "unpacking",
    "stardew", "terraria", "coral", "arceus", "digimon", "neopets",
    "webkinz", "clubpenguin", "moshimonsters", "animaljam", "adoptme",
    "widget", "finchcare", "clover", "plum", "mint", "olive", "sage",
    "basil", "thyme", "fern", "moss", "ivy", "willow", "aspen", "cedar",
    "nova", "luna", "stella", "aurora", "cosmo", "orbit", "comet",
    "vega", "lyra", "atlas", "titan", "iris", "echo", "ember", "onyx",
    "coco", "milo", "leo", "remy", "ollie", "ziggy", "biscuit", "mochi",
    "boba", "sushi", "bento", "ramen", "miso", "tofu", "yuzu", "matcha",
    "sakura", "kokoro", "ikigai", "wabi", "zen", "koan", "haiku", "manga",
    "kawaii", "senpai", "kohai", "otaku", "shiba", "akita", "tanuki",
    "kitsune", "totoro", "ghibli", "ponyo", "chihiro", "mononoke",
}

NEGATIVE_SUBSTRINGS = [
    # cross-language negative/slang/offensive fragments (en/fr/es/de/it/pt/ja/ko/zh-pinyin/ar/hi)
    "kaka", "caca", "pipi", "popo", "peepe", "pedo", "puta", "puto", "mierd",
    "merd", "kuso", "baka", "aho", "manko", "chinko", "kintama", "shine",
    "fick", "kack", "arsch", "fotze", "culo", "cazzo", "figa", "minch",
    "porra", "buceta", "viado", "sik", "yarak", "amcik", "gotu", "chut",
    "lund", "gand", "haram", "kalb", "himar", "sharmut", "zib", "kess",
    "fanny", "wank", "bollo", "prick", "slut", "whore", "rape", "nazi",
    "hitl", "isis", "died", "dead", "kill", "murd", "gore", "vomit",
    "fart", "poop", "crap", "piss", "dick", "cock", "cunt", "twat",
    "fuk", "fuck", "fck", "shit", "shyt", "bitc", "btch", "hoe",
    "nigg", "spic", "chink", "gook", "kike", "fagg", "dyke", "tard",
    "anal", "anus", "rect", "peni", "vagi", "tits", "boob", "porn",
    "sexo", "sexy", "nude", "milf", "bdsm", "coit", "orgy",
    "loko", "loco", "tont", "burro", "bobo", "necio", "gili",
    "dumm", "blod", "idiot", "imbec", "cret", "moron", "stupid",
    "sida", "aids", "cancer", "tumor", "ebola", "covid", "virus",
    "diar", "gono", "syph", "herp", "chlam",
]

AWKWARD_CLUSTERS = [
    "bk", "bt", "cb", "cg", "cj", "cp", "cv", "cx", "dk", "dq", "dx",
    "fk", "fq", "fx", "gk", "gq", "gx", "hh", "hj", "hq", "hx", "jj",
    "jk", "jq", "jx", "kq", "kx", "lx", "mx", "pq", "px", "qq", "qx",
    "sx", "tq", "tx", "vx", "wx", "xx", "zx", "xz", "qk", "qj", "qz",
    "vv", "ww", "uu", "ii", "aa" , "yy", "gn", "pf", "ts", "tz", "zh",
    "sr", "vr", "wr", "kn", "mn", "ng", "nk",  # awkward at word start; handled positionally below
]

# ------------------------------------------------------------- phonology ---

VOWELS = "aeiou"
V_W = {"a": 30, "o": 24, "i": 20, "e": 16, "u": 10}
C_W = {"l": 14, "m": 12, "n": 12, "r": 11, "v": 9, "y": 6, "z": 7,
       "k": 10, "p": 9, "b": 8, "t": 9, "d": 5, "f": 4, "s": 6,
       "h": 3, "j": 2, "w": 2, "g": 3}

def wchoice(weights):
    total = sum(weights.values())
    r = random.uniform(0, total)
    upto = 0
    for k, w in weights.items():
        upto += w
        if upto >= r:
            return k
    return k

def syllable_count(name):
    return len(re.findall(r"[aeiouy]+", name))

# --------------------------------------------------------------- filters ---

def levenshtein_leq1(a, b):
    if abs(len(a) - len(b)) > 1:
        return False
    if a == b:
        return True
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    if len(a) > len(b):
        a, b = b, a
    i = j = diff = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            diff += 1
            if diff > 1:
                return False
            j += 1
        else:
            i += 1
            j += 1
    return True

BLOCK_BY_LEN = defaultdict(set)
BLOCK_PREFIXES = set()
for b in EXISTING_BRANDS_BLOCK:
    BLOCK_BY_LEN[len(b)].add(b)
    if len(b) >= 4:
        BLOCK_PREFIXES.add(b[:4])

# real English words are rejected outright: the brief demands an invented name
DICT_WORDS = set()
try:
    with open("/tmp/claude-0/-home-user-Claude/3585d099-a3d2-560b-9c24-d2785ea6da88/scratchpad/popular_words.txt") as f:
        for w in f:
            w = w.strip().lower()
            if 3 <= len(w) <= 7:
                DICT_WORDS.add(w)
except FileNotFoundError:
    pass

def confusable_with_existing(name):
    if name[:4] in BLOCK_PREFIXES:
        return True
    n = len(name)
    for l in (n - 1, n, n + 1):
        for b in BLOCK_BY_LEN.get(l, ()):
            if levenshtein_leq1(name, b):
                return True
    for b in EXISTING_BRANDS_BLOCK:
        if len(b) >= 4 and (b in name or (len(name) >= 4 and name in b)):
            return True
    return False

START_BAD = ("gn", "kn", "mn", "ng", "nk", "sr", "vr", "wr", "ts", "tz", "pf", "zh", "wu", "yi")
END_BAD = ("j", "q", "v", "w", "h", "c")

def passes_hard_filters(name):
    if not (4 <= len(name) <= 7):
        return False
    syl = syllable_count(name)
    if syl < 2 or syl > 3:
        return False
    if any(s in name for s in NEGATIVE_SUBSTRINGS):
        return False
    for cl in AWKWARD_CLUSTERS:
        if cl in name:
            return False
    if name.startswith(START_BAD):
        return False
    if name.endswith(END_BAD):
        return False
    if re.search(r"[bcdfghjklmnpqrstvwxz]{3}", name):
        return False
    if re.search(r"(.)\1\1", name):
        return False
    if "q" in name and "qu" not in name:
        return False
    if "x" in name or "q" in name:  # spelling-risk letters: drop entirely
        return False
    if name in DICT_WORDS:          # invented names only, per brief
        return False
    if len(name) >= 5 and (name[:-1] in DICT_WORDS or name[1:] in DICT_WORDS):
        return False                # trivial word+letter variants read as misspellings
    if confusable_with_existing(name):
        return False
    return True

# -------------------------------------------------------------- scoring ---

PREF = set("lmnrvyzkpbt")
WARM_SOUNDS = ("mo", "lu", "la", "mi", "na", "no", "lo", "ma", "vi", "yu", "pi", "bo", "ki")
PREMIUM_END = ("a", "o", "i", "e", "u", "n", "r", "l", "m", "s", "y", "t", "k")

def score(name):
    s = 50.0
    L = len(name)
    s += {4: 16, 5: 18, 6: 12, 7: 4}.get(L, 0)
    syl = syllable_count(name)
    s += 10 if syl == 2 else 6
    pref_ratio = sum(1 for c in name if c in PREF) / L
    s += pref_ratio * 14
    if name[-1] in VOWELS:
        s += 8            # open ending: warm, global, mascot-friendly
    if name[0] in "lmnbpkvfy":
        s += 4
    cv = re.sub(f"[{VOWELS}]", "V", re.sub(f"[^{VOWELS}]", "C", name))
    if cv in ("CVCV", "CVCVC", "CVCCV", "CVVCV", "CVCVCV", "VCVCV", "CVCCVC"):
        s += 8            # canonical easy-to-say shapes
    if any(w in name for w in WARM_SOUNDS):
        s += 5
    if len(set(name)) >= L - 1:
        s += 3            # letter diversity aids memorability
    if re.search(r"(..).*\1", name):
        s += 2            # internal echo (duo-lingo effect)
    if name[-1] not in PREMIUM_END:
        s -= 8
    if re.search(r"[bcdfghjklmnpqrstvwxz]{2}", name[:2]):
        s -= 4            # initial cluster raises pronunciation friction
    for double in ("ll", "nn", "mm", "zz", "tt", "pp"):
        if double in name:
            s += 2
            break
    return round(min(100.0, max(0.0, s)), 1)

# ------------------------------------------------------------ generators ---

def gen_A_markov(n):
    """Markov chain (order 2) trained on brand corpus."""
    trans = defaultdict(list)
    starts = []
    for w in BRAND_CORPUS:
        w2 = "^" + w + "$"
        starts.append(w2[:3])
        for i in range(len(w2) - 2):
            trans[w2[i:i + 2]].append(w2[i + 2])
    out = []
    for _ in range(n):
        cur = random.choice(starts)
        name = cur.replace("^", "")
        for _ in range(10):
            key = cur[-2:]
            if key not in trans:
                break
            nxt = random.choice(trans[key])
            if nxt == "$":
                break
            name += nxt
            cur = key + nxt
            if len(name) >= 8:
                break
        out.append(name)
    return out

def gen_B_conlang(n):
    """Artificial phonetic language: fixed syllabary with vowel harmony."""
    onsets = ["l", "m", "n", "r", "v", "z", "k", "p", "b", "t", "y", "s", "d"]
    front, back = "ie", "aou"
    out = []
    for _ in range(n):
        harmony = random.choice([front, back, front + back])
        syls = random.choice([2, 2, 2, 3])
        name = ""
        for _ in range(syls):
            name += random.choice(onsets) + random.choice(harmony)
        if random.random() < 0.25:
            name += random.choice("nrls")
        out.append(name)
    return out

def gen_C_japanese(n):
    """Strict CV morae from Japanese-style syllabary."""
    morae = ["ka", "ki", "ku", "ke", "ko", "sa", "shi", "su", "se", "so",
             "ta", "to", "na", "ni", "nu", "ne", "no", "ha", "hi", "he", "ho",
             "ma", "mi", "mu", "me", "mo", "ya", "yu", "yo", "ra", "ri", "ru",
             "re", "ro", "wa", "po", "pa", "pi", "pu", "pe", "bo", "ba", "bi",
             "za", "zu", "zo", "ki", "ko", "mo", "mi", "yu", "ru", "na"]
    out = []
    for _ in range(n):
        k = random.choice([2, 2, 2, 3])
        name = "".join(random.choice(morae) for _ in range(k))
        if random.random() < 0.15:
            name += "n"
        out.append(name)
    return out

def gen_D_scandi(n):
    """Scandinavian-inspired: soft consonants, -a/-o/-en/-ka endings."""
    stems = ["li", "lu", "la", "vi", "ve", "no", "ny", "so", "su", "mo",
             "fi", "fri", "bri", "ka", "kli", "sno", "flo", "hei", "sol",
             "tro", "va", "ha", "ru", "ki", "el", "al", "os", "as", "in"]
    mids = ["v", "l", "m", "n", "r", "s", "d", "lk", "nd", "rn", "st"]
    ends = ["a", "o", "e", "en", "in", "on", "u", "y", "ka", "la", "na", "va", "sa"]
    out = []
    for _ in range(n):
        name = random.choice(stems) + random.choice(mids) + random.choice(ends)
        out.append(name)
    return out

def gen_E_latin(n):
    """Latin/Romance-inspired roots with brandable endings."""
    roots = ["lum", "vit", "am", "car", "sol", "ver", "nov", "prim", "mir",
             "aur", "flor", "cael", "stel", "ali", "ben", "clar", "dul",
             "fel", "gra", "iuv", "laet", "leni", "mel", "opt", "pax",
             "sen", "ten", "val", "viv", "seren", "candor"]
    ends = ["a", "o", "ia", "io", "eo", "ea", "us", "um", "is", "or", "e"]
    out = []
    for _ in range(n):
        r = random.choice(roots)
        e = random.choice(ends)
        if r[-1] in VOWELS and e[0] in VOWELS:
            e = e[1:] or "a"
        out.append(r + e)
    return out

def gen_F_synthetic(n):
    """Weighted CV templates, pure synthesis."""
    templates = ["CVCV", "CVCVC", "CVCCV", "CVCVCV", "VCVCV", "CVVCV", "CVCCVC", "VCCVCV"]
    tw = [30, 18, 14, 12, 8, 8, 6, 4]
    out = []
    for _ in range(n):
        t = random.choices(templates, weights=tw)[0]
        name = ""
        for ch in t:
            name += wchoice(C_W) if ch == "C" else wchoice(V_W)
        out.append(name)
    return out

def gen_H_constrained(n):
    """Rejection sampling over random strings with sonority constraints."""
    out = []
    sonorants = "lmnry"
    while len(out) < n:
        L = random.choice([4, 5, 5, 6, 6, 7])
        name = ""
        prev_v = random.random() < 0.4
        while len(name) < L:
            if prev_v:
                c = wchoice(C_W)
                if name and name[-1] in "ptkbd" and c not in sonorants + "aeiou":
                    continue
                name += c
                prev_v = False
            else:
                name += wchoice(V_W)
                prev_v = random.random() > 0.32
        out.append(name)
    return out

GENS = {
    "A_markov": gen_A_markov,
    "B_conlang": gen_B_conlang,
    "C_japanese": gen_C_japanese,
    "D_scandi": gen_D_scandi,
    "E_latin": gen_E_latin,
    "F_synthetic": gen_F_synthetic,
    "H_constrained": gen_H_constrained,
}

def run_generator(args):
    tag, n, seed = args
    random.seed(seed)
    raw = GENS[tag](n)
    survivors = {}
    for name in raw:
        if name in survivors:
            continue
        if passes_hard_filters(name):
            survivors[name] = score(name)
    return tag, len(raw), survivors

# ------------------------------------------------- evolutionary generator ---

def mutate(name):
    ops = random.random()
    i = random.randrange(len(name))
    if ops < 0.4:  # substitute
        pool = VOWELS if name[i] in VOWELS else "".join(C_W)
        return name[:i] + random.choice(pool) + name[i + 1:]
    if ops < 0.7 and len(name) < 7:  # insert
        return name[:i] + random.choice("aeioulmnr") + name[i:]
    if len(name) > 4:  # delete
        return name[:i] + name[i + 1:]
    return name

def crossover(a, b):
    cut = random.randrange(1, min(len(a), len(b)))
    return a[:cut] + b[cut:]

def gen_G_evolutionary(seed_pool, rounds=25, pop=4000):
    population = dict(seed_pool)
    total_generated = 0
    for _ in range(rounds):
        parents = sorted(population, key=population.get, reverse=True)[:600]
        children = []
        for _ in range(pop):
            if random.random() < 0.5 and len(parents) >= 2:
                c = crossover(*random.sample(parents, 2))
            else:
                c = mutate(random.choice(parents))
            children.append(c)
        total_generated += len(children)
        for c in children:
            if c not in population and passes_hard_filters(c):
                population[c] = score(c)
        if len(population) > 60000:
            keep = sorted(population, key=population.get, reverse=True)[:40000]
            population = {k: population[k] for k in keep}
    return total_generated, population

# ------------------------------------------------------------------ main ---

if __name__ == "__main__":
    import json, os, sys, time
    t0 = time.time()
    PER_GEN = int(sys.argv[1]) if len(sys.argv) > 1 else 750_000

    jobs = []
    seed = 1000
    for tag in GENS:
        # split each generator into 4 shards for parallelism
        for shard in range(4):
            jobs.append((tag, PER_GEN // 4, seed))
            seed += 7

    all_names = {}
    per_gen_stats = defaultdict(lambda: [0, 0])
    with Pool() as pool:
        for tag, n_raw, survivors in pool.imap_unordered(run_generator, jobs):
            per_gen_stats[tag][0] += n_raw
            for name, sc in survivors.items():
                if name not in all_names or sc > all_names[name][0]:
                    all_names[name] = (sc, tag)
            per_gen_stats[tag][1] = sum(1 for v in all_names.values() if v[1] == tag)

    total_raw = sum(v[0] for v in per_gen_stats.values())

    # Generator G: evolve from current top scorers
    seed_pool = {k: v[0] for k, v in
                 sorted(all_names.items(), key=lambda kv: kv[1][0], reverse=True)[:5000]}
    g_raw, evolved = gen_G_evolutionary(seed_pool)
    total_raw += g_raw
    for name, sc in evolved.items():
        if name not in all_names:
            all_names[name] = (sc, "G_evolutionary")
    per_gen_stats["G_evolutionary"] = [g_raw,
        sum(1 for v in all_names.values() if v[1] == "G_evolutionary")]

    ranked = sorted(all_names.items(), key=lambda kv: kv[1][0], reverse=True)

    os.makedirs("branding/output", exist_ok=True)
    with open("branding/output/top_5000.json", "w") as f:
        json.dump([{"name": n, "score": s, "generator": g}
                   for n, (s, g) in ranked[:5000]], f, indent=1)
    with open("branding/output/top_500.txt", "w") as f:
        for n, (s, g) in ranked[:500]:
            f.write(f"{n}\t{s}\t{g}\n")
    with open("branding/output/stats.json", "w") as f:
        json.dump({
            "total_raw_generated": total_raw,
            "unique_survivors": len(all_names),
            "per_generator": {k: {"raw": v[0], "survivors": v[1]}
                              for k, v in per_gen_stats.items()},
            "runtime_sec": round(time.time() - t0, 1),
        }, f, indent=2)

    print(f"raw generated : {total_raw:,}")
    print(f"survivors     : {len(all_names):,}")
    print(f"runtime       : {time.time()-t0:.1f}s")
    print("top 40:", ", ".join(n for n, _ in ranked[:40]))
