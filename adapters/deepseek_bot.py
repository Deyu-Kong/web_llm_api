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
    
    def __init__(self, page):
        super().__init__(page)
        self.name = "DeepSeek"
        self.url = DEEPSEEK_URL
        self.tab = None

    def activate(self) -> bool:
        """激活或打开 DeepSeek 标签页"""
        try:
            tabs = self.page.get_tabs()
            print(f"[{self.name}] 当前浏览器共有 {len(tabs)} 个标签页")
            
            # 查找 DeepSeek 标签页
            target_tab = None
            for tab in tabs:
                print(f"[{self.name}] 检查标签页: {tab.url}")
                if "chat.deepseek.com" in tab.url or "deepseek.com" in tab.url:
                    target_tab = tab
                    break
            
            if target_tab:
                self.tab = target_tab
                self.tab.set.activate()
                print(f"[{self.name}] ✅ 已激活现有 DeepSeek 标签页")
                return True
            else:
                print(f"[{self.name}] 未找到 DeepSeek 标签页，正在打开...")
                self.tab = self.page.latest_tab
                self.tab.get(self.url)
                time.sleep(3)
                print(f"[{self.name}] ✅ 已打开 DeepSeek")
                return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ 激活失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_input_box(self):
        """定位输入框 - DeepSeek 使用 textarea"""
        if not self.tab:
            return None
            
        selectors = [
            # 主要选择器：基于 placeholder
            'css:textarea[placeholder*="DeepSeek"]',
            'css:textarea[placeholder*="发送消息"]',
            # 基于 class
            'css:textarea._27c9245',
            'css:textarea.d96f2d2a',
            # 通用备用
            'tag:textarea',
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

    def _find_send_button(self):
        """定位发送按钮"""
        if not self.tab:
            return None
            
        selectors = [
            'css:div[class*="send"]',
            'css:button[class*="send"]',
            'css:div[role="button"][class*="send"]',
            # 基于 SVG 的发送图标
            'css:div._9e937ea',
        ]
        
        for selector in selectors:
            try:
                ele = self.tab.ele(selector, timeout=1)
                if ele:
                    print(f"[{self.name}] 找到发送按钮: {selector}")
                    return ele
            except:
                continue
        
        return None

    def _get_last_answer(self) -> dict:
        """
        获取最后一条回答，区分思考过程和最终回答
        返回: {"thought": str, "answer": str}
        """
        if not self.tab:
            return {"thought": "", "answer": ""}
        
        result = {"thought": "", "answer": ""}
        
        try:
            # 获取所有消息容器
            message_containers = self.tab.eles('css:div.ds-message')
            
            if not message_containers:
                return result
            
            # 取最后一个消息（应该是 AI 的回复）
            last_message = message_containers[-1]
            
            # 提取思考过程（在 ds-think-content 区域内）
            try:
                think_section = last_message.ele('css:div.ds-think-content div.ds-markdown', timeout=1)
                if think_section:
                    result["thought"] = think_section.text.strip()
            except:
                pass
            
            # 提取最终回答（直接子级的 ds-markdown，不在 think-content 内）
            try:
                # 获取所有 ds-markdown 元素
                all_markdown = last_message.eles('css:div.ds-markdown')
                
                for md in all_markdown:
                    # 检查父元素是否包含 think-content
                    try:
                        # 获取元素的完整路径来判断
                        parent = md.parent()
                        parent_class = parent.attr('class') or "" if parent else ""
                        
                        # 如果不在思考区域内，就是最终回答
                        if "think-content" not in parent_class and "ds-think" not in parent_class:
                            answer_text = md.text.strip()
                            if answer_text:
                                result["answer"] = answer_text
                                break
                    except:
                        pass
                
                # 备用方法：如果上面没找到，尝试直接获取非思考区域的 markdown
                if not result["answer"]:
                    # DeepSeek 的结构：ds-message > ds-markdown (最终回答在思考区域之后)
                    direct_markdown = last_message.ele('css:div.ds-message > div.ds-markdown', timeout=1)
                    if direct_markdown:
                        result["answer"] = direct_markdown.text.strip()
                        
            except Exception as e:
                print(f"[{self.name}] 提取回答时出错: {e}")
            
            # 最后的备用方案
            if not result["answer"]:
                # 获取整个消息文本，去除思考部分
                full_text = last_message.text.strip()
                if result["thought"]:
                    # 尝试定位思考结束的标记
                    thought_end_markers = ["已思考", "秒）", "思考完成"]
                    for marker in thought_end_markers:
                        if marker in full_text:
                            idx = full_text.rfind(marker)
                            # 找到标记后的换行位置
                            newline_idx = full_text.find("\n", idx)
                            if newline_idx != -1:
                                result["answer"] = full_text[newline_idx:].strip()
                                break
                    
                    # 如果还是没找到，简单地移除思考内容
                    if not result["answer"]:
                        result["answer"] = full_text.replace(result["thought"], "").strip()
                else:
                    result["answer"] = full_text
                    
        except Exception as e:
            print(f"[{self.name}] 获取回答失败: {e}")
            
        return result

    def _is_generating(self) -> bool:
        """检查是否正在生成回答"""
        try:
            # DeepSeek 在生成时可能显示加载动画或特定状态
            loading_indicators = [
                'css:div[class*="loading"]',
                'css:div[class*="generating"]',
                'css:div.cursor-blink',
                'css:span[class*="cursor"]',
            ]
            
            for selector in loading_indicators:
                try:
                    ele = self.tab.ele(selector, timeout=0.5)
                    if ele:
                        return True
                except:
                    continue
                    
            return False
        except:
            return False

    def _wait_for_response(self) -> dict:
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
            
            current_result = self._get_last_answer()
            current_text = current_result.get("answer", "") + current_result.get("thought", "")
            
            if current_text and current_text == prev_text:
                # 额外检查是否还在生成
                if not self._is_generating():
                    stable_count += 1
                    if stable_count >= required_stable_checks:
                        print(f"[{self.name}] ✅ 回答生成完成 (耗时 {elapsed_time:.1f}s)")
                        return current_result
            else:
                stable_count = 0
                if len(current_text) > len(prev_text):
                    new_chars = len(current_text) - len(prev_text)
                    print(f"[{self.name}] 生成中... (+{new_chars} 字符)")
            
            prev_text = current_text
        
        print(f"[{self.name}] ⚠️ 等待超时")
        return self._get_last_answer()

    def ask(self, query: str) -> dict:
        """
        发送问题并获取回答
        返回: {"thought": str, "answer": str}
        """
        if not self.tab:
            if not self.activate():
                return {"thought": "", "answer": "Error: 无法激活 DeepSeek 标签页"}

        print(f"[{self.name}] 📝 正在提问: {query[:50]}...")

        try:
            # 1. 定位输入框
            input_box = self._find_input_box()
            if not input_box:
                return {"thought": "", "answer": "Error: 找不到输入框，请确保已登录 DeepSeek"}
            
            # 2. 点击输入框激活
            input_box.click()
            time.sleep(0.3)
            
            # 3. 清空并输入问题
            input_box.clear()
            time.sleep(0.1)
            input_box.input(query)
            time.sleep(0.5)
            
            # 4. 发送消息（按回车或点击发送按钮）
            # 尝试按回车发送
            self.tab.actions.key_down('Enter').key_up('Enter')
            print(f"[{self.name}] 📤 消息已发送")
            
            # 5. 等待并获取回答
            result = self._wait_for_response()
            
            if not result.get("answer"):
                return {"thought": "", "answer": "Error: 未能获取到回答"}
            
            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"thought": "", "answer": f"Error: {str(e)}"}

    def new_chat(self) -> bool:
        """开启新对话"""
        try:
            if not self.tab:
                self.activate()
            
            # DeepSeek 的新对话按钮选择器
            new_chat_selectors = [
                # 根据你说的"开启新对话的文本"
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