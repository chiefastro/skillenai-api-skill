#!/usr/bin/env python3
"""Collect peer reviews and meta-reviews from OpenReview without an account.

ACCESS NOTE (verified 2026-09): OpenReview's main `/notes` endpoint sits behind a bot
challenge and returns 403 ChallengeRequiredError. `/notes/search` does NOT, and returns
full note content including review text and structured scores. This script uses search.

Consequences of using search, which you must respect when analysing the output:
  - A non-empty `query` is REQUIRED, so a corpus is assembled from many query terms and
    deduplicated by note id. This introduces term-selection bias. It is fine for
    per-review text properties; it is NOT valid for estimating venue totals.
  - `offset` caps hard at 10,000 per query (400 beyond).
  - `limit` works to at least 150.
  - `group=<venue id>` filters by venue; `source=reply` isolates reviews from submissions.
  - `forum=` is silently IGNORED, so per-paper retrieval is not possible.

For venue SIZE, don't count notes -- reviewer signatures embed the submission number
(`.../Submission19846/Reviewer_Z5SQ`), so the German tank estimator on those numbers
gives a defensible estimate. `--estimate-volume` does this.

Meta-reviews are badly under-sampled by paper-vocabulary queries (0.8% of a corpus in
testing). Use `--kind meta` to query chair-voice vocabulary instead, which lifted the
yield to ~26%.

Usage
-----
  # official reviews across specific venues
  openreview_collect.py --venues ICLR.cc/2026/Conference NeurIPS.cc/2025/Conference \
      --kind review --out reviews.jsonl

  # meta-reviews (uses chair-voice query terms)
  openreview_collect.py --kind meta --out meta.jsonl

  # venue size estimates from an already-collected file
  openreview_collect.py --estimate-volume --in reviews.jsonl
"""
import argparse, collections, json, math, os, re, sys, time, urllib.parse, urllib.request

BASE = "https://api2.openreview.net/notes/search?"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

PAPER_TERMS = ["novelty","baseline","experiments","clarity","significance","motivation",
 "ablation","theoretical","empirical","reproducibility","writing","claims","evaluation",
 "dataset","architecture","benchmark","limitations","assumptions","generalization",
 "hyperparameters","comparison","analysis","contribution","methodology","results",
 "presentation","soundness","scalability","robustness","efficiency","optimization"]

CHAIR_TERMS = ["metareview","recommendation","consensus","rebuttal","borderline",
 "reviewers agree","reviewers raised","after the discussion","area chair","acceptance",
 "threshold","unanimous","discussion period","authors responded","concerns were addressed",
 "remaining concerns","weak accept","weak reject","all reviewers","reviewer scores",
 "post-rebuttal","final decision","score raised","convinced","split","leaning","marginal"]


def fetch(url, tries=4, sleep=1.5):
    """Fetch with backoff. Raises loudly after N failures rather than returning empty --
    a crawler that treats a dead request as 'no results' silently produces an empty
    dataset, which is far worse than crashing."""
    last = None
    for a in range(tries):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
            return json.loads(raw)
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(sleep * (a + 1) * 4)
    raise RuntimeError(f"OpenReview unreachable after {tries} tries ({last})")


def collect(kinds, venues, terms, offsets, per, sleep, out_path):
    want = {"review": {"Official_Review"}, "meta": {"Meta_Review"},
            "both": {"Official_Review", "Meta_Review"}}[kinds]
    seen, n = set(), 0
    groups = venues or [None]
    with open(out_path, "w") as fh:
        for gi, g in enumerate(groups):
            for t in terms:
                for off in offsets:
                    u = BASE + f"query={urllib.parse.quote(t)}&source=reply&limit={per}&offset={off}"
                    if g: u += f"&group={urllib.parse.quote(g)}"
                    d = fetch(u); time.sleep(sleep)
                    notes = d.get("notes", [])
                    if not notes: break
                    for nt in notes:
                        kind = (nt.get("invitations") or [""])[0].split("/-/")[-1]
                        if kind not in want: continue
                        nid = nt.get("id")
                        if nid in seen: continue
                        seen.add(nid)
                        c = nt.get("content") or {}
                        fh.write(json.dumps({
                            "id": nid, "kind": kind, "domain": nt.get("domain"),
                            "forum": nt.get("forum"), "tcdate": nt.get("tcdate"),
                            "signatures": nt.get("signatures"),
                            "content": {k: (v.get("value") if isinstance(v, dict) else v)
                                        for k, v in c.items()}}) + "\n")
                        n += 1
            print(f"  [{gi+1}/{len(groups)}] {g or 'all venues'}: {n} notes", flush=True)
    print(f"DONE {n} unique notes -> {out_path}")


def estimate_volume(path):
    """German tank estimator on submission numbers in reviewer signatures.

    Counts submission SLOTS, which include withdrawn and desk-rejected papers, so the
    estimate runs above published accept-track figures. The RATIOS are the usable part.
    """
    subs = collections.defaultdict(set)
    for line in open(path):
        r = json.loads(line)
        for s in (r.get("signatures") or []):
            m = re.search(r"/Submission(\d+)/", s)
            if m: subs[r.get("domain") or "?"].add(int(m.group(1)))
    print(f"{'venue':<40}{'observed':>10}{'max seen':>10}{'estimate':>12}")
    for d, nums in sorted(subs.items(), key=lambda kv: -len(kv[1])):
        k = len(nums)
        if k < 40: continue
        mx = max(nums)
        print(f"{d:<40}{k:>10,}{mx:>10,}{mx*(k+1)/k - 1:>12,.0f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venues", nargs="*", help="venue group ids, e.g. ICLR.cc/2026/Conference")
    ap.add_argument("--kind", choices=["review", "meta", "both"], default="review")
    ap.add_argument("--out", default="openreview_notes.jsonl")
    ap.add_argument("--per-request", type=int, default=150)
    ap.add_argument("--offsets", type=int, default=3, help="pages per term (offset steps of --per-request)")
    ap.add_argument("--sleep", type=float, default=1.5)
    ap.add_argument("--estimate-volume", action="store_true")
    ap.add_argument("--in", dest="inp", help="input jsonl for --estimate-volume")
    a = ap.parse_args()
    if a.estimate_volume:
        if not a.inp: sys.exit("--estimate-volume needs --in <file.jsonl>")
        return estimate_volume(a.inp)
    terms = CHAIR_TERMS if a.kind == "meta" else PAPER_TERMS
    offsets = [i * a.per_request for i in range(a.offsets)]
    collect(a.kind, a.venues, terms, offsets, a.per_request, a.sleep, a.out)


if __name__ == "__main__":
    main()
