
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

URL = "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/allconnect"
OUTPUT = Path("portal_data")
OUTPUT.mkdir(exist_ok=True)


def inspect(page, name):
    data = {
        "url": page.url,
        "title": page.title(),
        "text": page.locator("body").inner_text(),
        "elements": page.locator(
            "button, a, input, select, "
            "[role=button], [onclick], "
            "[class*=provider], [class*=plan]"
        ).evaluate_all("""
            elements => elements.map(el => ({
                tag: el.tagName,
                id: el.id,
                name: el.getAttribute('name'),
                type: el.getAttribute('type'),
                text: (el.innerText || el.value || '').trim(),
                className: String(el.className),
                role: el.getAttribute('role'),
                onclick: el.getAttribute('onclick')
            }))
        """)
    }

    with open(
        OUTPUT / f"{name}.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(data, file, indent=2)

    page.screenshot(
        path=str(OUTPUT / f"{name}.png"),
        full_page=True
    )

    print("URL:", data["url"])
    print("Elements found:", len(data["elements"]))
    print("Saved:", name)


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

        # Start session if needed.
        start = page.locator("#startCall")

        if start.is_visible():
            start.click()

        page.locator("#forward").wait_for(
            state="visible",
            timeout=60000
        )
        page.locator("#forward").click()

        page.locator("#firstName").wait_for(
            state="visible",
            timeout=60000
        )

        # Synthetic test customer.
        page.locator("#namePrefixList").select_option(label="Mr")
        page.locator("#firstName").fill("John")
        page.locator("#middleName").fill("A")
        page.locator("#lastName").fill("Smith")
        page.locator("#ssZipCode").fill("78701")
        page.locator("#ssZipCode").press("Tab")

        page.wait_for_function("""
            () => {
                const e = document.querySelector('#address1');
                return e && !e.disabled;
            }
        """)

        page.locator("#address1").fill("123 Example Street")
        page.locator("#city").fill("Austin")
        page.locator("#stateList").select_option(label="Texas")
        page.locator("#zipcode").fill("78701")
        page.locator("#serviceAddressTypeList").select_option(label="House")
        page.locator("#rentOwnList").select_option(label="Own")
        page.locator("#customerMove").select_option(label="No")

        page.wait_for_timeout(5000)

        page.locator("#basicInfoForward").click()

        # Wait for the final address confirmation.
        address_confirmation = page.locator("p.green").filter(
            has_text="Proceed to the next screen"
        )

        address_confirmation.wait_for(
            state="visible",
            timeout=60000
        )
        print("Address confirmation received.")

        page.wait_for_timeout(2000)

        # Capture all visible navigation controls.
        controls = page.locator(
            "button:visible, input:visible, a:visible, "
            "[role='button']:visible"
        ).evaluate_all("""
            elements => elements.map(el => ({
                tag: el.tagName,
                id: el.id,
                type: el.getAttribute('type'),
                value: el.value || '',
                text: (el.innerText || '').trim(),
                className: String(el.className)
            }))
        """)

        print("\\nADDRESS SCREEN CONTROLS:")
        for control in controls:
            print(control)

        page.screenshot(
            path="portal_data/address_confirmation.png",
            full_page=True
        )

        print("Final address confirmation received.")

        page.wait_for_timeout(2500)

        # Click the actual Forward button on the Address Matched page.
        address_forward = page.locator("#addressFoundForward")
        address_forward.wait_for(state="visible", timeout=15000)
        address_forward.click()

        print("Address confirmation accepted. Moving to Qualification...")

        # Wait for the Qualification page and select New.
        new_option = page.locator(
            'input[type="radio"][value="New"]:visible'
        ).first
        new_option.wait_for(state="visible", timeout=30000)
        new_option.check()

        print("Qualification page loaded and New option selected.")

        # Inspect the actual navigation controls on the Qualification page.
        # Locate and click the visible Forward button.
        qualification_forward = page.locator(
            'input[type="button"][value*="Forward"]:visible'
        )
        qualification_forward.wait_for(
            state="visible",
            timeout=15000
        )
        print("Qualification Forward button found.")
        qualification_forward.click()

        print("Clicked Forward. Waiting for Recommendations...")

        # Confirm navigation and inspect the recommendations page.
        # Wait for the actual Recommendations page header.
        page.locator(
          "#content_header span.pageTitle"
        ).filter(
           has_text="Recommendations"
        ).wait_for(
           state="visible",
           timeout=60000
      )
        print("Recommendations page loaded successfully.")

        page.wait_for_timeout(2500)
        inspect(page, "recommendations_inspection")

        print("\nRecommendations page inspection completed.")
        print("Browser will remain open for five minutes.")
        page.wait_for_timeout(300000)

    except Exception as error:
        print("Inspection error:", repr(error))
        input("Press Enter to close...")

    finally:
        context.close()
        browser.close()
