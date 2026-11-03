
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()

PORTAL_URL = os.getenv("PORTAL_URL", "https://example.com")
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "60000"))

SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


class BrowserService:

    def __init__(self):
        self.headless = BROWSER_HEADLESS
        self.timeout = BROWSER_TIMEOUT

    def inspect_portal(self, url=None):
        target_url = url or PORTAL_URL

        if not target_url.startswith(("https://", "http://")):
            raise ValueError("Portal URL must start with http:// or https://")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self.headless
            )

            context = browser.new_context(
                viewport={"width": 1366, "height": 768}
            )

            page = context.new_page()
            page.set_default_timeout(self.timeout)

            try:
                print(f"Opening portal: {target_url}")

                response = page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout
                )

                page_title = page.title()
                current_url = page.url

                # Inspect visible inputs without collecting their values.
                inputs = page.locator(
                    "input:visible, textarea:visible"
                ).evaluate_all("""
                    elements => elements.map(element => ({
                        tag: element.tagName,
                        type: element.getAttribute('type'),
                        name: element.getAttribute('name'),
                        id: element.id,
                        placeholder: element.getAttribute('placeholder')
                    }))
                """)

                # Inspect visible dropdowns.
                dropdowns = page.locator(
                    "select:visible"
                ).evaluate_all("""
                    elements => elements.map(element => ({
                        name: element.getAttribute('name'),
                        id: element.id,
                        options: Array.from(element.options).map(option => ({
                            text: option.textContent.trim(),
                            value: option.value
                        }))
                    }))
                """)

                # Inspect visible buttons.
                buttons = page.locator(
                    "button:visible, input[type=submit]:visible"
                ).evaluate_all("""
                    elements => elements.map(element => ({
                        text: element.innerText || element.value || '',
                        type: element.getAttribute('type'),
                        id: element.id
                    }))
                """)

                screenshot_path = (
                    SCREENSHOT_DIR / "portal_inspection.png"
                )

                page.screenshot(
                    path=str(screenshot_path),
                    full_page=True
                )

                return {
                    "success": True,
                    "http_status": (
                        response.status if response else None
                    ),
                    "title": page_title,
                    "url": current_url,
                    "inputs": inputs,
                    "dropdowns": dropdowns,
                    "buttons": buttons,
                    "screenshot": str(screenshot_path)
                }

            except PlaywrightTimeoutError:
                raise RuntimeError(
                    "Portal navigation timed out. Check the URL or network."
                )

            finally:
                context.close()
                browser.close()


if __name__ == "__main__":
    service = BrowserService()
    result = service.inspect_portal()

    print("\nPORTAL INSPECTION RESULT")
    print(result)
