# core/tab_manager.py
"""
标签页池管理器
支持多标签页并行处理请求
"""

import time
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from queue import Queue
from contextlib import contextmanager


@dataclass
class TabInfo:
    """标签页信息"""
    tab: Any                    # DrissionPage Tab 对象
    bot_type: str              # 绑定的 Bot 类型
    in_use: bool = False       # 是否正在使用
    last_used: float = field(default_factory=time.time)
    url: str = ""              # 当前 URL


class TabPoolManager:
    """
    标签页池管理器
    
    功能:
    - 为每个请求分配独立标签页
    - 标签页复用，避免频繁创建
    - 线程安全的资源管理
    - 自动清理闲置标签页
    """
    
    def __init__(self, browser, max_tabs_per_bot: int = 3, tab_timeout: int = 300):
        """
        初始化标签页池
        
        Args:
            browser: DrissionPage 浏览器实例
            max_tabs_per_bot: 每种 Bot 最大标签页数
            tab_timeout: 标签页闲置超时时间（秒）
        """
        self.browser = browser
        self.max_tabs_per_bot = max_tabs_per_bot
        self.tab_timeout = tab_timeout
        
        # 标签页池: {bot_type: [TabInfo, ...]}
        self.pools: Dict[str, list] = {}
        
        # 线程锁
        self.lock = threading.RLock()
        
        # Bot URL 配置
        self.bot_urls = {
            "kimi": "https://kimi.moonshot.cn/",
            "deepseek": "https://chat.deepseek.com/",
            "yuanbao": "https://yuanbao.tencent.com/chat",
            "lmarena": "https://lmarena.ai/",
        }
        
        print(f"[TabPool] 初始化完成，每种 Bot 最大 {max_tabs_per_bot} 个标签页")
    
    def _create_tab(self, bot_type: str) -> TabInfo:
        """创建新标签页"""
        url = self.bot_urls.get(bot_type, "")
        if not url:
            raise ValueError(f"未知的 Bot 类型: {bot_type}")
        
        # 创建新标签页
        tab = self.browser.new_tab(url)
        time.sleep(2)  # 等待页面加载
        
        tab_info = TabInfo(
            tab=tab,
            bot_type=bot_type,
            in_use=True,
            url=url
        )
        
        print(f"[TabPool] 创建新标签页: {bot_type} (共 {self._count_tabs(bot_type) + 1} 个)")
        return tab_info
    
    def _count_tabs(self, bot_type: str) -> int:
        """统计某类型的标签页数量"""
        return len(self.pools.get(bot_type, []))
    
    def _find_available_tab(self, bot_type: str) -> Optional[TabInfo]:
        """查找可用的标签页"""
        pool = self.pools.get(bot_type, [])
        for tab_info in pool:
            if not tab_info.in_use:
                return tab_info
        return None
    
    def acquire_tab(self, bot_type: str) -> TabInfo:
        """
        获取一个可用的标签页
        
        Args:
            bot_type: Bot 类型
            
        Returns:
            TabInfo 对象
        """
        with self.lock:
            # 初始化池
            if bot_type not in self.pools:
                self.pools[bot_type] = []
            
            # 1. 尝试复用空闲标签页
            tab_info = self._find_available_tab(bot_type)
            if tab_info:
                tab_info.in_use = True
                tab_info.last_used = time.time()
                print(f"[TabPool] 复用标签页: {bot_type}")
                return tab_info
            
            # 2. 检查是否可以创建新标签页
            if self._count_tabs(bot_type) < self.max_tabs_per_bot:
                tab_info = self._create_tab(bot_type)
                self.pools[bot_type].append(tab_info)
                return tab_info
            
            # 3. 达到上限，等待复用
            print(f"[TabPool] {bot_type} 标签页已满，等待释放...")
            
        # 在锁外等待（避免死锁）
        while True:
            time.sleep(0.5)
            with self.lock:
                tab_info = self._find_available_tab(bot_type)
                if tab_info:
                    tab_info.in_use = True
                    tab_info.last_used = time.time()
                    print(f"[TabPool] 等待后复用标签页: {bot_type}")
                    return tab_info
    
    def release_tab(self, tab_info: TabInfo):
        """
        释放标签页（标记为可用）
        
        Args:
            tab_info: 要释放的标签页
        """
        with self.lock:
            tab_info.in_use = False
            tab_info.last_used = time.time()
            print(f"[TabPool] 释放标签页: {tab_info.bot_type}")
    
    @contextmanager
    def get_tab(self, bot_type: str):
        """
        上下文管理器：自动获取和释放标签页
        
        用法:
            with tab_pool.get_tab("kimi") as tab_info:
                # 使用 tab_info.tab
        """
        tab_info = self.acquire_tab(bot_type)
        try:
            yield tab_info
        finally:
            self.release_tab(tab_info)
    
    def cleanup_idle_tabs(self):
        """清理闲置超时的标签页"""
        with self.lock:
            now = time.time()
            for bot_type, pool in self.pools.items():
                # 保留至少一个标签页
                if len(pool) <= 1:
                    continue
                
                # 找出闲置超时的标签页
                to_remove = []
                for tab_info in pool:
                    if not tab_info.in_use and (now - tab_info.last_used) > self.tab_timeout:
                        to_remove.append(tab_info)
                
                # 关闭并移除（保留至少一个）
                for tab_info in to_remove[:-1] if len(pool) - len(to_remove) < 1 else to_remove:
                    try:
                        tab_info.tab.close()
                        pool.remove(tab_info)
                        print(f"[TabPool] 清理闲置标签页: {bot_type}")
                    except:
                        pass
    
    def get_stats(self) -> dict:
        """获取标签页池统计信息"""
        with self.lock:
            stats = {}
            for bot_type, pool in self.pools.items():
                in_use = sum(1 for t in pool if t.in_use)
                stats[bot_type] = {
                    "total": len(pool),
                    "in_use": in_use,
                    "available": len(pool) - in_use
                }
            return stats