"""PORM Web 界面深度测试"""

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError
import time


def test_web_interface():
    """测试 Web 界面的所有功能"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        # 启用控制台日志捕获
        console_messages = []
        page.on('console', lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        
        # 捕获页面错误
        page_errors = []
        page.on('pageerror', lambda err: page_errors.append(str(err)))
        
        try:
            print("\n=== 步骤 1: 访问首页 ===")
            page.goto('http://localhost:8000', wait_until='networkidle', timeout=30000)
            print(f"页面标题：{page.title()}")
            
            # 等待页面加载完成
            page.wait_for_load_state('domcontentloaded')
            time.sleep(2)
            
            # 截图
            page.screenshot(path='tests/screenshots/01_initial_page.png', full_page=True)
            print("✓ 初始页面截图已保存")
            
            print("\n=== 步骤 2: 检查页面元素 ===")
            
            # 检查标题
            logo = page.locator('.logo-title')
            expect(logo).to_be_visible(timeout=5000)
            print(f"✓ Logo 可见：{logo.inner_text()}")
            
            # 检查输入框
            upper_input = page.locator('#upper')
            lower_input = page.locator('#lower')
            expect(upper_input).to_be_visible()
            expect(lower_input).to_be_visible()
            print("✓ 上下联输入框可见")
            
            # 检查按钮
            analyze_btn = page.locator('#analyzeBtn')
            expect(analyze_btn).to_be_visible()
            expect(analyze_btn).to_be_enabled()
            print(f"✓ 评鉴按钮可见：{analyze_btn.inner_text()}")
            
            print("\n=== 步骤 3: 测试表单验证 ===")
            
            # 测试空提交
            analyze_btn.click()
            time.sleep(1)
            
            # 检查是否有错误提示
            toast = page.locator('#toast')
            if toast.is_visible():
                print(f"✓ 空提交验证通过：{toast.inner_text()}")
            
            print("\n=== 步骤 4: 输入测试数据 ===")
            
            # 输入测试对联
            test_upper = "春风化雨"
            test_lower = "秋月寒霜"
            
            upper_input.fill(test_upper)
            lower_input.fill(test_lower)
            print(f"✓ 输入上联：{test_upper}")
            print(f"✓ 输入下联：{test_lower}")
            
            # 截图
            page.screenshot(path='tests/screenshots/02_filled_form.png')
            print("✓ 填写表单截图已保存")
            
            print("\n=== 步骤 5: 测试字数不等验证 ===")
            
            # 测试字数不等
            upper_input.fill("春风化雨")
            lower_input.fill("秋月寒")
            analyze_btn.click()
            time.sleep(1)
            
            if toast.is_visible():
                toast_text = toast.inner_text()
                print(f"✓ 字数不等验证：{toast_text}")
            
            # 恢复正确输入
            upper_input.fill(test_upper)
            lower_input.fill(test_lower)
            
            print("\n=== 步骤 6: 检查加载状态 ===")
            
            # 点击评鉴按钮（不实际调用 API，只检查 UI）
            # 由于没有真实 API 密钥，我们只检查 UI 状态变化
            
            analyze_btn.click()
            time.sleep(2)
            
            # 检查是否有加载状态或错误
            loading_section = page.locator('#loadingSection')
            result_section = page.locator('#resultSection')
            
            if loading_section.is_visible():
                print("✓ 加载状态显示正常")
                page.screenshot(path='tests/screenshots/03_loading.png')
            
            print("\n=== 步骤 7: 检查控制台错误 ===")
            
            # 等待一段时间收集控制台消息
            time.sleep(3)
            
            if console_messages:
                errors = [msg for msg in console_messages if 'error' in msg.lower()]
                if errors:
                    print(f"⚠ 发现 {len(errors)} 条错误消息:")
                    for err in errors[:5]:
                        print(f"  - {err}")
                else:
                    print("✓ 控制台无错误")
            else:
                print("✓ 无控制台消息")
            
            if page_errors:
                print(f"❌ 发现 {len(page_errors)} 个页面错误:")
                for err in page_errors[:5]:
                    print(f"  - {err}")
            else:
                print("✓ 无页面 JavaScript 错误")
            
            print("\n=== 步骤 8: 检查响应式设计 ===")
            
            # 测试移动端视图
            context.set_viewport_size({'width': 375, 'height': 667})
            time.sleep(1)
            page.screenshot(path='tests/screenshots/04_mobile_view.png')
            print("✓ 移动端视图截图已保存")
            
            # 恢复桌面视图
            context.set_viewport_size({'width': 1920, 'height': 1080})
            
            print("\n=== 步骤 9: 检查 CSS 样式加载 ===")
            
            # 检查关键样式
            header = page.locator('.header')
            if header.is_visible():
                bg_color = header.evaluate('el => window.getComputedStyle(el).background')
                print(f"✓ Header 背景样式：{bg_color}")
            
            # 检查字体加载
            logo_font = logo.evaluate('el => window.getComputedStyle(el).fontFamily')
            print(f"✓ Logo 字体：{logo_font}")
            
            print("\n=== 步骤 10: 检查所有可见元素 ===")
            
            # 列出所有可见的按钮和链接
            buttons = page.locator('button').all()
            print(f"✓ 发现 {len(buttons)} 个按钮")
            
            links = page.locator('a').all()
            print(f"✓ 发现 {len(links)} 个链接")
            
            inputs = page.locator('input, textarea').all()
            print(f"✓ 发现 {len(inputs)} 个输入框")
            
            print("\n=== 测试完成 ===")
            print(f"总控制台消息：{len(console_messages)}")
            print(f"总页面错误：{len(page_errors)}")
            
            # 最终截图
            page.screenshot(path='tests/screenshots/05_final_state.png', full_page=True)
            print("✓ 最终状态截图已保存")
            
            # 测试结果总结
            if page_errors:
                print("\n❌ 测试失败 - 发现页面错误")
                return False
            else:
                print("\n✅ 测试通过 - 界面无错误")
                return True
                
        except PlaywrightTimeoutError as e:
            print(f"❌ 超时错误：{e}")
            page.screenshot(path='tests/screenshots/error_timeout.png')
            return False
            
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            page.screenshot(path='tests/screenshots/error_exception.png')
            return False
            
        finally:
            browser.close()
            print("\n浏览器已关闭")


if __name__ == '__main__':
    import os
    
    # 创建截图目录
    os.makedirs('tests/screenshots', exist_ok=True)
    
    # 运行测试
    success = test_web_interface()
    exit(0 if success else 1)
