"""敏感词库，按严重程度分级。

LOW：轻度不雅用语 — 自动脱敏（替换为 ***）
MEDIUM：中度敏感内容 — 拦截并返回警告
HIGH：严重违规内容 — 拦截、警告并记录
"""

from app.security.constants import ModerationSeverity

SENSITIVE_WORDS: dict[ModerationSeverity, list[str]] = {
    ModerationSeverity.LOW: [
        "妈的",
        "他妈的",
        "你妈",
        "操你",
        "傻逼",
        "草泥马",
        "特么的",
        "靠",
        "md",
        "m d",
        "fuck",
        "shit",
        "damn",
        "f u c k",
    ],
    ModerationSeverity.MEDIUM: [
        "废物",
        "蠢货",
        "狗屎",
        "去死",
        "混蛋",
        "asshole",
        "bitch",
        "bastard",
        "suck",
    ],
    ModerationSeverity.HIGH: [
        "自杀",
        "自残",
        "杀了他",
        "杀了你",
        "砍死",
        "弄死",
        "贩毒",
        "恐怖袭击",
        "爆炸物",
        "枪支",
        "贩卖",
        "人肉搜索",
        "色情",
        "赌博",
        "毒品",
        "buy gun",
        "kill myself",
        "suicide",
        "bomb",
        "terrorist",
    ],
}
