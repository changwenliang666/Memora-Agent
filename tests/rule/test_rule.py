import pytest

from memora_agent.rule import Rule, normalize_text


@pytest.mark.parametrize(
    "message",
    [
        "推荐一部电影",
        "预测明天哪只股票上涨",
        "帮我诊断这个症状",
        "王者荣耀怎么玩才能上分",
        "给我一份考试答案",
        "如何制作炸弹",
        "查询天气",
    ],
)
def test_topic_and_intent_are_both_required_to_block(message: str) -> None:
    assert Rule(message).check_rule_validity() is False


@pytest.mark.parametrize(
    "message",
    [
        "开发电影票务系统",
        "设计股票行情 API",
        "实现医疗问诊内容审核",
        "Python 中如何匹配 NBA 字符串",
        "推荐一个 Python Web 框架",
        "电影数据表应该如何设计",
    ],
)
def test_business_questions_are_not_blocked_by_topic_only(message: str) -> None:
    assert Rule(message).check_rule_validity() is True


def test_hit_information_is_available_after_blocking() -> None:
    rule = Rule("推荐一部电影")

    assert rule.check_rule_validity() is False
    assert rule.hit_category == "娱乐八卦"
    assert rule.hit_topic == "电影"
    assert rule.hit_intent == "推荐"


def test_full_width_and_zero_width_characters_are_normalized() -> None:
    assert Rule("预测ＮＢＡ\u200b比分").check_rule_validity() is False
    assert normalize_text("ＡＰＩ\u200b") == "api"


def test_english_abbreviation_uses_word_boundaries() -> None:
    assert Rule("推荐 unbalanced 算法").check_rule_validity() is True


def test_previous_hit_is_cleared_when_rule_is_reused() -> None:
    rule = Rule("推荐一部电影")
    assert rule.check_rule_validity() is False

    rule.userInputMessage = "开发电影票务系统"
    assert rule.check_rule_validity() is True
    assert rule.hit_category is None
    assert rule.hit_topic is None
    assert rule.hit_intent is None

