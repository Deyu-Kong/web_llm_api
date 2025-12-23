# adapters/__init__.py
from .base_bot import BaseBot
from .kimi_bot import KimiBot
from .lmarena_bot import LMArenaBot
from .yuanbao_bot import YuanbaoBot
from .deepseek_bot import DeepSeekBot

__all__ = [
    "BaseBot",
    "KimiBot", 
    "LMArenaBot",
    "YuanbaoBot",
    "DeepSeekBot",
]