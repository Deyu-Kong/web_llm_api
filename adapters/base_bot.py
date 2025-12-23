# adapters/base_bot.py
from abc import ABC, abstractmethod


class BaseBot(ABC):
    """
    所有网页机器人的抽象基类
    支持两种模式:
    1. 单例模式: 传入 page，自动管理标签页
    2. 多例模式: 传入 tab，使用外部提供的标签页
    """
    
    def __init__(self, page=None, tab=None):
        """
        初始化 Bot
        
        Args:
            page: DrissionPage 浏览器实例（单例模式）
            tab: 外部提供的标签页（多例模式）
        """
        self.page = page
        self.tab = tab
        self.name = "BaseBot"
        self.url = ""

    @abstractmethod
    def activate(self) -> bool:
        """激活/跳转到对应的标签页"""
        pass

    @abstractmethod
    def ask(self, query: str):
        """发送问题并获取答案"""
        pass

    @abstractmethod
    def new_chat(self) -> bool:
        """开启新对话（清除上下文）"""
        pass
    
    def set_tab(self, tab):
        """设置外部标签页"""
        self.tab = tab