"""The writer: the slogans for the strategist's campaigns, a few per campaign to choose from.

It decides nothing about an offer. The strategist has fixed what is bundled, the discount and
the audience, and the reviewer has checked them; the writer only words them. So it can run on
another model than the careful roles, and its check is small: a
slogan may not promise a number the campaign does not offer, or name a product type the user
has set aside.
"""

import json
import logging
import os
import re
from collections.abc import Sequence

from agents import Agent, Runner
from pydantic import BaseModel

from app.infra import progress
from app.roles.reviewer import written
from app.roles.strategist import Campaign, Strategy

# It can write a pun on a sound, which gpt-4o could not: see evals/writer-puns.md. No temperature
# is set: this model refuses any but the default (1.2 was tried), and gpt-4o came out garbled
# at 1.1. The slogans' variety has to come from the voices in the rules.
MODEL = "gpt-5.6-luna"
SLOGANS = 3  # asked for, per campaign
MAX_SLOGANS = 4  # kept, per campaign

RULES = """\
You are the copywriter of Constella AI. A strategist has drafted campaigns for one retail store.
Write {slogans} slogans for each: one line a shopper would see on a shelf tag or a banner.

- Write in the language of the user's question.
- Make the {slogans} really differ, each in its own voice. Not the same line reworded.
  1. A pun on a sound (a 諧音梗): see below.
  2. Cheeky: the way a friend, or the shop's own social post, would say it out loud. Spoken
     words, some attitude, a wink.
  3. A moment: one small scene the shopper knows from their own day, with something in it to
     see or feel. The products belong in the scene; the line does not explain them.
- None of them is there to state the offer: the discount and the products are printed next to
  the slogan. A line that only names the products and the discount is a label, not a slogan.
- Short: a line to read at a glance. No hashtags, no emoji, no quotation marks.
- The offer is fixed. Never promise anything it does not give: no free item, no gift, no other
  price. The only number a slogan may carry is the campaign's own discount. A 折 counts what
  is left to pay: 20% off is 8折, and 15% off is 85折, never 20折 or 15折.
- A campaign whose `basis` is "potential" is an untested combination: do not call it a
  favourite, a best seller or what everyone buys.
- You may name the campaign's product types, and no others.

The pun (諧音梗): a word in a phrase everyone knows is swapped for one that sounds the same or
nearly the same, so the line reads two ways at once.
- Work it out in `sounds` before you write. For each of the campaign's product types, and for
  the offer's own words (the discount, the bundle), list words that sound alike, and the
  idioms, sayings or everyday phrases one of them could be swapped into. Go by how the words
  are said aloud, syllable by syllable, not by how they are written.
- In Chinese, the sounds are those of Mandarin as spoken in Taiwan. A phrase from Taiwanese
  (台語) that every shopper there knows is fair game too. In another language, pun on that
  language's own sounds.
- Then build the slogan on the best one: take the phrase everyone knows and write the
  product's word into it, in place of the word it sounds like. The swap has to be heard at
  once, and the line has to still say something about the offer.
- `pun`: the swap, as "what is written ≈ what is heard", so it can be checked. What is written
  must be in the slogan, word for word. Null for the other slogans.
- If nothing in `sounds` really sounds alike, write another cheeky slogan or another moment in
  its place and leave `pun` null. A forced pun is worse than none.

Examples, from another store:
- mango: 再芒也要吃芒果 (pun: 芒 ≈ 忙, from 再忙也要…)
- pens: 筆較過才知道划算 (pun: 筆較 ≈ 比較)
- socks: 襪！這個價格太可以 (pun: 襪 ≈ 哇)
- shrimp: 買蝦米都划算 (pun: 蝦米 ≈ 啥米, Taiwanese for 什麼)
- cheeky, instant noodles and eggs: 加班的宵夜，不加蛋怎麼行
- cheeky, ice cream: 熱成這樣，不吃一支說不過去
- a moment, coffee: 鬧鐘響到第三次，還好咖啡已經在等
- a moment, umbrellas: 下班那場雨，剛好躲進同一把傘
Do not reuse them.

Return the campaigns in the order given, each with its `campaign` name exactly as given.
"""


class Slogan(BaseModel):
    text: str
    # For a pun on a sound: the swap, e.g. "芒 ≈ 忙". None for a slogan with no pun.
    pun: str | None


class Lines(BaseModel):
    """What the writer writes for one campaign."""

    campaign: str
    # Its working: the words that sound alike, found before the slogans are written. The model
    # does not reason before it answers, so this is where it does. Not sent to the app.
    sounds: list[str]
    slogans: list[Slogan]


class Copy(BaseModel):
    campaigns: list[Lines]


class Pitch(Campaign):
    """A campaign with the slogans to choose from. Empty when the writer did not run."""

    slogans: list[Slogan]


class Pitched(Strategy):
    """The strategist's options, each with its slogans: what the app shows."""

    campaigns: list[Pitch]


# A discount written as 折, the share left to pay, in digits or in Chinese numerals: 8折, 八五折.
FOLD = re.compile(r"(\d+(?:\.\d+)?|[一二三四五六七八九十]+)\s*折")
DIGITS = {numeral: str(digit) for digit, numeral in enumerate("一二三四五六七八九", 1)}


def slogan_problems(slogan: Slogan, campaign: Campaign, ignored: Sequence[str] = ()) -> list[str]:
    """Why a slogan cannot go out; empty when it can. Code, no model."""
    problems = []
    text = slogan.text
    off = campaign.discount_percent
    for fold in FOLD.findall(text):
        # 八五 reads digit by digit, as 85. With a 十 it is not a 折 anyone writes.
        left = "".join(DIGITS.get(c, c) for c in fold)
        if "十" in left or float(left) not in ((100 - off) / 10, 100 - off):
            problems.append(f"{fold}折 is not {off}% off.")
    allowed = {off, *written(" ".join([campaign.name, *campaign.items]))}
    for number in written(FOLD.sub(" ", text)):
        if number not in allowed:
            problems.append(f"{number:g} is not the campaign's discount.")
    for name in ignored:
        if name in text:
            problems.append(f"The user has set {name} aside.")
    if slogan.pun is not None:
        # A pun is played in the slogan: the word written there stands in for one it sounds like.
        seen, _, heard = (part.strip() for part in slogan.pun.partition("≈"))
        if not seen or not heard or seen == heard or seen not in text:
            problems.append(f"The slogan does not play the pun {slogan.pun}.")
    return problems


def pitched(strategy: Strategy, slogans: dict[str, list[Slogan]] | None = None) -> Pitched:
    """The strategy with each campaign's slogans, by the campaign's name; none by default."""
    campaigns = [
        Pitch(**c.model_dump(), slogans=(slogans or {}).get(c.name, [])) for c in strategy.campaigns
    ]
    return Pitched(text=strategy.text, campaigns=campaigns, figures=strategy.figures)


async def write(question: str, strategy: Strategy, ignored: Sequence[str] = ()) -> Pitched:
    """The strategy with slogans for each campaign. A slogan that fails its check is left out."""
    agent = Agent(
        name="Constella AI writer",
        instructions=RULES.format(slogans=SLOGANS),
        model=os.environ.get("WRITER_MODEL") or MODEL,
        output_type=Copy,
    )
    offers = [
        c.model_dump(include={"name", "basis", "items", "discount_percent", "audience"})
        for c in strategy.campaigns
    ]
    brief = {"question": question, "campaigns": offers}
    progress.step("writer")
    try:
        result = await Runner.run(agent, json.dumps(brief, ensure_ascii=False))
    except Exception:
        # The campaigns are reviewed and worth sending without slogans.
        logging.exception("The writer failed on %r", question)
        return pitched(strategy)
    drafts = {lines.campaign: lines.slogans for lines in result.final_output.campaigns}
    kept = {
        c.name: [s for s in drafts.get(c.name, []) if not slogan_problems(s, c, ignored)][
            :MAX_SLOGANS
        ]
        for c in strategy.campaigns
    }
    return pitched(strategy, kept)
