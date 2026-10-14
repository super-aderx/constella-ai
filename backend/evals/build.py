"""Builds the golden set: loads the sample into the test database, runs every case's
ground-truth SQL, and freezes the answers into evals/data/golden.json.

Run from backend/:  uv run --env-file .env python -m evals.build

The golden file is stamped with a hash of the sample data. If the data changes, rebuild, and do
not compare scores across the two builds.
"""

import hashlib
import json
import os
from pathlib import Path

import networkx as nx
import psycopg
import yaml
from psycopg.rows import dict_row

HERE = Path(__file__).parent
DATA = HERE / "data"
SAMPLE = DATA / "invoice.csv"
GOLDEN = DATA / "golden.json"


def load_sample(conn: psycopg.Connection) -> None:
    """Replaces the test database's invoice table with the sample."""
    conn.execute((DATA / "invoice.sql").read_text())
    header = SAMPLE.open(encoding="utf-8").readline().strip()
    with conn.cursor().copy(
        f"COPY invoice ({header}) FROM STDIN WITH (FORMAT csv, HEADER)"
    ) as copy:
        copy.write(SAMPLE.read_bytes())


def groups(edges: list[dict]) -> list[set[str]]:
    """The graph's groups: Louvain with its seed, over the pairs above chance, strongest first."""
    graph = nx.Graph()
    graph.add_weighted_edges_from((r["a"], r["b"], r["lift"]) for r in edges)
    return nx.community.louvain_communities(graph, seed=42)


def derived(kind: str, rows: list[dict], revenue: dict[str, int], fills: dict) -> dict:
    """The answers SQL alone cannot give: betweenness and groups, worked out with NetworkX."""
    items, figures = [], []
    if kind == "betweenness":
        between = nx.betweenness_centrality(nx.Graph((r["a"], r["b"]) for r in rows))
        items = [min(between, key=lambda name: (-between[name], name))]
    elif kind == "top_group":
        best = max(groups(rows), key=lambda g: sum(revenue[name] for name in g))
        items = sorted(best)
        total = sum(revenue[name] for name in best)
        figures = [{"name": "revenue", "value": total, "of": items}]
    elif kind == "bundle":
        # The SQL returns the two leading sets, so a tie for first is caught here.
        first, second = rows[0], rows[1] if len(rows) > 1 else {"co_orders": 0}
        assert first["co_orders"] > second["co_orders"], "two sets tie for first"
        items = [first["a"], first["b"], first["c"]]
        figures = [{"name": "co_orders", "value": first["co_orders"], "of": items}]
    elif kind == "group_of":
        group = next(g for g in groups(rows) if fills["item"] in g)
        items = sorted(group - {fills["item"]})
    return {"expected_items": items, "expected_figures": figures}


def expected(rows: list[dict], asked: list[str]) -> dict:
    """What a case's SQL rows mean: items, pairs, words the answer must contain, and the
    figures it must state."""
    names = ("item", "a", "b", "text")
    return {
        "expected_items": [r["item"] for r in rows if "item" in r],
        "expected_pairs": [[r["a"], r["b"]] for r in rows if "a" in r],
        "expected_text": [r["text"] for r in rows if "text" in r],
        "expected_figures": [
            {"name": column, "value": value, "of": [row[n] for n in names if n in row]}
            for row in rows
            for column, value in row.items()
            if column in asked
        ],
    }


def build(conn: psycopg.Connection) -> list[dict]:
    spec = yaml.safe_load((DATA / "cases.yaml").read_text(encoding="utf-8"))
    none = {"days": None, "segment": None}
    cases = []
    for case in spec["cases"]:
        template = spec["templates"][case["template"]]
        filters = {**none, **case.get("filters", {})}
        fills = case.get("fills", {})

        def rows(sql: str, params: dict) -> list[dict]:
            return conn.execute(spec["prelude"] + sql, params).fetchall()

        golden = {
            "id": case["id"],
            "template": case["template"],
            "kind": case.get("kind", "factual"),
            "split": case.get("split", "dev"),
            "input": case["input"],
            "filters": filters,
            "fills": fills,
            "catches": template["catches"],
            "expected_items": [],
            "expected_pairs": [],
            "expected_text": [],
            "expected_figures": [],
        }
        if golden["kind"] == "trap":
            # A trap is only a trap if what it asks about really is not there.
            if "missing" in case:
                named = conn.execute(
                    "SELECT COUNT(*) AS n FROM invoice WHERE item_tag = %s", [case["missing"]]
                ).fetchone()["n"]
                assert named == 0, f"{case['id']}: {case['missing']} is in the data"
            if "no_segment" in case:
                named = conn.execute(
                    "SELECT COUNT(*) AS n FROM invoice WHERE segment = %s", [case["no_segment"]]
                ).fetchone()["n"]
                assert named == 0, f"{case['id']}: {case['no_segment']} is a segment"
            if "hidden" in case:
                on_graph = rows(template["sql"], {**filters, **case["hidden"]})
                assert not on_graph, f"{case['id']}: the pair is on the graph"
            trap = next(key for key in ("missing", "hidden", "no_segment") if key in case)
            golden |= {"trap": trap, trap: case[trap]}
            if trap == "missing":
                # "Not in the data" may only be said after the name has been looked up.
                golden |= {"expected_tools": [{"name": "find_item", "args": {}}]}
        elif golden["kind"] == "open":
            # No single right answer, so no SQL: only the scopes and the tool are expected.
            scopes = case.get("compare", [case.get("scope", filters)])
            views = [{**none, **scope} for scope in scopes]
            tool = template["tool"]
            sides = {"a": views[0], "b": views[1]} if "compare" in case else views[0]
            golden |= {"expected_views": views}
            golden |= {
                "expected_tools": [{"name": tool["name"], "args": {**tool["args"], **sides}}]
            }
        elif "compare" in case:
            # The same question under two scopes: each side's answer, in the order asked.
            views = [{**none, **scope} for scope in case["compare"]]
            sides = [rows(template["sql"], {**view, **fills}) for view in views]
            assert all(sides), f"{case['id']}: a side of the comparison returned nothing"
            items = [side[0]["item"] for side in sides]
            assert len(set(items)) == 2, f"{case['id']}: both sides give {items[0]}"
            golden |= {"expected_items": items, "expected_views": views}
            # The template's tool, once for each side.
            tool = template["tool"]
            calls = [{"name": tool["name"], "args": {**tool["args"], **fills, **v}} for v in views]
            golden |= {"expected_tools": calls}
        else:
            # The scope the answer is about: the one the question names, else the graph's.
            view = {**none, **case["scope"]} if "scope" in case else filters
            found = rows(template["sql"], {**view, **fills})
            assert found, f"{case['id']}: the ground-truth SQL returned nothing"
            if "derive" in template:
                revenue = {r["item"]: r["revenue"] for r in rows(spec["revenue"], view)}
                golden |= derived(template["derive"], found, revenue, fills)
            else:
                golden |= expected(found, template.get("asked", []))
            tool = template["tool"]
            args = {**tool["args"], **(fills if tool.get("fills", True) else {}), **view}
            # Words that are not the data's have to be looked up before the template's tool.
            find = [{"name": "find_item", "args": {}}] if case.get("find") else []
            golden |= {"expected_views": [view]}
            golden |= {"expected_tools": [*find, {"name": tool["name"], "args": args}]}
        cases.append(golden)
    return cases


def main() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    assert url != os.environ.get("DATABASE_URL"), "TEST_DATABASE_URL must not be the real database"
    with psycopg.connect(url, row_factory=dict_row) as conn:
        load_sample(conn)
        as_of = conn.execute("SELECT MAX(datetime) AS latest FROM invoice").fetchone()["latest"]
        cases = build(conn)
    golden = {
        "as_of": as_of.isoformat(sep=" "),
        "data_sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest(),
        "cases": cases,
    }
    GOLDEN.write_text(json.dumps(golden, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{GOLDEN}: {len(cases)} cases")


if __name__ == "__main__":
    main()
