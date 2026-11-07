"""The conversation so far, as a model's input. No model."""

from app.roles.conversation import Turn, messages


def test_the_question_comes_after_the_earlier_turns_in_order():
    history = [
        Turn(question="忠誠客戶買吐司時還買什麼？", answer="最常一起買的是鮮乳。"),
        Turn(question="提升度多少？", answer="提升度為 2.1。"),
    ]
    assert messages("那新客戶呢？", history) == [
        {"role": "user", "content": "忠誠客戶買吐司時還買什麼？"},
        {"role": "assistant", "content": "最常一起買的是鮮乳。"},
        {"role": "user", "content": "提升度多少？"},
        {"role": "assistant", "content": "提升度為 2.1。"},
        {"role": "user", "content": "那新客戶呢？"},
    ]


def test_a_first_question_is_alone():
    assert messages("哪一組提升度最高？") == [{"role": "user", "content": "哪一組提升度最高？"}]
