"""公众号文章发布服务（Playwright CDP 自动化）"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async

from apps.core.services.browser import create_browser_async

from .auth_handler import capture_qr_code, check_login_status, wait_for_qr_scan
from .markdown_converter import convert_markdown_to_wechat_html

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

    from apps.wechat_mp.models import PublishTask

logger = logging.getLogger(__name__)

# 公众号后台 URL
MP_HOME_URL = "https://mp.weixin.qq.com"


class PublishError(Exception):
    """发布异常"""


class WeChatPublisher:
    """公众号文章发布器（CDP 模式）"""

    def __init__(self, task: PublishTask) -> None:
        self.task = task
        self.account_id = task.account_id
        self.account_name = task.account.name

    async def publish(self) -> dict:
        """执行发布流程。

        Returns:
            包含发布结果的字典

        Raises:
            PublishError: 发布失败时抛出
        """
        try:
            async with create_browser_async("wechat_mp") as (page, context):
                return await self._execute_publish(page, context)
        except PublishError:
            raise
        except Exception as e:
            logger.error("Publish failed for task %d: %s", self.task.pk, e, exc_info=True)
            raise PublishError(f"发布失败: {e}") from e

    async def _execute_publish(self, page: Page, context: BrowserContext) -> dict:
        """在浏览器上下文中执行发布流程。"""
        # Step 1: 检查登录状态
        await self._update_status("logging_in")

        await page.goto(MP_HOME_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        if not await check_login_status(page):
            # 需要扫码登录
            qr_image = await capture_qr_code(page)
            if qr_image:
                qr_path = Path(f"/tmp/wechat_qr_{self.account_id}.png")
                qr_path.write_bytes(qr_image)
                logger.info("QR code saved to %s", qr_path)

            # 等待扫码
            if not await wait_for_qr_scan(page, timeout_seconds=120):
                raise PublishError("扫码登录超时，请重试")

        logger.info("Account %s logged in successfully", self.account_name)

        # Step 2: 进入新建图文页面
        await self._update_status("editing")
        await self._navigate_to_new_article(page)

        # Step 3: 填写标题
        await self._fill_title(page, self.task.title)

        # Step 4: 注入内容到编辑器
        html_content = convert_markdown_to_wechat_html(self.task.content_md)
        await self._inject_content(page, html_content)

        # Step 5: 上传封面图（如有）
        if self.task.cover_image:
            await self._upload_cover(page, self.task.cover_image.path)

        # Step 6: 保存草稿或发布
        await self._update_status("publishing")

        if self.task.save_as_draft:
            result = await self._save_draft(page)
        else:
            result = await self._publish_article(page)

        return result

    async def _navigate_to_new_article(self, page: Page) -> None:
        """导航到新建图文页面。"""
        try:
            # 点击"新的创作"按钮
            new_creation_btn = page.locator("text=新的创作").first
            await new_creation_btn.click(timeout=10000)
            await asyncio.sleep(1)

            # 点击"图文消息"
            article_btn = page.locator("text=图文消息").first
            await article_btn.click(timeout=10000)

            # 等待编辑器加载
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # 如果打开了新窗口，切换到新窗口
            if len(page.context.pages) > 1:
                new_page = page.context.pages[-1]
                await new_page.wait_for_load_state("domcontentloaded", timeout=30000)
                logger.info("Switched to new article editor window")
        except Exception as e:
            raise PublishError(f"无法打开新建图文页面: {e}") from e

    async def _fill_title(self, page: Page, title: str) -> None:
        """填写文章标题。"""
        try:
            title_selectors = [
                "#title",
                "textarea[placeholder*='标题']",
                ".title_input textarea",
                "input[placeholder*='标题']",
            ]

            for selector in title_selectors:
                title_input = await page.query_selector(selector)
                if title_input:
                    await title_input.click()
                    await title_input.fill(title)
                    logger.info("Title filled: %s", title)
                    return

            raise PublishError("找不到标题输入框")
        except PublishError:
            raise
        except Exception as e:
            raise PublishError(f"填写标题失败: {e}") from e

    async def _inject_content(self, page: Page, html_content: str) -> None:
        """将 HTML 内容注入到编辑器。"""
        try:
            editor_selectors = [
                ".ql-editor",
                "#ueditor_0",
                ".ProseMirror",
                "[contenteditable='true']",
            ]

            for selector in editor_selectors:
                editor = await page.query_selector(selector)
                if editor:
                    await page.evaluate(
                        """(args) => {
                            const [selector, html] = args;
                            const editor = document.querySelector(selector);
                            if (editor) {
                                editor.innerHTML = html;
                                editor.dispatchEvent(new Event('input', { bubbles: true }));
                                editor.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }""",
                        [selector, html_content],
                    )
                    logger.info("Content injected into editor: %s", selector)
                    await asyncio.sleep(2)
                    return

            raise PublishError("找不到编辑器")
        except PublishError:
            raise
        except Exception as e:
            raise PublishError(f"注入内容失败: {e}") from e

    async def _upload_cover(self, page: Page, cover_path: str) -> None:
        """上传封面图。"""
        try:
            cover_selectors = [
                "text=选择封面",
                "text=上传封面",
                ".js_cover_area",
                "[data-type='cover']",
            ]

            for selector in cover_selectors:
                cover_btn = await page.query_selector(selector)
                if cover_btn:
                    await cover_btn.click()
                    await asyncio.sleep(1)

                    file_input = await page.query_selector("input[type='file']")
                    if file_input:
                        await file_input.set_input_files(cover_path)
                        logger.info("Cover image uploaded: %s", cover_path)
                        await asyncio.sleep(3)
                        return

            logger.warning("Cover upload button not found, skipping")
        except Exception:
            logger.warning("Failed to upload cover image", exc_info=True)

    async def _save_draft(self, page: Page) -> dict:
        """保存为草稿。"""
        try:
            draft_selectors = [
                "text=保存为草稿",
                "text=保存草稿",
                "button:has-text('保存')",
            ]

            for selector in draft_selectors:
                draft_btn = await page.query_selector(selector)
                if draft_btn:
                    await draft_btn.click()
                    await asyncio.sleep(3)

                    success_indicator = await page.query_selector("text=保存成功, text=已保存")
                    if success_indicator:
                        logger.info("Draft saved successfully")
                        return {"status": "draft_saved", "message": "草稿保存成功"}

                    return {"status": "draft_saved", "message": "草稿已保存（未检测到成功提示）"}

            raise PublishError("找不到保存草稿按钮")
        except PublishError:
            raise
        except Exception as e:
            raise PublishError(f"保存草稿失败: {e}") from e

    async def _publish_article(self, page: Page) -> dict:
        """直接发布文章。"""
        try:
            publish_selectors = [
                "text=群发",
                "text=发布",
                "button:has-text('群发')",
            ]

            for selector in publish_selectors:
                publish_btn = await page.query_selector(selector)
                if publish_btn:
                    await publish_btn.click()
                    await asyncio.sleep(2)

                    confirm_btn = await page.query_selector("text=确定, text=确认发布, text=继续群发")
                    if confirm_btn:
                        await confirm_btn.click()
                        await asyncio.sleep(3)

                    logger.info("Article published")
                    return {"status": "published", "message": "文章已发布"}

            raise PublishError("找不到发布按钮")
        except PublishError:
            raise
        except Exception as e:
            raise PublishError(f"发布失败: {e}") from e

    async def _update_status(self, status: str) -> None:
        """更新任务状态。"""
        from django.utils import timezone

        self.task.status = status
        if status == "logging_in":
            self.task.started_at = timezone.now()
        await sync_to_async(self.task.save)(update_fields=["status", "started_at", "updated_at"])
        logger.info("Task %d status updated to: %s", self.task.pk, status)
