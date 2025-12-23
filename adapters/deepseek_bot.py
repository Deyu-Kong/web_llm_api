# adapters/deepseek_bot.py
import time
from .base_bot import BaseBot
from config import STABLE_WAIT_TIME, CHECK_INTERVAL, MAX_WAIT_TIME

DEEPSEEK_URL = "https://chat.deepseek.com"


class DeepSeekBot(BaseBot):
    """
    DeepSeek (chat.deepseek.com) 网页机器人
    支持深度思考模式
    """
    
    def __init__(self, page=None, tab=None):
        super().__init__(page, tab)
        self.name = "DeepSeek"
        self.url = DEEPSEEK_URL

    def activate(self) -> bool:
        """激活标签页"""
        try:
            if self.tab:
                self.tab.set.activate()
                if "deepseek.com" not in self.tab.url:
                    self.tab.get(self.url)
                    time.sleep(2)
                return True
            
            if self.page:
                for tab in self.page.get_tabs():
                    if "deepseek.com" in tab.url:
                        self.tab = tab
                        self.tab.set.activate()
                        return True
                
                self.tab = self.page.latest_tab
                self.tab.get(self.url)
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
            # 主要选择器：基于 placeholder
            'css:textarea[placeholder*="DeepSeek"]',
            'css:textarea[placeholder*="发送消息"]',
            'tag:textarea',
        ]
        
        for sel in selectors:
            try:
                ele = self.tab.ele(sel, timeout=2)
                if ele:
                    return ele
            except:
                continue
        return None

    def _get_last_answer(self) -> dict:
        """获取最后回答（区分思考和回答）"""
        result = {"thought": "", "answer": ""}
        if not self.tab:
            return result
        
        try:
            messages = self.tab.eles('css:div.ds-message')
            if not messages:
                return result
            
            last = messages[-1]
            
            # 思考部分
            try:
                think = last.ele('css:div.ds-think-content div.ds-markdown', timeout=1)
                if think:
                    result["thought"] = think.text.strip()
            except:
                pass
            
            # 回答部分
            try:
                all_md = last.eles('css:div.ds-markdown')
                for md in all_md:
                    parent_class = ""
                    try:
                        parent_class = md.parent().attr('class') or ""
                    except:
                        pass
                    
                    if "think" not in parent_class.lower():
                        result["answer"] = md.text.strip()
                        break
            except:
                pass
            
            # 最后的备用方案
            if not result["answer"]:
                full = last.text.strip()
                if result["thought"]:
                    result["answer"] = full.replace(result["thought"], "").strip()
                else:
                    result["answer"] = full
                    
        except Exception as e:
            print(f"[{self.name}] 获取回答失败: {e}")
        
        return result

    def _wait_for_response(self) -> dict:
        """等待回答完成"""
        print(f"[{self.name}] ⏳ 等待回答...")
        time.sleep(2)
        
        prev = ""
        stable = 0
        elapsed = 0
        required = int(STABLE_WAIT_TIME / CHECK_INTERVAL)
        
        while elapsed < MAX_WAIT_TIME:
            time.sleep(CHECK_INTERVAL)
            elapsed += CHECK_INTERVAL
            
            current = self._get_last_answer()
            text = current.get("answer", "") + current.get("thought", "")
            
            if text and text == prev:
                stable += 1
                if stable >= required:
                    print(f"[{self.name}] ✅ 完成 ({elapsed:.1f}s)")
                    return current
            else:
                stable = 0
            prev = text
        
        print(f"[{self.name}] ⚠️ 超时")
        return self._get_last_answer()

    def ask(self, query: str) -> dict:
        """发送问题并获取回答"""
        if not self.tab and not self.activate():
            return {"thought": "", "answer": "Error: 无法激活标签页"}

        print(f"[{self.name}] 📝 提问: {query[:50]}...")

        try:
            input_box = self._find_input_box()
            if not input_box:
                return {"thought": "", "answer": "Error: 找不到输入框"}
            
            input_box.click()
            time.sleep(0.2)
            input_box.clear()
            input_box.input(query)
            time.sleep(0.5)
            
            self.tab.actions.key_down('Enter').key_up('Enter')
            print(f"[{self.name}] 📤 已发送")
            
            return self._wait_for_response()

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"thought": "", "answer": f"Error: {str(e)}"}

    def new_chat(self) -> bool:
        """开启新对话"""
        try:
            if not self.tab:
                return False
            
            selectors = [
                'tag:div@@text():新对话',
                'tag:span@@text():新对话',
                'tag:button@@text():新对话',
                'css:div[class*="new-chat"]',
                'css:button[class*="new-chat"]',
                # 侧边栏按钮
                'css:div[class*="sidebar"] div[class*="new"]',
                'css:a[class*="new-chat"]',
                # 加号按钮
                'css:div[class*="add-chat"]',
                'css:button[class*="create"]',
            ]
            
            for sel in selectors:
                try:
                    btn = self.tab.ele(sel, timeout=1)
                    if btn:
                        btn.click()
                        time.sleep(1)
                        return True
                except:
                    continue
            
            self.tab.refresh()
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ 新对话失败: {e}")
            return False