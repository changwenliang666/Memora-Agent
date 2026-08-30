"""用户输入规则校验。"""

import re
import unicodedata

from memora_agent.rule.policy import ACTION_WORDS, BLOCK_TOPICS


def normalize_text(text: str) -> str:
    """统一全半角、大小写并删除零宽字符。"""
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(
        character
        for character in text
        if unicodedata.category(character) != "Cf"
    )


def _contains_keyword(text: str, keyword: str) -> bool:
    """中文按子串匹配，英文缩写按完整单词匹配。"""
    keyword = normalize_text(keyword)
    if keyword.isascii() and keyword.isalnum():
        return re.search(
            rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])",
            text,
        ) is not None
    return keyword in text


def _first_hit(text: str, keywords: tuple[str, ...]) -> str | None:
    """返回文本中第一个命中的关键词，没有则返回 None。"""
    for word in keywords:
        if _contains_keyword(text, word):
            return word
    return None


class Rule:
    """同时匹配全局动作词和某一类主题词，判断输入是否允许回答。"""

    def __init__(self, userInputMessage: str):
        self.userInputMessage = userInputMessage
        self.hit_category: str | None = None
        self.hit_topic: str | None = None
        self.hit_intent: str | None = None

    def check_rule_validity(self) -> bool:
        """允许回答返回 True，不允许回答返回 False。"""
        text = normalize_text(self.userInputMessage)
        self.hit_category = None
        self.hit_topic = None
        self.hit_intent = None

        # 动作词是全局共用的，先找动作，再找主题。
        intent = _first_hit(text, ACTION_WORDS)
        if intent is None:
            return True

        for category, topics in BLOCK_TOPICS.items():
            topic = _first_hit(text, topics)
            if topic is None:
                continue
            self.hit_category = category
            self.hit_topic = topic
            self.hit_intent = intent
            return False

        return True
