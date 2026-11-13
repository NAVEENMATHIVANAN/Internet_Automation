
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/allconnect"

OUTPUT = Path("portal_data")
OUTPUT.mkdir(exist_ok=True)


def inspect_page(page, step):
    page.wait_for_timeout(2000)

    data = {
        "step": step,
        "url": page.url,
        "title": page.title(),
        "body_text": page.locator("body").inner_text(),
        "frames": [],
        "elements": []
    }

    for frame_index, frame in enumerate(page.frames):
        try:
            frame_data = {
                "frame_index": frame_index,
                "url": frame.url,
                "elements": frame.locator(
                    "input, select, textarea, button, "
                    "[role=button], [contenteditable=true]"
                ).evaluate_all("""
                    elements => elements.map(el => ({
                        tag: el.tagName,
                        type: el.getAttribute('type'),
                        id: el.id,
                        name: el.getAttribute('name'),
                        text: (el.innerText || el.value || '').trim(),
                        placeholder: el.getAttribute('placeholder'),
                        ariaLabel: el.getAttribute('aria-label'),
                        role: el.getAttribute('role')
                    }))
                """)
            }

            data["frames"].append(frame_data)

            if frame_index == 0:
                data["elements"] = frame_data["elements"]

        except Exception as error:
            data["frames"].append({
                "frame_index": frame_index,
                "error": str(error)
            })

    with open(
        OUTPUT / f"{step}.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(data, file, indent=2)

    page.screenshot(
        path=str(OUTPUT / f"{step}.png"),
        full_page=True
    )

    print(f"\nCaptured: {step}")
    print("URL:", page.url)
    print("Elements:", len(data["elements"]))
    print("Frames:", len(data["frames"]))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1600, "height": 900}
    )
    page = context.new_page()

    try:
        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        password = page.locator("#site-password")

        if password.is_visible():
            print("Authenticate manually.")
            password.wait_for(
                state="hidden",
                timeout=300000
            )

        page.wait_for_timeout(2000)

        # Start session if we are on the Idle Page.
        start = page.locator("#startCall")

        if start.is_visible():
            start.click()
            page.wait_for_timeout(3000)

        inspect_page(page, "03_greetings")

        # Advance using the confirmed Forward control.
        forward = page.locator("#forward")

        if not forward.is_visible():
            raise RuntimeError("Forward button not found.")

        print("\nAdvancing from Greetings...")
        forward.click()

        page.wait_for_timeout(3000)

        inspect_page(page, "04_next_screen")

        print("\nBrowser remains open for five minutes.")
        page.wait_for_timeout(300000)

    except Exception as error:
        print("\nInspection error:", repr(error))

        try:
            page.screenshot(
                path=str(OUTPUT / "inspection_error.png"),
                full_page=True
            )
        except Exception:
            pass

        input("Press Enter to close...")

    finally:
        context.close()
        browser.close()
