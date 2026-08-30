few_shot_examples = [
    {
        "input": "李文忠是谁，他的主要功绩是什么？",
        "output": '{"intent": "history", "confidence": "high"}',
    },
    {
        "input": "今天深圳天气怎么样？",
        "output": '{"intent": "weather", "confidence": "high"}',
    },
    {
        "input": "怎么用 Python 写 FastAPI？",
        "output": '{"intent": "other", "confidence": "high"}',
    },
    {
        "input": "今天北京天气怎么样？ 现在几点了？",
        "output": '{"intent": "weather", "confidence": "medium"}',
    },
    {
        "input": "李文忠是谁，他的主要功绩是什么？深圳有哪些好玩的地方？",
        "output": '{"intent": "history", "confidence": "medium"}',
    },
    {
        "input": "帮我看看那个",
        "output": '{"intent": "other", "confidence": "low"}',
    },
    {
        "input": "赤壁之战那天刮的是什么风？",
        "output": '{"intent": "history", "confidence": "low"}',
    },
    {
        "input": "最近感觉要变天了",
        "output": '{"intent": "other", "confidence": "low"}',
    },
]