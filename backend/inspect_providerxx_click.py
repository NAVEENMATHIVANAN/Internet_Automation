
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright, Error as PlaywrightError


async def inspect_frame(frame):
    for attempt in range(1, 6):
        try:
            return await frame.locator("body *").evaluate_all("""
                els => els.filter(el =>
                    el.children.length === 0 &&
                    el.innerText?.trim().toLowerCase() === "providerxx"
                ).map(el => {
                    let node = el;
                    const ancestors = [];

                    for (let i = 0; i < 7 && node; i++, node = node.parentElement) {
                        ancestors.push({
                            tag: node.tagName,
                            id: node.id,
                            className: typeof node.className === "string"
                                ? node.className : "",
                            onclick: node.getAttribute("onclick"),
                            role: node.getAttribute("role"),
                            cursor: getComputedStyle(node).cursor,
                            html: node.outerHTML.slice(0, 1500)
                        });
                    }

                    return ancestors;
                });
            """)
        except PlaywrightError as exc:
            if "Execution context was destroyed" in str(exc):
                print(f"Navigation detected. Retrying inspection ({attempt}/5)...")
                await asyncio.sleep(2)
                continue
            raise

    return []


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("Opening the test portal...")
        await page.goto(
            "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/allconnect",
            wait_until="domcontentloaded"
        )

        input(
            "\nLog in manually and navigate to the ProviderXX "
            "Recommendations page.\n"
            "Wait until the page is fully loaded, then press ENTER here..."
        )

        # Allow any pending portal navigation to finish.
        await asyncio.sleep(3)

        results = []

        for attempt in range(1, 6):
            try:
                print(f"\nInspection attempt {attempt}/5")
                await page.wait_for_load_state(
                    "domcontentloaded", timeout=15000
                )

                frames = page.frames
                print(f"Frames detected: {len(frames)}")

                results = []

                for index, frame in enumerate(frames):
                    try:
                        print(f"Inspecting frame {index}: {frame.url}")

                        matches = await inspect_frame(frame)

                        if matches:
                            results.append({
                                "frame_index": index,
                                "frame_url": frame.url,
                                "matches": matches
                            })

                    except PlaywrightError as exc:
                        print(f"Frame inspection skipped: {exc}")

                break

            except PlaywrightError as exc:
                print(f"Page is still navigating: {exc}")
                await asyncio.sleep(2)

        output_path = Path(__file__).parent / "providerxx_inspection.json"

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(results, file, indent=4, ensure_ascii=False)

        print("\n========== INSPECTION RESULT ==========")
        print(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\nSaved inspection: {output_path}")

        input("\nPress ENTER to close the browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
