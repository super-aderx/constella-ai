"""Writes the sample sales records the golden set is built on: evals/data/invoice.csv.

Run from backend/:  uv run python -m evals.make_sample

The columns are the real invoice table's. The records are made up, but not at random: every
basket comes from a shopping mission (breakfast, snacks, cleaning …), and a few facts are planted
so each golden question can tell a right method from a wrong one. `check` asserts every planted
fact, so the file is never written without them.
"""

import csv
import random
from collections import Counter
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path

import networkx as nx

OUT = Path(__file__).parent / "data" / "invoice.csv"
COLUMNS = [
    "inv_num",
    "datetime",
    "user_id",
    "segment",
    "county",
    "city",
    "item_tag",
    "item_name",
    "item_brand_name",
    "price",
    "unit",
    "amount",
]

SEED = 7
INVOICES = 1500
USERS = 400  # each has one segment and one home district, on every invoice
COUNTY = "高雄市"
AS_OF = datetime(2026, 9, 30)  # the newest day in the data; every period counts back from it
DAYS = 120
GRAPH_FLOOR = 30  # the graph leaves out pairs sharing fewer baskets (data.MIN_CO_ORDERS)

# Product type: its products, each with a brand and a price.
PRODUCTS = {
    "鮮乳": [
        ("瑞穗鮮乳 930ml", "瑞穗", 92),
        ("低脂鮮乳 936ml", "光泉", 88),
        ("鮮乳 1857ml", "林鳳營", 172),
    ],
    "吐司": [
        ("白吐司", "統一麵包", 42),
        ("全麥吐司", "統一麵包", 48),
        ("厚片吐司", "義美", 45),
    ],
    "雞蛋": [
        ("洗選蛋 10入", "大成", 85),
        ("放牧蛋 6入", "石安牧場", 98),
        ("土雞蛋 10入", "大成", 120),
    ],
    "優格": [
        ("原味優格 500g", "福樂", 79),
        ("希臘優格 400g", "馬修嚴選", 109),
        ("草莓優格 4入", "福樂", 65),
    ],
    "咖啡": [
        ("濾掛咖啡 20入", "UCC", 229),
        ("即溶咖啡 100g", "雀巢", 189),
        ("咖啡豆 227g", "UCC", 320),
    ],
    "洋芋片": [
        ("原味洋芋片", "樂事", 39),
        ("海苔洋芋片", "樂事", 39),
        ("厚切洋芋片 大包", "品客", 65),
    ],
    "可樂": [
        ("可樂 600ml", "可口可樂", 29),
        ("零卡可樂 600ml", "可口可樂", 29),
        ("可樂 2L", "百事", 49),
    ],
    "啤酒": [
        ("經典啤酒 6入", "台灣啤酒", 199),
        ("金牌啤酒 6入", "台灣啤酒", 219),
        ("啤酒 6入", "海尼根", 329),
    ],
    "泡麵": [
        ("牛肉泡麵 5入", "統一", 95),
        ("海鮮泡麵 5入", "維力", 99),
        ("乾拌麵 4入", "維力", 129),
    ],
    "餅乾": [
        ("蘇打餅乾", "義美", 45),
        ("巧克力餅乾", "義美", 55),
        ("夾心餅乾 家庭包", "奧利奧", 89),
    ],
    "衛生紙": [
        ("抽取式衛生紙 12包", "舒潔", 139),
        ("抽取式衛生紙 24包", "五月花", 259),
        ("捲筒衛生紙 12捲", "舒潔", 119),
    ],
    "洗衣精": [
        ("洗衣精 2L", "白蘭", 199),
        ("濃縮洗衣精 1.8L", "一匙靈", 259),
        ("洗衣精補充包 1.5L", "白蘭", 149),
    ],
    "洗髮精": [
        ("洗髮精 700ml", "飛柔", 189),
        ("去屑洗髮精 400ml", "海倫仙度絲", 219),
        ("護色洗髮精 500ml", "潘婷", 249),
    ],
    "紅酒": [
        ("智利紅酒 750ml", "紅魔鬼", 399),
        ("法國紅酒 750ml", "木桐嘉棣", 620),
        ("澳洲紅酒 750ml", "黃尾袋鼠", 450),
    ],
    "起司": [
        ("切達起司片", "安佳", 119),
        ("莫札瑞拉起司", "安佳", 159),
        ("卡門貝爾起司", "總統牌", 199),
    ],
}

# Mission: the chance each product type is in a basket on that mission.
MISSIONS = {
    "breakfast": {"鮮乳": 0.8, "吐司": 0.55, "雞蛋": 0.3, "優格": 0.35, "咖啡": 0.28},
    "snacks": {"洋芋片": 0.6, "可樂": 0.55, "泡麵": 0.4, "餅乾": 0.45, "啤酒": 0.35, "咖啡": 0.34},
    "cleaning": {"衛生紙": 0.8, "洗衣精": 0.5, "洗髮精": 0.4},
    # A quick top-up of best sellers from different aisles: popular, but not bought as a set.
    "top-up": {"鮮乳": 0.5, "衛生紙": 0.5, "雞蛋": 0.3, "可樂": 0.2},
    # Rare and tight: a huge lift on very few baskets.
    "wine": {"紅酒": 0.9, "起司": 0.7, "餅乾": 0.3},
}
MISSION_WEIGHTS = {
    "breakfast": 0.30,
    "snacks": 0.25,
    "cleaning": 0.21,
    "top-up": 0.22,
    "wine": 0.02,
}

SEGMENTS = {"重要價值客戶": 0.25, "忠誠客戶": 0.2, "新客戶": 0.3, "沉睡客戶": 0.25}
CITIES = {"三民區": 0.35, "鳳山區": 0.28, "左營區": 0.22, "前鎮區": 0.15}

# The planted facts that are not just a mission.
LOYAL = "忠誠客戶"  # with coffee, they take toast rather than milk
BEER_CITY = "前鎮區"  # the smallest district buys the most beer
RISING = "優格"  # sells much better in the last four weeks


def pick(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def basket(rng: random.Random, segment: str, city: str, day: datetime) -> list[str]:
    """The product types of one invoice."""
    weights = dict(MISSION_WEIGHTS)
    if city == BEER_CITY:
        weights["snacks"] = 0.45
    mission = pick(rng, weights)
    chances = dict(MISSIONS[mission])
    if city == BEER_CITY and mission == "snacks":
        chances["啤酒"] = 0.8
    if day > AS_OF - timedelta(days=28) and RISING in chances:
        chances[RISING] = 0.7
    tags = [tag for tag, chance in chances.items() if rng.random() < chance]
    # Coffee at breakfast goes with milk, except for loyal customers, who take toast instead.
    if mission == "breakfast" and "咖啡" in tags:
        toast, milk = (0.95, 0.3) if segment == LOYAL else (0.5, 0.95)
        tags = [t for t in tags if t not in ("吐司", "鮮乳")]
        tags += ["吐司"] if rng.random() < toast else []
        tags += ["鮮乳"] if rng.random() < milk else []
    # No empty invoices: the mission's most likely type.
    return tags or [max(chances, key=chances.get)]


def make_rows() -> list[dict]:
    rng = random.Random(SEED)
    users = [(f"U{n:04d}", pick(rng, SEGMENTS), pick(rng, CITIES)) for n in range(1, USERS + 1)]
    rows = []
    for n in range(1, INVOICES + 1):
        user_id, segment, city = rng.choice(users)
        day = AS_OF - timedelta(days=rng.randrange(DAYS), hours=rng.randrange(2, 16))
        for tag in basket(rng, segment, city, day):
            name, brand, price = rng.choice(PRODUCTS[tag])
            unit = rng.choice([1, 1, 1, 2])
            rows.append(
                {
                    "inv_num": f"S{n:06d}",
                    "datetime": day.isoformat(sep=" "),
                    "user_id": user_id,
                    "segment": segment,
                    "county": COUNTY,
                    "city": city,
                    "item_tag": tag,
                    "item_name": name,
                    "item_brand_name": brand,
                    "price": price,
                    "unit": unit,
                    "amount": price * unit,
                }
            )
    return rows


def stats(rows: list[dict]) -> dict:
    """Orders, revenue, shared baskets and lift per product type and pair, in plain Python."""
    baskets: dict[str, set[str]] = {}
    revenue: Counter = Counter()
    for r in rows:
        baskets.setdefault(r["inv_num"], set()).add(r["item_tag"])
        revenue[r["item_tag"]] += r["amount"]
    orders = Counter(tag for tags in baskets.values() for tag in tags)
    shared = Counter(pair for tags in baskets.values() for pair in combinations(sorted(tags), 2))
    lift = {p: n * len(baskets) / (orders[p[0]] * orders[p[1]]) for p, n in shared.items()}
    return {"orders": orders, "revenue": revenue, "shared": shared, "lift": lift}


def top(counter: dict, n: int = 1) -> list:
    return [key for key, _ in sorted(counter.items(), key=lambda kv: -kv[1])[:n]]


def check(rows: list[dict]) -> None:
    """Every planted fact, by golden-question template. A failure means the sample is useless."""
    all_ = stats(rows)
    orders, revenue, shared, lift = all_["orders"], all_["revenue"], all_["shared"], all_["lift"]

    # 1. The top 5 by revenue are not the top 5 by orders.
    assert set(top(revenue, 5)) != set(top(orders, 5))

    # 2. The pair bought together most often is not the two best sellers.
    #    And it leads clearly, so the question has one answer.
    best_sellers = tuple(sorted(top(orders, 2)))
    first, second = top(shared, 2)
    assert first != best_sellers and shared[first] > 1.1 * shared[second]

    # 3. The highest lift of all belongs to a pair too rare for the graph: on the graph, the
    #    highest lift is another pair's.
    solid = {p: v for p, v in lift.items() if shared[p] >= GRAPH_FLOOR}
    assert top(lift)[0] != top(solid)[0]

    # 4. With coffee, loyal customers' top partner differs from everyone's.
    def partner(some_rows: list[dict], tag: str) -> str:
        counts = stats(some_rows)["shared"]
        with_tag = {p: n for p, n in counts.items() if tag in p}
        a, b = top(with_tag)[0]
        return b if a == tag else a

    assert partner(rows, "咖啡") != partner([r for r in rows if r["segment"] == LOYAL], "咖啡")

    # 5. Beer's best district is not the district with the most revenue overall.
    by_city: Counter = Counter()
    beer_by_city: Counter = Counter()
    for r in rows:
        by_city[r["city"]] += r["amount"]
        if r["item_tag"] == "啤酒":
            beer_by_city[r["city"]] += r["amount"]
    assert top(beer_by_city)[0] == BEER_CITY != top(by_city)[0]

    # 6. Yoghurt revenue in the last 4 weeks is well above the 4 before.
    def window(first_day: int, last_day: int) -> int:
        start, end = AS_OF - timedelta(days=last_day), AS_OF - timedelta(days=first_day)
        return sum(
            r["amount"]
            for r in rows
            if r["item_tag"] == RISING and start < datetime.fromisoformat(r["datetime"]) <= end
        )

    assert window(0, 28) > 1.3 * window(28, 56)

    # 7. The type that connects the most others (betweenness, the graph's pairs above chance) is
    #    not the best seller.
    graph = nx.Graph(p for p, v in solid.items() if v > 1)
    #    And it leads clearly, so the question has one answer.
    between = nx.betweenness_centrality(graph)
    hub, runner_up = top(between, 2)
    assert hub != top(orders)[0] and between[hub] > 1.5 * between[runner_up]

    # 9. The two best sellers share enough baskets to be on the graph, yet fewer than chance
    #    predicts.
    assert shared[best_sellers] >= GRAPH_FLOOR + 10 and lift[best_sellers] < 1


def main() -> None:
    rows = make_rows()
    check(rows)
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{OUT}: {len(rows)} lines, {INVOICES} invoices")


if __name__ == "__main__":
    main()
