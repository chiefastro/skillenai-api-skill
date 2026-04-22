#!/usr/bin/env python3
"""Graph-native entity analysis helpers for the Skillenai knowledge graph.

Resolves entity names to canonical IDs, then runs Cypher queries that are
awkward or slow in SQL:

  - bridge_docs(a_id, a_type, b_id, b_type):
      count DISTINCT documents that mention both entities
      (good for "how narratively entangled are X and Y?")

  - coreq_jobs(pivot_id, others):
      for a pivot product, count jobs that co-require it with each of a
      list of other products
      (good for "is Cursor + Claude Code a complementary toolkit?")

  - internal_hiring_stack(company_id):
      for a company, what products are required in its own job postings
      (good for "does this company have a product-eng org, or a pure SRE org?")

Usage:
    export API_KEY=...
    export API_URL=https://api.skillenai.com
    python entity_bridge_analysis.py --resolve "Cursor:product" "Grok:product" "Anthropic:company"
    python entity_bridge_analysis.py --bridge PRODUCT_ID:product COMPANY_ID:company
    python entity_bridge_analysis.py --coreq PIVOT_ID OTHER1_ID OTHER2_ID ...
    python entity_bridge_analysis.py --stack COMPANY_ID

Engine constraints (verified against the production API 2026-04-22):
  - Max 3 hops in variable-length paths ([*..3])
  - Max 2 comma-separated MATCH patterns (use relationship-chain patterns instead)
  - Documents in the graph expose only id + name — use relational SQL if you
    need source_type/title/published_at for the matched docs
"""
import argparse
import json
import os
import sys
import time
import urllib.request


API_URL = os.environ.get("API_URL", "https://api.skillenai.com")
API_KEY = os.environ.get("API_KEY")


def _post(path, body):
    if not API_KEY:
        sys.exit("API_KEY env var required")
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API_URL}{path}",
        data=data,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def resolve(names):
    payload = {
        "names": [
            {"name": n.split(":")[0], "entity_type": n.split(":")[1]} if ":" in n
            else {"name": n}
            for n in names
        ],
        "mode": "auto",
        "limit": 1,
    }
    return _post("/v1/resolution/entities", payload)


def cypher(q, limit=25):
    return _post("/v1/query/graph", {"cypher": q, "limit": limit})


def bridge_docs(id_a, type_a, id_b, type_b):
    q = (
        f"MATCH (a:{type_a} {{id: '{id_a}'}})<-[:MENTIONS]-(d)"
        f"-[:MENTIONS]->(b:{type_b} {{id: '{id_b}'}}) "
        f"RETURN count(DISTINCT d) AS n"
    )
    r = cypher(q, limit=1)
    return r.get("rows", [{}])[0].get("n", 0)


def coreq_jobs(pivot_id, other_id, pivot_type="product", other_type="product"):
    q = (
        f"MATCH (p:{pivot_type} {{id: '{pivot_id}'}})<-[:MENTIONS]-(j:job)"
        f"-[:MENTIONS]->(o:{other_type} {{id: '{other_id}'}}) "
        f"RETURN count(j) AS n"
    )
    r = cypher(q, limit=1)
    return r.get("rows", [{}])[0].get("n", 0)


def internal_hiring_stack(company_id, limit=20):
    q = (
        f"MATCH (j:job)-[:POSTED_BY]->(c:company {{id: '{company_id}'}}), "
        f"(j)-[:MENTIONS]->(p:product) "
        f"RETURN p.name AS product, count(j) AS jobs "
        f"ORDER BY jobs DESC"
    )
    return cypher(q, limit=limit).get("rows", [])


def top_cooccurring(entity_id, entity_type="product", doc_label="job", limit=25):
    """Top entities that co-appear with the pivot in a given document label."""
    q = (
        f"MATCH (pivot:{entity_type} {{id: '{entity_id}'}})<-[:MENTIONS]-(d:{doc_label})"
        f"-[:MENTIONS]->(e) WHERE e.id <> '{entity_id}' "
        f"RETURN labels(e)[0] AS type, e.name AS name, count(d) AS n "
        f"ORDER BY n DESC"
    )
    return cypher(q, limit=limit).get("rows", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolve", nargs="+", help="Resolve names (format name:entity_type)")
    ap.add_argument("--bridge", nargs=2, metavar=("A", "B"),
                    help="Count bridge docs for two entities (format id:type)")
    ap.add_argument("--coreq", nargs="+", metavar="ID",
                    help="Pivot ID followed by other product IDs (pivot assumed product)")
    ap.add_argument("--stack", help="Company ID — list internal hiring stack")
    ap.add_argument("--cooccur", help="Entity ID:type — list top co-occurring entities in jobs")
    args = ap.parse_args()

    if args.resolve:
        print(json.dumps(resolve(args.resolve), indent=2))
    elif args.bridge:
        (id_a, type_a) = args.bridge[0].split(":")
        (id_b, type_b) = args.bridge[1].split(":")
        print(bridge_docs(id_a, type_a, id_b, type_b))
    elif args.coreq:
        pivot = args.coreq[0]
        for other in args.coreq[1:]:
            print(f"{other}\t{coreq_jobs(pivot, other)}")
            time.sleep(3)
    elif args.stack:
        for row in internal_hiring_stack(args.stack):
            print(f"{row['jobs']:>6}  {row['product']}")
    elif args.cooccur:
        eid, etype = args.cooccur.split(":")
        for row in top_cooccurring(eid, etype):
            print(f"{row['n']:>6}  {row['type']:<10} {row['name']}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
