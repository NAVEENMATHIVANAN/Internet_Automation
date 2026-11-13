from pathlib import Path
import json
from playwright.sync_api import sync_playwright, Error as PlaywrightError

URL = "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/allconnect"
OUTPUT = Path("portal_data/checkout_dom_frames")
OUTPUT.mkdir(parents=True, exist_ok=True)

SNAPSHOT_JS = r"""
() => {
  const visible = (el) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const labelFor = (el) => {
    const labels = el.labels
      ? Array.from(el.labels).map(x => clean(x.innerText || x.textContent || ''))
      : [];
    const parentText = clean(el.closest('label')?.innerText || '');
    return [...labels, parentText].filter(Boolean).join(' | ');
  };

  const controls = Array.from(document.querySelectorAll(
    'input,select,textarea,button,a,[role="button"]'
  )).filter(visible).map((el, i) => {
    const type = (el.getAttribute('type') || '').toLowerCase();
    const sensitive = /password|hidden/i.test(type) ||
      /ssn|social|birth|dob|credit.?card|card.?number|cvv|security.?code|payment/i.test(
        [el.id, el.name, el.getAttribute('placeholder'), labelFor(el)].join(' ')
      );

    return {
      index: i,
      tag: el.tagName,
      id: el.id || '',
      name: el.getAttribute('name') || '',
      type,
      valueAttribute: sensitive ? '[REDACTED]' : (el.getAttribute('value') || ''),
      placeholder: el.getAttribute('placeholder') || '',
      label: labelFor(el),
      // Never read live input values; this prevents SSN/DOB/payment data leaking.
      text: clean(el.innerText || el.textContent || ''),
      disabled: !!el.disabled,
      checked: ('checked' in el) ? !!el.checked : null,
      className: (typeof el.className === 'string') ? el.className : '',
      options: el.tagName === 'SELECT'
        ? Array.from(el.options).map(o => ({
            text: clean(o.text),
            value: o.value,
            selected: o.selected
          }))
        : [],
      outerHTML: el.outerHTML.slice(0, 1000)
    };
  });

  const headings = Array.from(document.querySelectorAll(
    'h1,h2,h3,[class*="pageTitle"],[id*="content_header"]'
  )).filter(visible)
    .map(el => clean(el.innerText || el.textContent))
    .filter(Boolean);

  return {
    url: location.href,
    title: document.title,
    headings,
    controls
  };
}
"""

def safe_frame_snapshot(frame):
    last_error = None
    for attempt in range(1, 4):
        try:
            return frame.evaluate(SNAPSHOT_JS)
        except PlaywrightError as exc:
            last_error = exc
            try:
                frame.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            frame.page.wait_for_timeout(800)
    return {
        "url": frame.url,
        "error": f"Frame changed during capture: {type(last_error).__name__}"
    }

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": 1600, "height": 900})
    page = context.new_page()

    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)

        if page.locator("#site-password").is_visible():
            print("Log in manually. Do not share the portal password.")
            page.locator("#site-password").wait_for(state="hidden", timeout=300000)

        print("\nNavigate manually to Recommendations.")
        input("When Recommendations is fully visible, press Enter...")

        print("\nCapture screens in order. Wait until each screen is stable.")
        print("Do not enter SSN, DOB, payment credentials, run a credit check, or submit an order.")
        print("Live input values are not captured by this script.")
        print("Type q then Enter to finish.\n")

        count = 0
        while True:
            command = input("Capture current screen? [Enter=yes, q=quit]: ").strip().lower()
            if command == "q":
                break

            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightError:
                pass
            page.wait_for_timeout(1000)

            frame_data = []
            frames = list(page.frames)
            for index, frame in enumerate(frames):
                snap = safe_frame_snapshot(frame)
                snap["frame_index"] = index
                snap["is_main_frame"] = frame == page.main_frame
                frame_data.append(snap)

            count += 1
            payload = {
                "capture_number": count,
                "main_url": page.url,
                "frame_count": len(frame_data),
                "frames": frame_data
            }
            filename = OUTPUT / f"screen_{count:02d}.json"
            filename.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            print(f"Saved {filename}")
            print(f"Frames captured: {len(frame_data)}")
            for frame in frame_data:
                print(
                    f"  Frame {frame.get('frame_index')}: "
                    f"{frame.get('url', '')} | "
                    f"Title: {frame.get('title', '')} | "
                    f"Controls: {len(frame.get('controls', []))}"
                )
            print("Navigate manually to the next screen and wait until stable.\n")

        print(f"\nCaptured {count} screens in {OUTPUT}")
    finally:
        context.close()
        browser.close()
