#!/usr/bin/env python3
"""Exact all-pairs near-duplicate scan over Skillenai document embeddings.

Answers "how much of this corpus is a rewrite of itself?" for any index whose
documents carry embeddings (prod-enriched-scholarly, -blog, -news, -jobs).

Embeddings are 256-dim and L2-normalised, so cosine is a dot product and an exact
all-pairs scan is tractable well past 100k documents via chunked matmul.

Two things this script does that a naive version gets wrong:

  1. DEDUPLICATES FIRST, by document id and content hash. A corpus with
     double-ingested documents will otherwise report those pipeline artifacts as
     "near-duplicate content" -- the single easiest way to fabricate this finding.

  2. REPORTS AUTHOR OVERLAP PER SIMILARITY BAND. The interesting question is
     almost never "are there duplicates" but "are they the same author?" Self-
     versioning (re-uploads, v2 rewrites, annual challenge reports) looks
     identical to plagiarism until you split by author overlap.

Calibrate the threshold, don't assume it: --dump-pairs writes sampled pairs per
band so you can read them and decide what "duplicate" means in your corpus.

Usage
-----
  # scan a JSONL export (fields: documentId, embedding, plus any id/author fields)
  near_duplicate_scan.py --input corpus.jsonl --author-field authors

  # tighter/looser bands, and dump pairs for manual calibration
  near_duplicate_scan.py --input corpus.jsonl \
      --thresholds 0.90,0.95,0.98 --dump-pairs pairs.json

  # trend check at constant corpus size (a bigger corpus mechanically raises
  # nearest-neighbour similarity, so a raw month-over-month trend is an artifact)
  near_duplicate_scan.py --input corpus.jsonl --by-period publishedAt --period-n 6000
"""
import argparse, collections, json, sys

try:
    import numpy as np
except ImportError:
    sys.exit("numpy required: pip install numpy")

BANDS = [(0.85, 0.90), (0.90, 0.925), (0.925, 0.95), (0.95, 0.97), (0.97, 1.01)]


def load(path, emb_field, id_field, hash_field, author_field, period_field):
    rows, seen_id, seen_hash = [], set(), set()
    dup_id = dup_hash = 0
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            e = r.get(emb_field)
            if not e:
                continue
            rid = r.get(id_field)
            h = r.get(hash_field)
            if rid is not None and rid in seen_id:
                dup_id += 1
                continue
            if h and h in seen_hash:
                dup_hash += 1
                continue
            if rid is not None:
                seen_id.add(rid)
            if h:
                seen_hash.add(h)
            rows.append({
                "emb": e,
                "id": rid,
                "authors": r.get(author_field) or [],
                "period": (r.get(period_field) or "")[:7] if period_field else None,
                "title": r.get("title"),
            })
    return rows, dup_id, dup_hash


def scan(X, thresholds, block=2048):
    """Return per-row nearest-neighbour similarity, its index, and counts per threshold."""
    n = len(X)
    best = np.zeros(n, dtype=np.float32)
    besti = np.full(n, -1, dtype=np.int64)
    cnt = {t: np.zeros(n, dtype=np.int32) for t in thresholds}
    for s in range(0, n, block):
        e = min(n, s + block)
        S = X[s:e] @ X.T
        for k in range(e - s):
            S[k, s + k] = -1.0
        mi = S.argmax(1)
        best[s:e] = S[np.arange(e - s), mi]
        besti[s:e] = mi
        for t in thresholds:
            cnt[t][s:e] = (S >= t).sum(1)
        del S
    return best, besti, cnt


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="JSONL with one document per line")
    ap.add_argument("--embedding-field", default="embedding")
    ap.add_argument("--id-field", default="documentId")
    ap.add_argument("--hash-field", default="contentHash")
    ap.add_argument("--author-field", default=None,
                    help="array field used for the author-overlap split (e.g. authors)")
    ap.add_argument("--thresholds", default="0.90,0.925,0.95,0.97,0.98,0.99")
    ap.add_argument("--dump-pairs", metavar="PATH",
                    help="write sampled pairs per band for manual threshold calibration")
    ap.add_argument("--by-period", metavar="FIELD",
                    help="date field; compute WITHIN-period rates at a fixed subsample size")
    ap.add_argument("--period-n", type=int, default=6000)
    ap.add_argument("--period-draws", type=int, default=5)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()

    thresholds = [float(t) for t in a.thresholds.split(",")]
    rows, dup_id, dup_hash = load(a.input, a.embedding_field, a.id_field,
                                  a.hash_field, a.author_field, a.by_period)
    if not rows:
        sys.exit("no documents with embeddings found")
    print(f"loaded {len(rows):,} unique documents "
          f"(dropped {dup_id:,} duplicate ids, {dup_hash:,} duplicate content hashes)")

    X = np.asarray([r["emb"] for r in rows], dtype=np.float32)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X /= norms
    print(f"matrix {X.shape}")

    best, besti, cnt = scan(X, thresholds)
    n = len(X)

    print("\n=== nearest-neighbour similarity distribution ===")
    for q in (50, 75, 90, 95, 99, 99.9):
        print(f"  p{q:<5} {np.percentile(best, q):.4f}")
    print(f"  mean  {best.mean():.4f}   max {best.max():.4f}")

    print("\n=== documents with >=1 neighbour above threshold ===")
    for t in thresholds:
        k = int((cnt[t] > 0).sum())
        print(f"  cos >= {t:.3f} : {k:7,}  ({100 * k / n:6.3f}%)")

    if a.author_field:
        print("\n=== author overlap by similarity band ===")
        print("  (high overlap = self-versioning; low overlap = independent convergence)")
        auth = [set(str(x).lower().strip() for x in r["authors"]) for r in rows]
        for lo, hi in BANDS:
            idx = np.where((best >= lo) & (best < hi))[0]
            if len(idx) == 0:
                continue
            sh = sum(1 for i in idx if auth[i] & auth[int(besti[i])])
            print(f"  [{lo:.3f},{hi:.3f})  n={len(idx):7,}  share an author: {100 * sh / len(idx):5.1f}%")

    if a.by_period:
        rng = np.random.default_rng(a.seed)
        bym = collections.defaultdict(list)
        for i, r in enumerate(rows):
            if r["period"]:
                bym[r["period"]].append(i)
        print(f"\n=== within-period rate at FIXED subsample N={a.period_n:,} "
              f"({a.period_draws} draws) ===")
        print("  a growing corpus mechanically raises NN similarity, so a raw")
        print("  period-over-period trend is an artifact; this holds size constant")
        for m in sorted(bym):
            ix = np.asarray(bym[m])
            if len(ix) < a.period_n:
                print(f"  {m}  n={len(ix):6,}  (skipped, under {a.period_n:,})")
                continue
            acc = {t: [] for t in thresholds}
            for _ in range(a.period_draws):
                pick = ix[rng.choice(len(ix), a.period_n, replace=False)]
                S = X[pick] @ X[pick].T
                np.fill_diagonal(S, -1.0)
                mx = S.max(1)
                for t in thresholds:
                    acc[t].append(100 * (mx >= t).mean())
                del S
            cells = "  ".join(f">={t:.3f} {np.mean(acc[t]):6.3f}%" for t in thresholds)
            print(f"  {m}  n={len(ix):6,}  {cells}")

    if a.dump_pairs:
        out = {}
        for lo, hi in BANDS:
            idx = np.where((best >= lo) & (best < hi))[0]
            if len(idx) == 0:
                continue
            pick = idx[np.linspace(0, len(idx) - 1, min(12, len(idx))).astype(int)]
            out[f"{lo}-{hi}"] = [{
                "cos": float(best[i]),
                "a_id": rows[i]["id"], "b_id": rows[int(besti[i])]["id"],
                "a_title": rows[i]["title"], "b_title": rows[int(besti[i])]["title"],
                "a_authors": rows[i]["authors"], "b_authors": rows[int(besti[i])]["authors"],
            } for i in pick]
        with open(a.dump_pairs, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"\nwrote calibration pairs -> {a.dump_pairs}")
        print("READ THESE before choosing a threshold; 'duplicate' is corpus-specific.")


if __name__ == "__main__":
    main()
