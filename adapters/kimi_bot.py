# adapters/kimi_bot.py
import time
from .base_bot import BaseBot
from config import KIMI_URL, STABLE_WAIT_TIME, CHECK_INTERVAL, MAX_WAIT_TIME

class KimiBot(BaseBot):
    """
    Kimi (moonshot.cn) 网页机器人
    """
    
    def __init__(self, page):
        super().__init__(page)
        self.name = "Kimi"
        self.url = KIMI_URL
        self.tab = None

    def activate(self) -> bool:
        """激活或打开 Kimi 标签页（在已有浏览器中）"""
        try:
            # 获取当前浏览器的所有标签页
            tabs = self.page.get_tabs()
            print(f"[{self.name}] 当前浏览器共有 {len(tabs)} 个标签页")
            
            # 遍历查找 Kimi 标签页
            target_tab = None
            for tab in tabs:
                print(f"[{self.name}] 检查标签页: {tab.url}")
                if self.url in tab.url:
                    target_tab = tab
                    break
            
            if target_tab:
                # 找到了，激活它
                self.tab = target_tab
                self.tab.set.activate()
                print(f"[{self.name}] ✅ 已激活现有 Kimi 标签页")
                return True
            else:
                # 没找到，在当前浏览器中用 get 方法打开（不是 new_tab）
                # 直接在当前标签页打开 Kimi
                print(f"[{self.name}] 未找到 Kimi 标签页，正在当前浏览器中打开...")
                
                # 获取当前活动标签页
                self.tab = self.page.latest_tab
                self.tab.get(self.url)
                
                # 等待页面加载
                time.sleep(2)
                print(f"[{self.name}] ✅ 已在当前浏览器中打开 Kimi")
                return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ 激活失败: {e}")
            import traceback
            traceback.print_exc()
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
                    print(f"[{self.name}] 找到输入框: {selector}")
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
        print(f"[{self.name}] ⏳ 等待回答生成...")
        
        # 等待回答开始
        time.sleep(2)
        
        prev_text = ""
        stable_count = 0
        elapsed_time = 0
        required_stable_checks = int(STABLE_WAIT_TIME / CHECK_INTERVAL)
        
        while elapsed_time < MAX_WAIT_TIME:
            time.sleep(CHECK_INTERVAL)
            elapsed_time += CHECK_INTERVAL
            
            current_text = self._get_last_answer()
            
            if current_text and current_text == prev_text:
                stable_count += 1
                if stable_count >= required_stable_checks:
                    print(f"[{self.name}] ✅ 回答生成完成 (耗时 {elapsed_time:.1f}s)")
                    return current_text
            else:
                stable_count = 0
                if len(current_text) > len(prev_text):
                    new_chars = len(current_text) - len(prev_text)
                    print(f"[{self.name}] 生成中... (+{new_chars} 字符)")
            
            prev_text = current_text
        
        print(f"[{self.name}] ⚠️ 等待超时")
        return prev_text

    def ask(self, query: str) -> str:
        """发送问题并获取回答"""
        if not self.tab:
            if not self.activate():
                return "Error: 无法激活 Kimi 标签页"

        print(f"[{self.name}] 📝 正在提问: {query[:50]}...")

        try:
            # 1. 定位输入框
            input_box = self._find_input_box()
            if not input_box:
                return "Error: 找不到输入框，请确保已登录 Kimi 并打开对话页面"
            
            # 2. 清空并输入问题
            input_box.clear()
            input_box.input(query)
            time.sleep(0.5)
            
            # 3. 按回车发送
            self.tab.actions.key_down('Enter').key_up('Enter')
            print(f"[{self.name}] 📤 消息已发送")
            
            # 4. 等待并获取回答
            answer = self._wait_for_response()
            
            if not answer:
                return "Error: 未能获取到回答"
            
            return answer

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"

    def new_chat(self) -> bool:
        """开启新对话"""
        try:
            if not self.tab:
                self.activate()
            
            # 尝试点击"新对话"按钮
            new_chat_selectors = [
                'css:div[class*="new-chat"]',
                'tag:button@@text():新对话',
                'css:button[data-testid="new-chat"]',
                'css:span@@text():新对话',
                'css:a.new-chat-btn',
            ]
            
            for selector in new_chat_selectors:
                try:
                    btn = self.tab.ele(selector, timeout=1)
                    if btn:
                        btn.click()
                        time.sleep(1)
                        print(f"[{self.name}] ✅ 已开启新对话")
                        return True
                except:
                    continue
            
            # 找不到按钮就刷新页面
            print(f"[{self.name}] 未找到新对话按钮，刷新页面...")
            self.tab.refresh()
            time.sleep(2)
            print(f"[{self.name}] ✅ 页面已刷新")
            return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ 开启新对话失败: {e}")
            return False