# adapters/base_bot.py
from abc import ABC, abstractmethod

class BaseBot(ABC):
    """
    所有网页机器人的抽象基类
    定义了统一的接口规范
    """
    
    def __init__(self, page):
        self.page = page
        self.tab = None
        self.name = "BaseBot"

    @abstractmethod
    def activate(self) -> bool:
        """
        激活或跳转到对应的标签页
        返回: 是否成功激活
        """
        pass

    @abstractmethod
    def ask(self, query: str) -> str:
        """
        发送问题并获取答案
        参数: query - 用户问题
        返回: 模型回答的文本
        """
        pass

    @abstractmethod
    def new_chat(self) -> bool:
        """
        开启新对话（清除上下文）
        返回: 是否成功
        """
        pass