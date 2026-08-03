#!/usr/bin/env python3
"""Automated availability pre-screen: iTunes App Store + RDAP domains."""
import json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

CANDIDATES = [
    "otomo","poko","pomu","moomo","bolio","rillo","tamo","namo","koru","solu",
    "kirone","kirona","korina","tiona","riona","rione","kelu","nalo","lovi","tovi",
    "veki","luki","lemi","sumi","kalo","meki","maku","tunu","leli","varo",
    "toko","mesi","rima","valu","yala","kore","muli","tolo","tule","rano",
    "bele","nolu","tali","lanu","mamo","neli","palo","keme","nodo","vene",
    "maka","telu","karo","meri","kamo","vono","rila","rubo","vona","tole",
    "sela","loka","tola","pobi","nidi","toka","kepi","taru","damo","voli",
    "leme","vako","meke","tevi","zima","sula","mibi","teno","teki","kere",
    "paru","peli","motu","bonu","savi","vite","pebi","ponu","roza","bazu",
    "zeme","peme","konu","bremo","tance","remon","migoku","botomo","memoni","pical",
    "finte","bance","monin","velin","boline","akise","banmo","goomo","nooda","tioni",
    "minly","zele","piflo","tiflo","memie",
]

def curl(url, extra=None):
    cmd = ["curl", "-sL", "--max-time", "7", "-o", "-", "-w", "\n%{http_code}", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        body, _, code = r.stdout.rpartition("\n")
        return body, code.strip()
    except Exception:
        return "", "err"

def rdap(domain):
    _, code = curl(f"https://rdap.org/domain/{domain}")
    if code == "404":
        return "AVAILABLE"
    if code == "200":
        return "taken"
    return f"unknown({code})"

def itunes(name):
    body, code = curl(f"https://itunes.apple.com/search?term={name}&entity=software&limit=25")
    if code != "200":
        return {"status": f"err({code})"}
    try:
        d = json.loads(body)
    except Exception:
        return {"status": "parse_err"}
    exact, near = [], []
    for app in d.get("results", []):
        t = app.get("trackName", "").lower()
        first = t.replace(":", " ").replace("-", " ").split()[0] if t.split() else ""
        if first == name or t == name:
            exact.append(app.get("trackName"))
        elif name in t:
            near.append(app.get("trackName"))
    return {"status": "ok", "n_results": d.get("resultCount", 0),
            "exact": exact[:5], "near": near[:5]}

def check_domains(name):
    with ThreadPoolExecutor(4) as ex:
        futs = {tld: ex.submit(rdap, f"{name}.{tld}") for tld in ("com", "app", "ai")}
        return {tld: f.result() for tld, f in futs.items()}

if __name__ == "__main__":
    out = {}
    for i, name in enumerate(CANDIDATES):
        row = {"appstore": itunes(name), "domains": check_domains(name)}
        out[name] = row
        print(f"[{i+1}/{len(CANDIDATES)}] {name}: apps={row['appstore'].get('n_results','?')} "
              f"exact={len(row['appstore'].get('exact',[]))} com={row['domains']['com']} "
              f"app={row['domains']['app']} ai={row['domains']['ai']}",
              flush=True)
        with open("branding/output/availability.json", "w") as f:
            json.dump(out, f, indent=1)
        time.sleep(2.6)  # respect iTunes Search API rate limits (~20/min)
    print("done")
