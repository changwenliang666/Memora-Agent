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
        "input": "这个东西我不想要了，因为他是历史书，我喜欢天气类的书籍",
        "output": '{"intent": "other", "confidence": "high"}',
    },
    {
        "input": "我很喜欢晴天题材的小说，推荐几本吧",
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
    {
        "input":"刚刚的回答我觉得不够严谨，请重新组织语言再回答一次",
        "output": '{"intent": "regenerate", "confidence": "high"}',
    },
    {
        "input":"把我们刚刚讨论的内容，总结一下",
        "output": '{"intent": "summary", "confidence": "high"}',
    },
    {
        "input":"我觉得你刚才的回答不够准确，请重新回答一次",
        "output": '{"intent": "regenerate", "confidence": "high"}',
    },
    {
        "input":"我刚刚说的内容，你再总结一下",
        "output": '{"intent": "summary", "confidence": "high"}',
    },
    {
        "input":"你的回答我并不满意，你在想一想",
        "output": '{"intent": "regenerate", "confidence": "high"}',
    },
    {
        "input":"我觉得你在胡言乱语，请重新回答一次",
        "output": '{"intent": "regenerate", "confidence": "high"}',
    },
    {
        "input":"我今天很高兴，谢谢你",
        "output": '{"intent": "mood", "confidence": "high"}',
    },
    {
        "input":"我今天很悲伤，谢谢你",
        "output": '{"intent": "mood", "confidence": "high"}',
    },
    {
        "input":"最近总觉得很难过，想找人聊聊",
        "output": '{"intent": "mood", "confidence": "high"}',
    },
    {
        "input":"我今天很无聊，谢谢你",
        "output": '{"intent": "mood", "confidence": "high"}',
    },
    {
        "input":"你好，你能帮我解决什么问题",
        "output": '{"intent": "help", "confidence": "high"}',
    },
    {
        "input":"有个问题我想知道怎么解决",
        "output": '{"intent": "other", "confidence": "low"}',
    },
    {
        "input":"哈哈哈，你这个回复还蛮有意思的",
        "output": '{"intent": "mood", "confidence": "high"}',
    },
    {
        "input":"你好，你是谁",
        "output": '{"intent": "help", "confidence": "high"}',
    },
    {
        "input":"这几部电影,哪个好看",
        "output": '{"intent": "other", "confidence": "high"}',
    },
    {
        "input":"这几个汽车,哪个更适合我",
        "output": '{"intent": "other", "confidence": "high"}',
    },
    {
        "input":"我讨厌这本历史书，换一本天气科普书吧",
        "output": '{"intent": "other", "confidence": "high"}',
    },
    {
        "input":"请推荐三款预算一万以内的笔记本电脑",
        "output": '{"intent": "other", "confidence": "high"}',
    },
    {
        "input":"把刚刚那段话总结成三点，再重写得更口语一点",
        "output": '{"intent": "summary", "confidence": "medium"}',
    },
    {
        "input":"把上一条回答重写一下，另外告诉我今天广州天气",
        "output": '{"intent": "regenerate", "confidence": "medium"}',
    },
    {
        "input":"你能做什么，顺便把上一条回答再说一遍",
        "output": '{"intent": "help", "confidence": "medium"}',
    },
    {
        "input":"我很烦，但先帮我总结一下刚才的内容",
        "output": '{"intent": "summary", "confidence": "medium"}',
    },
    {
        "input":"我心情不太好，另外你是谁",
        "output": '{"intent": "mood", "confidence": "medium"}',
    },
    {
        "input":"你会什么",
        "output": '{"intent": "help", "confidence": "low"}',
    },
    {
        "input":"帮我重新来一版",
        "output": '{"intent": "regenerate", "confidence": "low"}',
    },
    {
        "input":"给我总结下那个",
        "output": '{"intent": "summary", "confidence": "low"}',
    },
    {
        "input":"最近有点烦",
        "output": '{"intent": "mood", "confidence": "high"}',
    },
    {
        "input":"我想知道《明朝那些事儿》讲了什么",
        "output": '{"intent": "other", "confidence": "high"}',
    },
    {
        "input":"天气真好这本书讲什么",
        "output": '{"intent": "other", "confidence": "high"}',
    },
    {
        "input":"赤壁之战发生在什么时候",
        "output": '{"intent": "history", "confidence": "high"}',
    },
    {
        "input":"我说的那个事情你懂的",
        "output": '{"intent": "other", "confidence": "low"}',
    },
    {
        "input":"我心情很糟糕，你能为我做什么",
        "output": '{"intent": "help", "confidence": "low"}',
    }
]

review_few_shot_examples = [
    {
        "input": "今天北京天气怎么样？ 现在几点了？",
        "intent": "weather",
        "confidence": "medium",
        "output": '{"intent": "weather", "confidence": "medium", "review_opinion": "主问题是查天气，但还包含独立的时间询问，维持 weather/medium。"}',
    },
    {
        "input": "李文忠是谁，他的主要功绩是什么？深圳有哪些好玩的地方？",
        "intent": "history",
        "confidence": "medium",
        "output": '{"intent": "history", "confidence": "medium", "review_opinion": "主问题是历史人物，但还包含独立的旅行询问，维持 history/medium。"}',
    },
    {
        "input": "赤壁之战那天刮的是什么风？",
        "intent": "history",
        "confidence": "low",
        "output": '{"intent": "history", "confidence": "high", "review_opinion": "虽然夹了天气词，但问的是赤壁之战史实，应判 history。"}',
    },
    {
        "input": "帮我看看那个",
        "intent": "other",
        "confidence": "low",
        "output": '{"intent": "other", "confidence": "low", "review_opinion": "指代不清，没有可识别主题，维持 other 且置信度为 low。"}',
    },
    {
        "input": "最近感觉要变天了",
        "intent": "weather",
        "confidence": "medium",
        "output": '{"intent": "other", "confidence": "low", "review_opinion": "只是主观感受，没有查天气的明确意图，改为 other。"}',
    },
    {
        "input": "这个东西我不想要了，因为他是历史书，我喜欢天气类的书籍",
        "intent": "mood",
        "confidence": "medium",
        "output": '{"intent": "other", "confidence": "high", "review_opinion": "用户在表达书籍类型偏好和拒绝，不是在表达当前情绪，也没有查询历史或天气。"}',
    },
    {
        "input": "你到底能回答哪些类型的问题？",
        "intent": "other",
        "confidence": "low",
        "output": '{"intent": "help", "confidence": "high", "review_opinion": "用户明确询问本系统支持的能力范围，应改为 help/high。"}',
    },
    {
        "input": "把刚刚那段话总结成三点，再重写得更口语一点",
        "intent": "summary",
        "confidence": "high",
        "output": '{"intent": "summary", "confidence": "medium", "review_opinion": "包含“总结”和“重写”两个独立动作，主诉求可判 summary，但应降为 medium。"}',
    },
    {
        "input": "把上一条回答重写一下，另外告诉我今天广州天气",
        "intent": "regenerate",
        "confidence": "high",
        "output": '{"intent": "regenerate", "confidence": "medium", "review_opinion": "主诉求是重写上一条回答，同时包含独立天气查询，应判 regenerate/medium。"}',
    },
    {
        "input": "你能做什么，顺便把上一条回答再说一遍",
        "intent": "help",
        "confidence": "high",
        "output": '{"intent": "help", "confidence": "medium", "review_opinion": "主诉求是咨询系统能力，但还包含复述上一条回答的次要诉求，应为 help/medium。"}',
    },
    {
        "input": "我想知道《明朝那些事儿》讲了什么",
        "intent": "history",
        "confidence": "high",
        "output": '{"intent": "other", "confidence": "high", "review_opinion": "用户在询问书籍内容，不是查询真实历史人物或史实，改为 other/high。"}',
    },
    {
        "input": "天气真好这本书讲什么",
        "intent": "weather",
        "confidence": "high",
        "output": '{"intent": "other", "confidence": "high", "review_opinion": "虽然有“天气”关键词，但查询对象是书籍内容，不属于现实天气查询。"}',
    },
    {
        "input": "帮我重新来一版",
        "intent": "regenerate",
        "confidence": "high",
        "output": '{"intent": "regenerate", "confidence": "low", "review_opinion": "用户没有说明重写对象，缺少必要上下文，需澄清，故降为 low。"}',
    },
    {
        "input": "我说的那个事情你懂的",
        "intent": "other",
        "confidence": "high",
        "output": '{"intent": "other", "confidence": "low", "review_opinion": "指代对象不明确，无法确定真实诉求，应判 other/low 以触发澄清。"}',
    },
    {
        "input": "我心情不太好，另外你是谁",
        "intent": "help",
        "confidence": "high",
        "output": '{"intent": "mood", "confidence": "medium", "review_opinion": "主要在表达当前情绪并期待情绪回应，同时带有身份询问次要诉求，应判 mood/medium。"}',
    },
]