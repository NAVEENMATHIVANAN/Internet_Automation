from pathlib import Path
import json
from playwright.sync_api import sync_playwright, Error as PlaywrightError

URL = "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/allconnect"
OUTPUT = Path("portal_data/checkout_dom")
OUTPUT.mkdir(parents=True, exist_ok=True)

SNAPSHOT_JS = r"""
() => {
  const visible = (el) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };
  const labelFor = (el) => {
    const labels = el.labels ? Array.from(el.labels).map(x => (x.innerText || x.textContent || '').trim()) : [];
    const parentText = (el.closest('label')?.innerText || '').trim();
    return [...labels, parentText].filter(Boolean).join(' | ');
  };
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const controls = Array.from(document.querySelectorAll('input,select,textarea,button,a,[role="button"]'))
    .filter(visible).map((el, i) => ({
      index: i,
      tag: el.tagName,
      id: el.id || '',
      name: el.getAttribute('name') || '',
      type: el.getAttribute('type') || '',
      valueAttribute: el.getAttribute('value') || '',
      placeholder: el.getAttribute('placeholder') || '',
      label: clean(labelFor(el)),
      text: clean(el.innerText || el.textContent || (el.tagName === 'INPUT' ? el.value : '')),
      disabled: !!el.disabled,
      checked: ('checked' in el) ? !!el.checked : null,
      className: (typeof el.className === 'string') ? el.className : '',
      options: el.tagName === 'SELECT' ? Array.from(el.options).map(o => ({text: clean(o.text), value: o.value, selected: o.selected})) : [],
      outerHTML: el.outerHTML.slice(0, 1200)
    }));
  const headings = Array.from(document.querySelectorAll('h1,h2,h3,[class*="pageTitle"],[id*="content_header"]'))
    .filter(visible).map(el => clean(el.innerText || el.textContent)).filter(Boolean);
  return { url: location.href, title: document.title, headings, controls };
}
"""

def capture_page(page):
    """Capture after navigation settles; retry if Chromium destroys the JS context."""
    last_error = None

    for attempt in range(1, 6):
        try:
            # Wait for the new document to expose a body before evaluating.
            page.locator("body").wait_for(state="attached", timeout=10000)
            page.wait_for_timeout(700)
            return page.evaluate(SNAPSHOT_JS)
        except PlaywrightError as exc:
            last_error = exc
            print(
                f"Page changed while capturing (attempt {attempt}/5). "
                "Waiting for navigation to settle..."
            )
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightError:
                pass
            page.wait_for_timeout(1200)

    raise RuntimeError(
        "Could not capture the page because it kept navigating. "
        "Wait until the screen is stable, then run the capture again."
    ) from last_error


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": 1600, "height": 900})
    page = context.new_page()

    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)

        if page.locator("#site-password").is_visible():
            print("Log in manually using the portal password. Do not share it with me.")
            page.locator("#site-password").wait_for(state="hidden", timeout=300000)

        print("\nNavigate manually to the Recommendations page.")
        input("When Recommendations is visible and fully loaded, press Enter here...")

        print("\nCapture each checkout screen in order.")
        print("For each screen: leave the page visible and wait until it stops changing, then press Enter.")
        print("Do not submit an order, run a credit check, or enter SSN/DOB/payment details.")
        print("Type q then Enter when finished.\n")

        count = 0
        while True:
            command = input("Capture current screen? [Enter=yes, q=quit]: ").strip().lower()
            if command == "q":
                break

            try:
                data = capture_page(page)
            except Exception as exc:
                print(f"Capture failed: {exc}")
                print("Wait for the current page to finish loading, then press Enter to retry.")
                continue

            count += 1
            filename = OUTPUT / f"screen_{count:02d}.json"
            filename.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"Saved {filename}")
            print("URL:", data.get("url"))
            print("Page:", data.get("title"), "| Headings:", " / ".join(data.get("headings", [])))
            print("Visible controls:", len(data.get("controls", [])))
            print("Now navigate manually to the next screen in Chromium.")
            print("Wait until the next screen is fully visible before capturing it.\n")

        print(f"\nCaptured {count} screens in {OUTPUT}")
    finally:
        context.close()
        browser.close()
