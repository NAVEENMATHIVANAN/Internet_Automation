
from pathlib import Path
from playwright.sync_api import sync_playwright


class BrowserService:

    def __init__(self, headless=False):
        self.headless = headless

    def test_browser(self, url):
        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=self.headless
            )

            context = browser.new_context(
                viewport={
                    "width": 1366,
                    "height": 768
                }
            )

            page = context.new_page()

            try:
                print("Launching Chromium...")
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page_title = page.title()

                print("Browser launched successfully!")
                print("Page title:", page_title)
                print("Current URL:", page.url)

                screenshot_dir = Path("screenshots")
                screenshot_dir.mkdir(exist_ok=True)

                screenshot_path = (
                    screenshot_dir / "browser_test.png"
                )

                page.screenshot(
                    path=str(screenshot_path),
                    full_page=True
                )

                print("Screenshot saved:", screenshot_path)

            finally:
                context.close()
                browser.close()
                print("Browser closed.")


if __name__ == "__main__":
    browser_service = BrowserService(headless=True)

    browser_service.test_browser(
        "https://example.com"
    )
