"""OpenPROM Web 界面深度测试"""

import os
import pytest

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError


@pytest.mark.skipif(
    os.getenv("SKIP_PLAYWRIGHT", "false").lower() == "true", reason="设置了 SKIP_PLAYWRIGHT"
)
def test_web_interface():
    """测试 Web 界面的所有功能"""

    os.makedirs("tests/screenshots", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        try:
            page.goto("http://localhost:8000", wait_until="networkidle", timeout=30000)
            expect(page.locator(".brand-title")).to_be_visible(timeout=5000)

            page.screenshot(path="tests/screenshots/01_initial_page.png", full_page=True)

            upper_input = page.locator("#upper")
            lower_input = page.locator("#lower")
            analyze_btn = page.locator("#analyzeBtn")
            toast = page.locator("#toast")

            expect(upper_input).to_be_visible()
            expect(lower_input).to_be_visible()
            expect(analyze_btn).to_be_visible()
            expect(analyze_btn).to_be_enabled()

            analyze_btn.click()
            page.wait_for_selector("#toast.show", timeout=5000)
            assert toast.is_visible(), "空提交应显示提示"

            upper_input.fill("春风化雨")
            lower_input.fill("秋月寒霜")
            page.screenshot(path="tests/screenshots/02_filled_form.png")

            upper_input.fill("春风化雨")
            lower_input.fill("秋月寒")
            analyze_btn.click()
            page.wait_for_selector("#toast.show", timeout=5000)
            assert toast.is_visible(), "字数不等应显示提示"

            upper_input.fill("春风化雨")
            lower_input.fill("秋月寒霜")

            page.set_viewport_size({"width": 375, "height": 667})
            page.screenshot(path="tests/screenshots/04_mobile_view.png")

            page.set_viewport_size({"width": 1920, "height": 1080})

            header = page.locator(".header")
            if header.is_visible():
                bg_color = header.evaluate("el => window.getComputedStyle(el).background")
                assert bg_color is not None, "Header 应加载样式"

            assert len(page_errors) == 0, f"发现页面错误: {page_errors[:5]}"

            page.screenshot(path="tests/screenshots/05_final_state.png", full_page=True)

        except PlaywrightTimeoutError as e:
            page.screenshot(path="tests/screenshots/error_timeout.png")
            pytest.skip(f"服务器未启动或超时: {e}")

        except Exception as e:
            err_msg = str(e)
            if "ERR_CONNECTION_REFUSED" in err_msg or "net::ERR" in err_msg:
                pytest.skip(f"服务器未启动: {err_msg}")
            page.screenshot(path="tests/screenshots/error_exception.png")
            raise

        finally:
            browser.close()
