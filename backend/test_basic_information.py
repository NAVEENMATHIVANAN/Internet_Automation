
from pathlib import Path
import re
import json
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/allconnect"

OUTPUT = Path("portal_data")
OUTPUT.mkdir(exist_ok=True)

CUSTOMER = {
    "prefix": "Mr",
    "first_name": "John",
    "middle_initial": "A",
    "last_name": "Smith",
    "initial_zip": "78701",
    "address": "123 Example Street",
    "city": "Austin",
    "state": "Texas",
    "service_zip": "78701",
    "dwelling": "House",
    "ownership": "Own",
    "moving": "No",
    "customer_type": "New"
}


def wait_between_steps(page):
    page.wait_for_timeout(2500)


def click_forward(page):
    """Find and click the visible Forward control."""

    button = page.get_by_role(
        "button",
        name=re.compile(r"Forward", re.I)
    )

    if button.count() == 1 and button.is_visible():
        button.click()
        return

    alternatives = page.locator(
        "input[type='button'][value*='Forward'], "
        "input[type='submit'][value*='Forward']"
    )

    if alternatives.count() == 1 and alternatives.is_visible():
        alternatives.click()
        return

    raise RuntimeError(
        "Could not uniquely identify the Forward button. "
        "Inspect the current screen before continuing."
    )


def wait_for_visible_page_text(page, text, timeout=60000):
    page.wait_for_function(
        """
        expected => {
            const body = document.body;
            return body &&
                body.innerText.toLowerCase().includes(
                    expected.toLowerCase()
                );
        }
        """,
        arg=text,
        timeout=timeout
    )


def save_screen(page, name):
    page.screenshot(
        path=str(OUTPUT / f"{name}.png"),
        full_page=True
    )

    data = {
        "url": page.url,
        "title": page.title(),
        "text": page.locator("body").inner_text()
    }

    with open(
        OUTPUT / f"{name}.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(data, file, indent=2)

    print(f"Captured screen: {name}")


def authenticate(page):
    page.goto(
        PORTAL_URL,
        wait_until="domcontentloaded",
        timeout=90000
    )

    password = page.locator("#site-password")

    if password.is_visible():
        print("Enter portal password manually.")
        password.wait_for(
            state="hidden",
            timeout=300000
        )

    print("Portal authenticated.")


def navigate_to_basic_information(page):

    print("Checking current portal screen...")

    start = page.locator("#startCall")
    forward = page.locator("#forward")

    # Start session if the portal is on the Idle Page.
    if start.is_visible():
        print("Idle Page detected. Starting session...")
        start.click()

        forward.wait_for(
            state="visible",
            timeout=60000
        )

    # If already on Greetings, continue.
    if forward.is_visible():
        print("Greetings screen detected.")

        wait_between_steps(page)
        click_forward(page)

    # Wait for the actual Basic Information form.
    page.locator("#firstName").wait_for(
        state="visible",
        timeout=60000
    )

    print("Basic Information screen reached.")


def fill_basic_information(page):

    page.locator("#namePrefixList").select_option(
        label=CUSTOMER["prefix"]
    )

    page.locator("#firstName").fill(
        CUSTOMER["first_name"]
    )

    page.locator("#middleName").fill(
        CUSTOMER["middle_initial"]
    )

    page.locator("#lastName").fill(
        CUSTOMER["last_name"]
    )

    page.locator("#ssZipCode").fill(
        CUSTOMER["initial_zip"]
    )

    page.locator("#ssZipCode").press("Tab")

    page.wait_for_function("""
        () => {
            const field = document.querySelector('#address1');
            return field && !field.disabled;
        }
    """, timeout=30000)

    page.locator("#address1").fill(
        CUSTOMER["address"]
    )

    page.locator("#city").fill(
        CUSTOMER["city"]
    )

    page.locator("#stateList").select_option(
        label=CUSTOMER["state"]
    )

    page.locator("#zipcode").fill(
        CUSTOMER["service_zip"]
    )

    page.locator("#serviceAddressTypeList").select_option(
        label=CUSTOMER["dwelling"]
    )

    page.locator("#rentOwnList").select_option(
        label=CUSTOMER["ownership"]
    )

    page.locator("#customerMove").select_option(
        label=CUSTOMER["moving"]
    )

    print("\nCustomer information populated.")

    # Save screenshot for verification.
    save_screen(page, "basic_information_filled")

    print("\nPlease verify the customer details.")
    print("Automation will continue in 5 seconds...")

    page.wait_for_timeout(5000)

    print("Verification wait completed.")


def process_address_validation(page):

    print("Waiting before submitting Basic Information...")
    wait_between_steps(page)

    page.locator("#basicInfoForward").click()

    wait_for_visible_page_text(page, "Address Matched")

    print("Address matched successfully.")

    save_screen(page, "valid_address")

    wait_between_steps(page)

    click_forward(page)

    page.locator("input[type='radio']").first.wait_for(
        state="visible",
        timeout=60000
    )

    print("Qualification screen reached.")


def select_customer_type(page):

    print("Selecting customer type...")

    customer_type = CUSTOMER["customer_type"]

    radio = page.locator(
        f'input[type="radio"][value="{customer_type}"]:visible'
    ).first

    radio.wait_for(
        state="visible",
        timeout=30000
    )

    radio.check()

    if not radio.is_checked():
        raise RuntimeError(
            "Customer type selection was unsuccessful."
        )

    print("Customer type selected:", customer_type)

    save_screen(page, "qualification_selected")

    wait_between_steps(page)

    click_forward(page)

    wait_for_visible_page_text(
        page,
        "Recommendations"
    )

    print("Recommendations screen reached.")

    save_screen(page, "recommendations")


def main():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            viewport={"width": 1600, "height": 900}
        )

        page = context.new_page()

        try:
            authenticate(page)

            navigate_to_basic_information(page)

            fill_basic_information(page)

            process_address_validation(page)

            select_customer_type(page)

            print("\nSUCCESS!")
            print("Automation reached Recommendations.")
            print("Browser will remain open for review.")

            page.wait_for_timeout(300000)

        except Exception as error:

            print("\nAUTOMATION ERROR:", repr(error))

            try:
                save_screen(page, "automation_error")
            except Exception:
                pass

            input("Press Enter to close browser...")

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
