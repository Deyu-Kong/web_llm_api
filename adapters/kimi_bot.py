# adapters/kimi_bot.py
import time
from .base_bot import BaseBot
from config import KIMI_URL, STABLE_WAIT_TIME, CHECK_INTERVAL, MAX_WAIT_TIME


class KimiBot(BaseBot):
    """Kimi 网页机器人 - 支持多标签页并行"""
    
    def __init__(self, page=None, tab=None):
        super().__init__(page, tab)
        self.name = "Kimi"
        self.url = KIMI_URL

    def activate(self) -> bool:
        """激活标签页"""
        try:
            # 如果已有 tab，直接激活
            if self.tab:
                self.tab.set.activate()
                
                # 检查 URL 是否正确
                if self.url not in self.tab.url:
                    self.tab.get(self.url)
                    time.sleep(2)
                
                print(f"[{self.name}] ✅ 标签页已激活")
                return True
            
            # 单例模式：从浏览器查找或创建
            if self.page:
                tabs = self.page.get_tabs()
                for tab in tabs:
                    if self.url in tab.url:
                        self.tab = tab
                        self.tab.set.activate()
                        return True
                
                # 未找到，打开新页面
                self.tab = self.page.latest_tab
                self.tab.get(self.url)
                
                # 等待页面加载
                time.sleep(2)
                return True
            
            return False
            
        except Exception as e:
            print(f"[{self.name}] ❌ 激活失败: {e}")
            return False

    def _find_input_box(self):
        """定位输入框"""
        if not self.tab:
            return None
            
        selectors = [
            'tag:div@@contenteditable=true',
            'css:[data-testid="chat-input"]',
            'css:div[class*="editor"]@@contenteditable=true',
            'css:div[placeholder]@@contenteditable=true',
        ]
        
        for selector in selectors:
            try:
                ele = self.tab.ele(selector, timeout=2)
                if ele:
                    return ele
            except:
                continue
        return None

    def _get_last_answer(self) -> str:
        """获取最后一条回答的文本"""
        if not self.tab:
            return ""
            
        selectors = [
            'css:div[class*="markdown"]',
            'css:div[data-testid="message-content"]',
            'css:div[class*="message-content"]',
        ]
        
        for selector in selectors:
            try:
                answers = self.tab.eles(selector)
                if answers:
                    return answers[-1].text.strip()
            except:
                continue
        
        return ""

    def _wait_for_response(self) -> str:
        """等待回答生成完成"""
        print(f"[{self.name}] ⏳ 等待回答...")
        time.sleep(2)
        
        prev_text = ""
        stable_count = 0
        elapsed = 0
        required = int(STABLE_WAIT_TIME / CHECK_INTERVAL)
        
        while elapsed < MAX_WAIT_TIME:
            time.sleep(CHECK_INTERVAL)
            elapsed += CHECK_INTERVAL
            
            current = self._get_last_answer()
            
            if current and current == prev_text:
                stable_count += 1
                if stable_count >= required:
                    print(f"[{self.name}] ✅ 完成 ({elapsed:.1f}s)")
                    return current
            else:
                stable_count = 0
            
            prev_text = current
        
        print(f"[{self.name}] ⚠️ 超时")
        return prev_text

    def ask(self, query: str) -> str:
        """发送问题并获取回答"""
        if not self.tab and not self.activate():
            return "Error: 无法激活标签页"

        print(f"[{self.name}] 📝 提问: {query[:50]}...")

        try:
            # 1. 定位输入框
            input_box = self._find_input_box()
            if not input_box:
                return "Error: 找不到输入框"
            
            # 2. 清空并输入问题
            input_box.clear()
            input_box.input(query)
            time.sleep(0.5)
            
            # 3. 按回车发送
            self.tab.actions.key_down('Enter').key_up('Enter')
            print(f"[{self.name}] 📤 已发送")
            
            # 4. 等待并获取回答
            answer = self._wait_for_response()
            return answer if answer else "Error: 未获取到回答"

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"

    def new_chat(self) -> bool:
        """开启新对话"""
        try:
            if not self.tab:
                return False
            
            selectors = [
                'css:div[class*="new-chat"]',
                'tag:button@@text():新对话',
            ]
            
            for selector in selectors:
                try:
                    btn = self.tab.ele(selector, timeout=1)
                    if btn:
                        btn.click()
                        time.sleep(1)
                        return True
                except:
                    continue
            
            # 刷新页面作为备选
            self.tab.refresh()
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ 新对话失败: {e}")
            return False