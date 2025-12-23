# adapters/lmarena_bot.py
"""
LMArena 适配器 - 支持多标签页并发
"""

import time
from .base_bot import BaseBot
from config import LMARENA_URL, STABLE_WAIT_TIME, CHECK_INTERVAL, MAX_WAIT_TIME

class LMArenaBot(BaseBot):
    """
    LMArena (lmarena.ai) 网页机器人
    支持直接模式，可指定模型
    支持多标签页并发
    """
    
    def __init__(self, page=None, tab=None, model_name: str = None):
        """
        初始化 LMArena Bot
        
        Args:
            page: DrissionPage 浏览器实例（单例模式）
            tab: 外部提供的标签页（多例/并发模式）
            model_name: 默认使用的模型名称
        """
        super().__init__(page, tab)
        self.name = "LMArena"
        self.url = LMARENA_URL
        self.model_name = model_name  # 指定的默认模型
        self.current_model = None     # 当前选中的模型

    def activate(self) -> bool:
        """激活标签页"""
        try:
            # 多例模式：使用外部提供的 tab
            if self.tab:
                self.tab.set.activate()
                
                # 检查 URL 是否正确，不正确则跳转
                if "lmarena.ai" not in self.tab.url:
                    print(f"[{self.name}] 跳转到 LMArena...")
                    self.tab.get(self.url)
                    time.sleep(3)
                
                print(f"[{self.name}] ✅ 标签页已激活")
                return True
            
            # 单例模式：从浏览器查找或创建
            if self.page:
                tabs = self.page.get_tabs()
                print(f"[{self.name}] 当前浏览器共有 {len(tabs)} 个标签页")
                
                # 查找已有的 LMArena 标签页
                for tab in tabs:
                    if "lmarena.ai" in tab.url:
                        self.tab = tab
                        self.tab.set.activate()
                        print(f"[{self.name}] ✅ 已激活现有标签页")
                        return True
                
                # 未找到，打开新页面
                print(f"[{self.name}] 未找到标签页，正在打开...")
                self.tab = self.page.latest_tab
                self.tab.get(self.url)
                time.sleep(3)
                print(f"[{self.name}] ✅ 已打开 LMArena")
                return True
            
            print(f"[{self.name}] ❌ 未提供 page 或 tab")
            return False
            
        except Exception as e:
            print(f"[{self.name}] ❌ 激活失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _select_model(self, model_name: str) -> bool:
        """
        选择指定的模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            是否成功选择
        """
        if not self.tab:
            return False
        
        try:
            print(f"[{self.name}] 🔍 正在选择模型: {model_name}")
            
            # 1. 点击模型选择按钮
            combobox_selectors = [
                # 'tag:button@@role=combobox',
                # 'css:button[role="combobox"]',
                'css:button[aria-haspopup="dialog"]',
            ]
            
            button = None
            for selector in combobox_selectors:
                try:
                    button = self.tab.ele(selector, timeout=2)
                    if button:
                        print(f"[{self.name}] 找到模型选择按钮")
                        break
                except:
                    continue
            
            if not button:
                print(f"[{self.name}] ⚠️ 未找到模型选择按钮")
                return False
            
            # 使用 JS 点击按钮（避免位置问题）
            try:
                button.click(by_js=True)
            except:
                self.tab.actions.move_to(button).click()
            
            time.sleep(1.5)
            
            # 2. 查找并点击指定模型
            # 尝试多种方式定位模型选项
            model_selectors = [
                f'tag:span@@text()={model_name}',
                f'tag:span@@text():={model_name}',
                f'xpath://span[contains(@class, "truncate") and contains(text(), "{model_name}")]',
                f'css:span.truncate',  # 获取所有选项，然后手动筛选
            ]
            
            model_element = None
            
            # 尝试精确匹配
            for selector in model_selectors:
                try:
                    model_element = self.tab.ele(selector, timeout=2)
                    if model_element:
                        break
                except:
                    continue
            
            # 如果精确匹配失败，获取所有选项并手动查找
            if not model_element:
                try:
                    all_options = self.tab.eles('css:span.truncate', timeout=2)
                    print(f"[{self.name}] 找到 {len(all_options)} 个可选模型")
                    for option in all_options:
                        option_text = option.text.strip()
                        if model_name in option_text or option_text in model_name:
                            model_element = option
                            print(f"[{self.name}] 匹配到模型: {option_text}")
                            break
                except Exception as e:
                    print(f"[{self.name}] 获取模型列表失败: {e}")
            
            if not model_element:
                print(f"[{self.name}] ⚠️ 未找到模型 '{model_name}'")
                self.tab.actions.key_down('Escape').key_up('Escape')
                return False
            
            # 点击选择模型
            try:
                model_element.click(by_js=True)
            except:
                parent = model_element.parent()
                if parent:
                    parent.click(by_js=True)
                else:
                    model_element.click()
            
            time.sleep(0.5)
            
            self.current_model = model_name
            print(f"[{self.name}] ✅ 已选择模型: {model_name}")
            return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ 选择模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_input_box(self):
        """定位输入框"""
        if not self.tab:
            return None
            
        selectors = [
            'tag:textarea@@name=message',
            'css:textarea[name="message"]',
            'css:textarea[placeholder*="Ask"]',
            'tag:textarea',
        ]
        
        for selector in selectors:
            try:
                ele = self.tab.ele(selector, timeout=2)
                if ele:
                    return ele
            except:
                continue
        
        return None

    def _get_last_answer(self) -> dict:
        """
        获取最后一条回答
        
        Returns:
            {"thought": "思考过程", "answer": "实际回答"}
        """
        if not self.tab:
            return {"thought": "", "answer": ""}
        
        try:
            # 查找回答容器
            # 根据 HTML 结构：<div class="no-scrollbar relative flex w-full flex-1 flex-col overflow-x-auto...">
            container_selectors = [
                'css:div.no-scrollbar.relative.flex',
                'css:div[class*="no-scrollbar"][class*="flex-col"]',
            ]
            
            containers = None
            for selector in container_selectors:
                try:
                    containers = self.tab.eles(selector, timeout=2)
                    if containers:
                        break
                except:
                    continue
            
            if not containers:
                return {"thought": "", "answer": ""}
            
            # 获取最后一个回答容器
            last_container = containers[-1]
            
            # 提取思考过程（如果存在）
            thought = ""
            try:
                # <div data-state="open" class="not-prose mb-4">
                thought_div = last_container.ele('css:div.not-prose', timeout=1)
                if thought_div:
                    # 查找思考内容
                    thought_content = thought_div.ele('css:div.space-y-4', timeout=1)
                    if thought_content:
                        thought = thought_content.text.strip()
            except:
                pass
            
            # 提取实际回答
            answer = ""
            try:
                # <div class="prose prose-sm prose-pre:bg-transparent prose-pre:p-0 text-wrap break-words">
                answer_div = last_container.ele('css:div.prose', timeout=1)
                if answer_div:
                    answer = answer_div.text.strip()
            except:
                pass
            
            return {"thought": thought, "answer": answer}
            
        except Exception as e:
            print(f"[{self.name}] 提取回答时出错: {e}")
            return {"thought": "", "answer": ""}

    def _wait_for_response(self) -> dict:
        """等待回答生成完成"""
        print(f"[{self.name}] ⏳ 等待回答...")
        time.sleep(2)
        
        prev_answer = ""
        prev_thought = ""
        stable_count = 0
        elapsed = 0
        required = int(STABLE_WAIT_TIME / CHECK_INTERVAL)
        
        while elapsed < MAX_WAIT_TIME:
            time.sleep(CHECK_INTERVAL)
            elapsed += CHECK_INTERVAL
            
            current = self._get_last_answer()
            current_answer = current["answer"]
            current_thought = current["thought"]
            
            if current_answer and current_answer == prev_answer and current_thought == prev_thought:
                stable_count += 1
                if stable_count >= required:
                    print(f"[{self.name}] ✅ 完成 ({elapsed:.1f}s)")
                    return current
            else:
                stable_count = 0
                if len(current_answer) > len(prev_answer):
                    print(f"[{self.name}] 回答中... (+{len(current_answer) - len(prev_answer)} 字符)")
                elif len(current_thought) > len(prev_thought):
                    print(f"[{self.name}] 思考中... (+{len(current_thought) - len(prev_thought)} 字符)")
            
            prev_answer = current_answer
            prev_thought = current_thought
        
        print(f"[{self.name}] ⚠️ 超时")
        return {"thought": prev_thought, "answer": prev_answer}

    def ask(self, query: str, model_name: str = None) -> dict:
        """
        发送问题并获取回答
        
        Args:
            query: 用户问题
            model_name: 可选，指定使用的模型
            
        Returns:
            {"thought": "思考过程", "answer": "实际回答"}
        """
        if not self.tab and not self.activate():
            return {"thought": "", "answer": "Error: 无法激活标签页"}

        # 切换模型（如果需要）
        target_model = model_name or self.model_name
        if target_model and target_model != self.current_model:
            if not self._select_model(target_model):
                print(f"[{self.name}] ⚠️ 模型选择失败，使用当前模型")

        print(f"[{self.name}] 📝 提问: {query[:50]}...")

        try:
            # 1. 定位输入框
            input_box = self._find_input_box()
            if not input_box:
                return {"thought": "", "answer": "Error: 找不到输入框"}
            
            # 2. 清空并输入问题
            input_box.clear()
            input_box.input(query)
            time.sleep(0.5)
            
            # 3. 按回车发送
            self.tab.actions.key_down('Enter').key_up('Enter')
            print(f"[{self.name}] 📤 已发送")
            
            # 4. 等待并获取回答
            result = self._wait_for_response()
            
            if not result["answer"]:
                return {"thought": result["thought"], "answer": "Error: 未获取到回答"}
            
            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"thought": "", "answer": f"Error: {str(e)}"}

    def new_chat(self) -> bool:
        """开启新对话"""
        try:
            if not self.tab:
                return False
            
            print(f"[{self.name}] 🔄 开启新对话...")
            self.tab.get(self.url)
            time.sleep(2)
            
            # 重置模型状态
            self.current_model = None
            
            print(f"[{self.name}] ✅ 已开启新对话")
            return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ 新对话失败: {e}")
            return False