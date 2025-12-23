# adapters/yuanbao_bot.py
import time
from .base_bot import BaseBot
from config import STABLE_WAIT_TIME, CHECK_INTERVAL, MAX_WAIT_TIME

# 可以在 config.py 中添加，或直接使用默认值
YUANBAO_URL = "https://yuanbao.tencent.com/chat"


class YuanbaoBot(BaseBot):
    """
    腾讯元宝 (yuanbao.tencent.com) 网页机器人
    """
    
    def __init__(self, page):
        super().__init__(page)
        self.name = "Yuanbao"
        self.url = YUANBAO_URL
        self.tab = None

    def activate(self) -> bool:
        """激活或打开腾讯元宝标签页"""
        try:
            tabs = self.page.get_tabs()
            print(f"[{self.name}] 当前浏览器共有 {len(tabs)} 个标签页")
            
            # 查找元宝标签页
            target_tab = None
            for tab in tabs:
                print(f"[{self.name}] 检查标签页: {tab.url}")
                if "yuanbao.tencent.com" in tab.url:
                    target_tab = tab
                    break
            
            if target_tab:
                self.tab = target_tab
                self.tab.set.activate()
                print(f"[{self.name}] ✅ 已激活现有元宝标签页")
                return True
            else:
                print(f"[{self.name}] 未找到元宝标签页，正在打开...")
                self.tab = self.page.latest_tab
                self.tab.get(self.url)
                time.sleep(3)
                print(f"[{self.name}] ✅ 已打开腾讯元宝")
                return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ 激活失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_input_box(self):
        """定位输入框 - 腾讯元宝使用 contenteditable div"""
        if not self.tab:
            return None
            
        selectors = [
            # 主要选择器：基于 class 和 contenteditable
            'css:div.ql-editor[contenteditable="true"]',
            # 备用：基于 placeholder
            'css:div[data-placeholder*="有问题"][contenteditable="true"]',
            # 更通用的备用
            'css:div.ql-editor',
            'tag:div@@contenteditable=true@@class:ql-editor',
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
            'css:#yuanbao-send-btn',
            'css:div.chat-input-send-button',
            'css:button[class*="send"]',
            'css:div[class*="send-btn"]',
            'css:span[class*="send"]',
            # 通过 SVG 图标定位
            'css:div.chat-input-send-button svg',
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
            # 获取所有回复容器
            response_containers = self.tab.eles('css:div.agent-chat__speech-text--box-left')
            
            if not response_containers:
                # 备用选择器
                response_containers = self.tab.eles('css:div[class*="speech-text--box-left"]')
            
            if not response_containers:
                return result
            
            # 取最后一个回复
            last_response = response_containers[-1]
            
            # 尝试提取思考过程
            try:
                think_section = last_response.ele('css:div.hyc-component-reasoner__think-content', timeout=1)
                if think_section:
                    result["thought"] = think_section.text.strip()
            except:
                pass
            
            # 尝试提取最终回答（思考区域之外的 markdown 内容）
            try:
                # 方法1：查找不在思考区域内的 markdown 内容
                all_markdown = last_response.eles('css:div.hyc-content-md')
                
                if all_markdown:
                    # 通常最后一个 markdown 块是最终回答
                    # 或者查找不在 reasoner 区域内的内容
                    for md in all_markdown:
                        # 检查是否在思考区域内
                        parent_classes = ""
                        try:
                            parent = md.parent()
                            if parent:
                                parent_classes = parent.attr('class') or ""
                        except:
                            pass
                        
                        if "think-content" not in parent_classes:
                            answer_text = md.text.strip()
                            if answer_text and answer_text != result["thought"]:
                                result["answer"] = answer_text
                
                # 如果上面方法没找到，尝试其他选择器
                if not result["answer"]:
                    # 查找主要回答区域
                    main_content = last_response.ele('css:div.hyc-common-markdown', timeout=1)
                    if main_content:
                        full_text = main_content.text.strip()
                        # 如果有思考内容，需要去除
                        if result["thought"] and full_text.startswith(result["thought"]):
                            result["answer"] = full_text[len(result["thought"]):].strip()
                        else:
                            result["answer"] = full_text
                            
            except Exception as e:
                print(f"[{self.name}] 提取回答时出错: {e}")
            
            # 如果仍然没有答案，尝试获取整个容器的文本
            if not result["answer"]:
                full_text = last_response.text.strip()
                if result["thought"]:
                    # 移除思考部分
                    result["answer"] = full_text.replace(result["thought"], "").strip()
                else:
                    result["answer"] = full_text
                    
        except Exception as e:
            print(f"[{self.name}] 获取回答失败: {e}")
            
        return result

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
                return {"thought": "", "answer": "Error: 无法激活元宝标签页"}

        print(f"[{self.name}] 📝 正在提问: {query[:50]}...")

        try:
            # 1. 定位输入框
            input_box = self._find_input_box()
            if not input_box:
                return {"thought": "", "answer": "Error: 找不到输入框，请确保已登录腾讯元宝"}
            
            # 2. 点击输入框激活
            input_box.click()
            time.sleep(0.3)
            
            # 3. 清空并输入问题
            # 对于 contenteditable div，使用不同的清空方式
            try:
                # 先全选再删除
                self.tab.actions.key_down('Ctrl').key('a').key_up('Ctrl')
                time.sleep(0.1)
                self.tab.actions.key('Backspace')
                time.sleep(0.1)
            except:
                pass
            
            # 输入新内容
            input_box.input(query)
            time.sleep(0.5)
            
            # 4. 发送消息
            # 方式1：按回车（根据 placeholder 提示：enterkeyhint="send"）
            # self.input_box.actions.key_down('Enter').key_up('Enter')
            # 上面的方法不行换成下面的方法
            btn = self._find_send_button()
            btn.click()
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
            
            # 腾讯元宝的新对话按钮选择器
            new_chat_selectors = [
                'css:div[class*="new-chat"]',
                'css:button[class*="new"]',
                'css:div[class*="create-chat"]',
                'tag:span@@text():新对话',
                'tag:div@@text():新对话',
                'css:a[href*="chat"]@@text():新对话',
                # 侧边栏的新建按钮
                'css:div.sidebar-new-chat',
                'css:div[class*="sidebar"]@@text():新对话',
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