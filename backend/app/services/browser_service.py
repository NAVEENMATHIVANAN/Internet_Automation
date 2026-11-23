from __future__ import annotations
import os, re, json, random
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()
PORTAL_URL = os.getenv('PORTAL_URL', 'https://test-site-working-09878.newapps.net/tellcom')
DATA_DIR = Path('portal_data')
DATA_DIR.mkdir(exist_ok=True)

STATE_NAMES = {
'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','DC':'District Of Columbia','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'}

class BrowserService:
    """Full portal workflow runner. Login is entered manually; all later pages are driven from order data."""
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.steps: list[str] = []
        self._run_succeeded = False
        self._sensitive_data_active = False

    def _step(self, name: str):
        self.steps.append(name)
        print(f'[AUTOMATION] {name}')

    
    def _human_type(self, locator, value: str, delay: int = 75):
        """Type text character by character so the action is visible."""
        locator.wait_for(state="visible", timeout=15000)

        if not locator.is_enabled():
            raise RuntimeError("Cannot type into a disabled field.")

        locator.click()
        locator.fill("")
        locator.press_sequentially(str(value), delay=delay)

        self.page.wait_for_timeout(250)

    def _human_select(self, locator, value: str = None, label: str = None):
        """Select a dropdown option with a visible pause."""
        locator.wait_for(state="visible", timeout=15000)
        self.page.wait_for_timeout(random.randint(300, 600))

        if label is not None:
            locator.select_option(label=label)
        else:
            locator.select_option(value=value)

        self.page.wait_for_timeout(random.randint(400, 700))

    def _human_click(self, locator):
        """Perform a visible click with a short pause."""
        locator.wait_for(state="visible", timeout=15000)

        if not locator.is_enabled():
            raise RuntimeError("Cannot click a disabled control.")

        self.page.wait_for_timeout(random.randint(300, 600))
        locator.click()
        self.page.wait_for_timeout(random.randint(400, 700))

    def _human_check(self, locator):
        """Check a checkbox or radio button visibly."""
        locator.wait_for(state="visible", timeout=15000)

        if not locator.is_checked():
            self.page.wait_for_timeout(random.randint(300, 600))
            locator.check()
            self.page.wait_for_timeout(random.randint(400, 700))

    
    def _review_pause(self, section: str):
        delay = random.randint(30, 40)

        print(
            f"\n[REVIEW] {section} is ready."
            f"\nCheck the browser and correct any information."
            f"\nAutomation will continue in {delay} seconds."
        )

        self.page.wait_for_timeout(delay * 1000)
    

    def _screenshot(self, name: str):
      if self.page and not self._sensitive_data_active:
        self.page.screenshot(
            path=str(DATA_DIR / f"{name}.png"),
            full_page=True
        )

    def _wait_text(self, text: str, timeout: int = 60000):
        self.page.get_by_text(re.compile(re.escape(text), re.I)).first.wait_for(state='visible', timeout=timeout)

    def _forward_main(self):
        candidates = [self.page.locator('#forward'), self.page.locator('#basicInfoForward'), self.page.locator('#addressFoundForward')]
        for loc in candidates:
            if loc.count() and loc.first.is_visible() and loc.first.is_enabled():
                loc.first.click(); return
        loc = self.page.locator('input[type="button"][value*="Forward"],input[type="submit"][value*="Forward"]')
        for i in range(loc.count()):
            if loc.nth(i).is_visible() and loc.nth(i).is_enabled():
                loc.nth(i).click(); return
        raise RuntimeError('No enabled Forward control found on the current main portal page.')

    def _login_and_start(self):
        self._step('Open portal and wait for manual password login')
        self.page.goto(PORTAL_URL, wait_until='domcontentloaded', timeout=90000)
        password = self.page.locator('#site-password')
        if password.count() and password.is_visible():
            print('\nPortal password required. Enter it in the opened Chromium window; automation will resume automatically.')
            password.wait_for(state='hidden', timeout=300000)
        self.page.wait_for_load_state('domcontentloaded', timeout=60000)
        self.page.wait_for_timeout(1500)
        start = self.page.locator('#startCall')
        if start.count() and start.is_visible():
            self._step('Start Session from Idle Page')
            start.click()
        self.page.locator('#forward').wait_for(state='visible', timeout=60000)
        self._step('Continue through Greetings')
        self.page.locator('#forward').click()
        self.page.locator('#firstName').wait_for(state='visible', timeout=60000)

    def _fill_basic_information(self, data: dict[str, Any]):
        
        c, a = data['customer'], data['service_address']
        self._step('Fill Basic Information')

        
        # Prefix is optional. Match the portal's actual options
        # instead of assuming that its labels match our API values.
        prefix = (c.get('prefix') or '').strip()

        if prefix:
            prefix_select = self.page.locator('#namePrefixList')
            prefix_select.wait_for(state='visible', timeout=15000)

            normalize = lambda value: re.sub(
                r'[^a-z0-9]',
                '',
                (value or '').lower()
            )

            requested_prefix = normalize(prefix)
            matched_value = None

            options = prefix_select.locator('option')

            for index in range(options.count()):
                option = options.nth(index)

                option_text = option.inner_text().strip()
                option_value = option.get_attribute('value') or ''

                if (
                    requested_prefix
                    and requested_prefix in {
                        normalize(option_text),
                        normalize(option_value)
                    }
                ):
                    matched_value = option_value
                    break

            if matched_value is not None:
                prefix_select.select_option(value=matched_value)
                self._step('Customer prefix selected')
            else:
                self._step(
                    'Optional prefix not available in portal - skipped'
                )
        else:
            self._step('Optional customer prefix skipped')


        self._human_type(
            self.page.locator('#firstName'),
            c['first_name']
        )

        if c.get('middle_initial'):
            self._human_type(
                self.page.locator('#middleName'),
                c['middle_initial']
            )

        self._human_type(
            self.page.locator('#lastName'),
            c['last_name']
        )

        if c.get('suffix'):
            self._human_select(
                self.page.locator('#nameSuffixList'),
                label=c['suffix']
            )

        # Initial ZIP prompt
        self._human_type(
            self.page.locator('#ssZipCode'),
            a['zip_code'][:5]
        )

        self.page.locator('#ssZipCode').press('Tab')

        self.page.wait_for_function(
            "() => { const e=document.querySelector('#address1'); "
            "return e && !e.disabled; }",
            timeout=30000
        )

        self._human_type(
            self.page.locator('#address1'),
            a['address_line_1']
        )

        if a.get('unit_type'):
            self._human_select(
                self.page.locator('#unitTypeList'),
                label=a['unit_type']
            )

        if a.get('unit_number'):
            self._human_type(
                self.page.locator('#unitNumber'),
                a['unit_number']
            )

        self._human_type(
            self.page.locator('#city'),
            a['city']
        )

        state = a['state'].upper()

        self._human_select(
            self.page.locator('#stateList'),
            label=STATE_NAMES.get(state, state)
        )

        self._human_type(
            self.page.locator('#zipcode'),
            a['zip_code']
        )

                # Select dwelling type using the actual portal options.
        dwelling_dropdown = self.page.locator(
            '#serviceAddressTypeList'
        )

        dwelling_dropdown.wait_for(
            state='visible',
            timeout=15000
        )

        available_options = dwelling_dropdown.locator(
            'option'
        ).evaluate_all("""
            options => options.map(option => ({
                text: option.textContent.trim(),
                value: option.value,
                disabled: option.disabled
            }))
        """)

        print("\\n[DWELLING TYPE] Available portal options:")
        print(json.dumps(available_options, indent=2))

        dwelling_map = {
            'HOUSE': ['House'],
            'CONDO': ['Condo'],
            'DUPLEX': ['Duplex'],
            'APARTMENT': ['Apartment'],
            'MOBILE_HOME': ['Mobile Home']
        }

        requested_type = a['dwelling_type'].upper()
        candidates = dwelling_map.get(requested_type)

        if not candidates:
            raise RuntimeError(
                f'Unsupported dwelling type: {requested_type}'
            )

        selected_option = next(
            (
                option for option in available_options
                if option['text'].strip().casefold()
                in [candidate.casefold() for candidate in candidates]
                and not option['disabled']
            ),
            None
        )

        if not selected_option:
            raise RuntimeError(
                f'Could not find dwelling type {requested_type}. '
                f'Actual portal options: {available_options}'
            )

        dwelling_dropdown.select_option(
            value=selected_option['value']
        )

        print(
            f"[DWELLING TYPE] Selected: "
            f"{selected_option['text']}"
        )
        self.page.locator('#rentOwnList').select_option(label={'OWN':'Own','RENT':'Rent'}[a['ownership']])
                # Fill Lead ID
        lead_id = data['order'].get('lead_id')

        if not lead_id:
            raise RuntimeError(
                'Lead ID is missing from the order data.'
            )

        self._human_type(
            self.page.locator('#rvCallID'),
            lead_id
        )

        self._step('Lead ID entered')
        self.page.locator('#customerMove').select_option(label='Yes' if a['moving_status'] else 'No')
                # Fill move-in date only when the customer is moving.
        if a.get('moving_status'):
            move_date = a.get('move_in_date')

            if not move_date:
                raise RuntimeError(
                    'Moving customer requires a move-in date.'
                )

            self.page.locator('#datepicker').wait_for(
                state='visible',
                timeout=15000
            )

            self.page.locator('#datepicker').fill(move_date)

        self._screenshot('full_flow_01_basic_information')
        self._step('Submit service address for portal validation')
        self._review_pause('Basic Information')
        self.page.locator('#basicInfoForward').click()
        self.page.locator('p.green').filter(has_text='Proceed to the next screen').wait_for(state='visible', timeout=60000)
        self._review_pause('Address Validation')
        self.page.locator('#addressFoundForward').click()
        self.page.locator('input[type="radio"][value="New"],input[type="radio"][value="Transfer"]').first.wait_for(state='visible', timeout=60000)

    
    
    def _select_customer_type(self, data: dict[str, Any]):
        customer_type = data["customer_type"]

        self._step("Select Customer Type")

        if customer_type == "NEW":
            self.page.locator(
                'input[type="radio"][value="New"]:visible'
            ).check()

        elif customer_type == "TRANSFER":
            self.page.locator(
                'input[type="radio"][value="Transfer"]:visible'
            ).check()

            # Wait for the provider section
            provider_section = self.page.locator("#existingProviderDiv")
            provider_section.wait_for(
                state="visible",
                timeout=15000
            )

            # Locate ProviderXX using its actual HTML name
            provider_checkbox = self.page.locator(
                '#existingProvidersSpan input[type="checkbox"][name="ProviderXX"]'
            )

            provider_checkbox.wait_for(
                state="visible",
                timeout=15000
            )

            # Select ProviderXX
            provider_checkbox.check()

            # Verify selection
            if not provider_checkbox.is_checked():
                raise RuntimeError(
                    "ProviderXX checkbox selection failed."
                )

            print("[SUCCESS] ProviderXX selected.")

            self._review_pause("Transfer Provider Selection")

        else:
            raise ValueError(
                f"Unsupported customer type: {customer_type}"
            )

        # Continue the existing portal flow
        self._forward_main()

                # Wait for the ProviderXX recommendations card.
        # The outer portal heading may say "Qualification",
        # so do not use the heading as the page validation.

        recommendations_frame = None
        provider_card = None

        for _ in range(60):
            recommendations_frame = next(
                (
                    frame for frame in self.page.frames
                    if '/allconnect/recommendations/' in frame.url
                ),
                None
            )

            if recommendations_frame is not None:
                provider_card = recommendations_frame.locator('#goldTable')

                if provider_card.count() and provider_card.is_visible():
                    break

            self.page.wait_for_timeout(500)

        else:
            raise RuntimeError(
                'ProviderXX recommendation card did not appear '
                'after customer type selection.'
            )

        self._step('ProviderXX recommendation card is visible')

        # Wait for the visible Recommendations page heading
        recommendations_heading = self.page.locator(
            "#content_header span.pageTitle"
       )

        recommendations_heading.wait_for(
            state="visible",
            timeout=30000
       )

        heading_text = recommendations_heading.inner_text().strip()

        if "Recommendations" not in heading_text:
            raise RuntimeError(
                f"Unexpected page heading: {heading_text}"
            )

        print("[SUCCESS] Recommendations page loaded.")



    
    def _select_provider_and_plan(self, order: dict[str, Any]):
        self._step('Select available ProviderXX and open its internet catalogue')

        # Locate the actual Allconnect Recommendations frame.
        recommendations_frame = next(
            (
                frame for frame in self.page.frames
                if '/allconnect/recommendations/' in frame.url
            ),
            None
        )

        if recommendations_frame is None:
            raise RuntimeError(
                'Allconnect Recommendations frame was not found.'
            )

        # Locate ProviderXX recommendation card.
        provider_card = recommendations_frame.locator('#goldTable')
        provider_card.wait_for(state='visible', timeout=30000)

        self._step('Select ProviderXX recommendation card')
        self._human_click(provider_card)

        # Check whether the ProviderXX acknowledgement appears.
        self._step('Check ProviderXX acknowledgement')

        yes = self.page.locator('#providerxxYes')
        products_button = self.page.locator('#ProviderXXProductsButton')

        details_buttons = self.page.locator(
            'input.ViewDetailsBtn:visible'
        )

        try:
            yes.wait_for(state='visible', timeout=8000)
        except PlaywrightTimeoutError:
            pass

        if yes.count() and yes.is_visible():
            print(
                '\n[MANUAL REVIEW REQUIRED]'
                '\nReview the ProviderXX commission acknowledgement.'
                '\nSelect Yes in the browser only if the authorized operator '
                'confirms the acknowledgement.'
            )

            input(
                'After reviewing and selecting Yes in the browser, '
                'press ENTER to continue...'
            )

            if not yes.is_checked():
                raise RuntimeError(
                    'ProviderXX acknowledgement was not confirmed.'
                )

            self._human_click(products_button)

        else:
            # Continue only if the catalogue is actually visible.
            if not details_buttons.count():
                diagnostics = self.page.locator(
                    'button:visible, a:visible, input:visible, '
                    '[role="button"]:visible, [onclick]:visible'
                ).evaluate_all("""els => els.map(el => ({
                    tag: el.tagName,
                    id: el.id || '',
                    type: el.getAttribute('type') || '',
                    value: el.value || '',
                    text: (el.innerText || el.textContent || '').trim().slice(0, 180),
                    className: String(el.className || ''),
                    onclick: el.getAttribute('onclick') || '',
                    html: el.outerHTML.slice(0, 1200)
                }))""")

                raise RuntimeError(
                    'ProviderXX card was clicked, but neither the '
                    'confirmation dialog nor Internet catalogue appeared. '
                    f'Visible controls: {diagnostics}'
                )

        # Open Internet tab if required.
        if not self.page.locator('input.ViewDetailsBtn:visible').count():
            internet_link = self.page.locator('a:visible').filter(
                has_text=re.compile(r'^\s*Internet\s*$', re.I)
            )

            if internet_link.count():
                self._human_click(internet_link.first)

        buttons = self.page.locator('input.ViewDetailsBtn:visible')

        buttons.first.wait_for(
            state='visible',
            timeout=30000
        )

        # Match the requested internet speed and pricing term.
        self._step('Find requested Internet plan')

        speed = int(order['internet_speed_mbps'])
        term = order['pricing_term']

        match_index = None
        visible_cards = []

        speed_patterns = {
            300: r'300\s*mbps|300\s*mb',
            500: r'500\s*mbps|500\s*mb',
            1000: r'1\s*gig|1000\s*mbps|1000\s*mb',
            2000: r'2\s*gig|2000\s*mbps|2000\s*mb'
        }

        for i in range(buttons.count()):
            btn = buttons.nth(i)

            card_text = btn.evaluate(
                "el => { let n=el; for(let i=0;i<10 && n;i++,n=n.parentElement){"
                "const t=(n.innerText||'').trim(); if(t.length>20) return t;} return ''; }"
            )

            normalized = re.sub(r'\s+', ' ', card_text).lower()
            visible_cards.append(normalized)

            speed_match = re.search(
                speed_patterns.get(
                    speed,
                    rf'(?<!\d){speed}\s*(?:mbps|mb|meg)'
                ),
                normalized
            ) is not None

            year_match = (
                re.search(r'1[- ]year(?: pricing)?', normalized) is not None
                if term == '1_YEAR'
                else re.search(
                    r'5[- ]year(?: price guarantee)?',
                    normalized
                ) is not None
            )

            if speed_match and year_match:
                match_index = i
                break

        if match_index is None:
            raise RuntimeError(
                f'Internet catalogue opened, but no {speed} Mbps / '
                f'{term} plan matched. Visible product cards: {visible_cards}'
            )

        # Open the matching plan details visibly.
        self._step(f'Open details for {speed} Mbps {term} plan')

        self._human_click(buttons.nth(match_index))

        add_button = self.page.locator('#addToOrderAndCheckout')

        add_button.wait_for(
            state='visible',
            timeout=30000
        )

        self._screenshot('full_flow_02_product_details')

        self._step('Review selected Internet plan')
        self._review_pause('Provider and Internet Plan Selection')

        # Add the selected plan and proceed to checkout.
        self._step('Add selected plan and proceed to checkout')

        self._human_click(add_button)

        self.page.wait_for_url(
            re.compile(r'.*/checkout/.*'),
            timeout=60000
        )

        print('[SUCCESS] Internet plan added. Checkout page opened.')


    def _checkout_frame(self):
        for _ in range(30):
            for frame in self.page.frames:
                if 'allconnect-frame' in frame.url and 'checkout' in frame.url:
                    return frame
            self.page.wait_for_timeout(1000)
        raise RuntimeError('Embedded Allconnect checkout iframe did not load.')

    
    
    
    def _choose_radio_by_label(self, frame, group_name, option_pattern):
        """Select a radio button by group name and its associated label.

        Supports regular-expression patterns used throughout the workflow.
        """
        pattern = re.compile(option_pattern, re.IGNORECASE)

        radios = frame.locator(
            f'input[type="radio"][name="{group_name}"]'
        )

        count = radios.count()

        if count == 0:
            raise RuntimeError(
                f"No radio buttons found for group '{group_name}'."
            )

        for index in range(count):
            radio = radios.nth(index)

            labels = radio.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => label.innerText.trim())
            """)

            for label in labels:
                normalized_label = re.sub(r'\s+', ' ', label).strip()

                if pattern.search(normalized_label):
                    radio.check(force=True)

                    if not radio.is_checked():
                        raise RuntimeError(
                            f"Radio selection failed for '{group_name}': "
                            f"'{normalized_label}'"
                        )

                    print(
                        f"[AUTOMATION] Selected '{normalized_label}' "
                        f"from radio group '{group_name}'."
                    )
                    return

        raise RuntimeError(
            f"Could not match pattern '{option_pattern}' "
            f"in radio group '{group_name}'."
        )



    def _debug_autopay_radios(self, frame):
        radios = frame.locator(
            'input[type="radio"][name="autopay"]'
        )

        print("\n[AUTOPAY RADIO DIAGNOSTIC]")
        print("Radio count:", radios.count())

        for index in range(radios.count()):
            details = radios.nth(index).evaluate("""
                el => {
                    const labels = Array.from(el.labels || [])
                        .map(label => label.innerText.trim());

                    let ancestors = [];
                    let node = el;

                    for (let i = 0; i < 4 && node; i++) {
                        ancestors.push({
                            tag: node.tagName,
                            id: node.id,
                            className: String(node.className || ""),
                            text: (node.innerText || "").trim().slice(0, 250)
                        });
                        node = node.parentElement;
                    }

                    return {
                        value: el.value,
                        checked: el.checked,
                        disabled: el.disabled,
                        id: el.id,
                        labels,
                        ancestors
                    };
                }
            """)

            print(f"Radio {index + 1}:", details)

    
    
    
    def _select_installation_radio(
        self,
        frame,
        option_value: str,
        option_label: str
    ):
        """
        Select installation option using the actual portal HTML.
        Radio inputs have no value or id attributes.
        """

        installation_box = frame.locator(
            'div.box.itype'
        ).first

        installation_box.wait_for(
            state='visible',
            timeout=15000
        )

        option_labels = installation_box.locator(
            'label.g-opt'
        )

        target_label = None

        for index in range(option_labels.count()):
            label = option_labels.nth(index)
            label_text = label.inner_text().strip().upper()

            if option_value.upper() in label_text:
                target_label = label
                break

        if target_label is None:
            raise RuntimeError(
                f'Installation option {option_value} not found.'
            )

        radio = target_label.locator(
            'input[type="radio"]'
        )

        if radio.count() != 1:
            raise RuntimeError(
                f'Expected one radio input for {option_value}.'
            )

        # Select through the actual label.
        if not radio.is_checked():
            target_label.click(timeout=10000)

        # Wait for the portal to update its checked state.
        radio.wait_for(state='attached')

        if not radio.is_checked():
            raise RuntimeError(
                f'{option_label} was not selected by the portal.'
            )

        self._step(
            f'{option_label} selected and verified'
        )


    
    
    
    def _place_order_and_get_portal_id(self, frame):
        """
        Complete the final order submission for both Case 1 and Case 2.

        1. Verify Order Summary.
        2. Click Place Order exactly once.
        3. Wait for final confirmation.
        4. Extract the portal-generated Order ID.
        """
        self._step("ENTERED FINAL PLACE ORDER FUNCTION")

        # --------------------------------------------------
        # 1. Verify Order Summary after navigation
        # --------------------------------------------------

        self._step(
            "Waiting for Order Summary navigation to complete"
        )

        # The previous checkout iframe may be detached after
        # the portal navigates to the Order Summary page.
        # Therefore, do not use the old frame reference here.

        try:
            self.page.wait_for_url(
                    re.compile(r".*/order-summary(?:/|\?).*"),
                    timeout=30000
                )
        except Exception:
            # If already on the Order Summary URL, continue.
            if "/order-summary/" not in self.page.url.lower():
                    raise RuntimeError(
                        "Portal did not navigate to the Order Summary page. "
                        f"Current URL: {self.page.url}"
                    )

        self._step(
            f"Order Summary navigation confirmed: {self.page.url}"
        )

        # --------------------------------------------------
        # 2. Find Place Order on the parent page
        # --------------------------------------------------

        place_order = self.page.locator(
            'form#checkoutForm input#placeOrder'
        )

        place_order.wait_for(
            state="visible",
            timeout=20000
        )

        if place_order.count() != 1:
            raise RuntimeError(
                f"Expected exactly one Place Order button, "
                f"found {place_order.count()}."
            )

        if not place_order.is_visible():
            raise RuntimeError(
                "Place Order button is not visible."
            )

        if not place_order.is_enabled():
            raise RuntimeError(
                "Place Order button is disabled."
            )

        button_info = place_order.evaluate("""
            element => ({
                id: element.id,
                value: element.value,
                disabled: element.disabled,
                formId: element.form?.id,
                formAction: element.form?.action,
                formMethod: element.form?.method,
                eventId: element.form?.querySelector(
                    'input[name="_eventId"]'
                )?.value
            })
        """)

        self._step(
            f"Place Order diagnostics: {button_info}"
        )

        # --------------------------------------------------
        # 3. Capture click and submit events
        # --------------------------------------------------

        self.page.evaluate("""
            () => {
                window.__placeOrderEvents = [];

                const button = document.querySelector(
                    'form#checkoutForm input#placeOrder'
                );

                const form = document.querySelector(
                    'form#checkoutForm'
                );

                if (!button || !form) {
                    throw new Error(
                        'Place Order button or checkout form missing.'
                    );
                }

                button.addEventListener(
                    'click',
                    event => {
                        window.__placeOrderEvents.push({
                            type: 'click',
                            trusted: event.isTrusted
                        });
                    },
                    true
                );

                form.addEventListener(
                    'submit',
                    event => {
                        window.__placeOrderEvents.push({
                            type: 'submit',
                            trusted: event.isTrusted
                        });
                    },
                    true
                );
            }
        """)

        # --------------------------------------------------
        # 4. Click Place Order exactly once
        # --------------------------------------------------

        self._step(
            "Submitting final order using browser interaction"
        )

        place_order.scroll_into_view_if_needed()

        # Do not retry this click automatically.
        place_order.click(timeout=15000)

        self._step("Place Order click completed")

        self.page.wait_for_timeout(2000)

        try:
            event_results = self.page.evaluate(
                "() => window.__placeOrderEvents || []"
            )
        except Exception:
            # The page may have navigated and replaced its document.
            event_results = ["Original document no longer available"]

        self._step(
            f"Place Order browser events: {event_results}"
        )

        self._step(
            f"URL after Place Order: {self.page.url}"
        )

        # --------------------------------------------------
        # 5. Wait for final confirmation and Order ID
        # --------------------------------------------------

        confirmation_patterns = [
            r"Thank\s+you",
            r"Close\s+Call",
            r"order\s+(?:successfully\s+)?placed",
            r"order\s+confirmation"
        ]

        order_id_patterns = [
            (
                r"\b(?:your\s+)?order\s+"
                r"(?:id|number)\s*(?:is\s*)?[:#]?\s*"
                r"([A-Z0-9][A-Z0-9-]{5,})\b"
            ),
            (
                r"\bconfirmation\s+"
                r"(?:id|number)\s*(?:is\s*)?[:#]?\s*"
                r"([A-Z0-9][A-Z0-9-]{5,})\b"
            )
        ]

        confirmation_page = None
        confirmation_frame = None
        confirmation_text = ""
        portal_order_id = None

        self._step(
            "Waiting for final portal confirmation and generated Order ID"
        )

        for attempt in range(60):

            pages = list(self.page.context.pages)

            for current_page in pages:

                for current_frame in current_page.frames:

                    try:
                        body_text = current_frame.locator(
                            "body"
                        ).inner_text(timeout=1500)

                        if not body_text:
                            continue

                        has_confirmation = any(
                            re.search(
                                pattern,
                                body_text,
                                re.I
                            )
                            for pattern in confirmation_patterns
                        )

                        extracted_id = None

                        for pattern in order_id_patterns:

                            match = re.search(
                                pattern,
                                body_text,
                                re.I
                            )

                            if match:
                                extracted_id = match.group(1)
                                break

                        # Both conditions must exist in the same frame.
                        if has_confirmation and extracted_id:

                            confirmation_page = current_page
                            confirmation_frame = current_frame
                            confirmation_text = body_text
                            portal_order_id = extracted_id

                            break

                    except Exception:
                        continue

                if confirmation_page and portal_order_id:
                    break

            if confirmation_page and portal_order_id:
                break

            self.page.wait_for_timeout(1000)

        # --------------------------------------------------
        # 6. Do not report success without the portal ID
        # --------------------------------------------------

        if not confirmation_page or not portal_order_id:

            diagnostic_pages = []

            for current_page in self.page.context.pages:

                page_info = {
                    "url": current_page.url,
                    "frames": []
                }

                for current_frame in current_page.frames:

                    try:
                        text_content = current_frame.locator(
                            "body"
                        ).inner_text(timeout=1000)

                        page_info["frames"].append({
                            "url": current_frame.url,
                            "confirmation_detected": any(
                                re.search(
                                    pattern,
                                    text_content,
                                    re.I
                                )
                                for pattern in confirmation_patterns
                            ),
                            "order_id_detected": any(
                                re.search(
                                    pattern,
                                    text_content,
                                    re.I
                                )
                                for pattern in order_id_patterns
                            )
                        })

                    except Exception:
                        continue

                diagnostic_pages.append(page_info)

            self._step(
                f"Final submission diagnostics: {diagnostic_pages}"
            )

            raise RuntimeError(
                "Final order verification incomplete. "
                f"Portal Order ID: {portal_order_id}. "
                f"Current URL: {self.page.url}. "
                "The order may have been submitted, but final "
                "confirmation was not verified. Check the portal "
                "before attempting another submission."
            )

        # --------------------------------------------------
        # 7. Confirm successful order placement
        # --------------------------------------------------

        self._step(
            "Final confirmation page detected"
        )

        self._step(
            f"Portal order successfully placed. "
            f"Order ID: {portal_order_id}"
        )

        return {
            "status": "ORDER_PLACED",
            "portal_order_id": portal_order_id,
            "confirmation_message": (
                "Final confirmation received. "
                "Portal order successfully placed."
            ),
            "current_url": confirmation_page.url,
            "steps": self.steps,
            "screenshot": None
        }






    def _checkout_and_account(
        self,
        data: dict[str, Any],
        identity_data: dict[str, str] | None = None,
        payment_data: dict[str, str] | None = None,
        cvv: str | None = None
    ):
        order, q, disclosures = data['order'], data['qualification'], data['disclosures']
        frame = self._checkout_frame()


        self._step('Configure checkout services')
        
        # -------------------------------------------------
        # VIDEO, INTERNET AND PHONE ADD-ON SELECTION
        # -------------------------------------------------

        self._step('Configure video and phone add-ons')

        video_packages = {
            'ULTIMATE_TV': r'Ultimate TV',
            'POPULAR_TV': r'Popular TV',
            'WORLD_SOCCER_TICKET': r'World Soccer Ticket',
        }

        phone_packages = {
            'PROVIDERXX_VOICE_PREMIER': r'ProviderXX Voice Premier',
        }

        # Video service
        if order.get('video_service', False):
            video_package = order.get('video_package')

            if video_package not in video_packages:
                raise RuntimeError(
                    f'Unsupported video package: {video_package}'
                )

            self._choose_radio_by_label(
                frame,
                'video',
                video_packages[video_package]
            )
        else:
            self._choose_radio_by_label(
                frame, 'video', r'^None$'
            )

        # Phone service
        if order.get('phone_service', False):
            phone_package = order.get('phone_package')

            if phone_package not in phone_packages:
                raise RuntimeError(
                    f'Unsupported phone package: {phone_package}'
                )

            self._choose_radio_by_label(
                frame,
                'phone',
                phone_packages[phone_package]
            )
        else:
            self._choose_radio_by_label(
                frame, 'phone', r'^None$'
            )

        self._review_pause('video and phone add-on selections')

        forward = frame.locator('input[type="button"][value*="Forward"]')
        self._human_click(forward)
        self._review_pause('checkout service selections')
        frame.wait_for_timeout(500)
        # Broadband labels: select only the choice supplied in the API request.
        label_choice = disclosures['broadband_label_choice']
        self._choose_radio_by_label(frame, 'labels', r'Customer requested' if label_choice == 'REQUESTED' else r'Customer did not request')
        if not disclosures.get('broadband_label_acknowledged', False):
            raise RuntimeError('Customer broadband-label acknowledgement is false; stopped without checking the Read box.')
        # Acknowledgement is represented by the visible Read checkbox on this page.
        read_box = frame.get_by_role('checkbox').first
        self._human_check(read_box)
        equipment_pattern = r'Leased Gateway' if order['equipment_type']=='LEASED_GATEWAY' else r'EQUIPMENT OWN'
        self._choose_radio_by_label(frame, 'equipment', equipment_pattern)
        if order.get('now_tv', False): self._choose_radio_by_label(frame, 'nowtv', r'NOW TV')
        self._review_pause('checkout broadband label and equipment selections')
        forward = frame.locator('input[type="button"][value*="Forward"]')
        self._human_click(forward)
        
        self._step('Fill account-holder and contact information')
        self.page.wait_for_timeout(1500)


        # Account holder is pre-populated from Basic Information.
        holder = frame.get_by_role('combobox', name='Account holder')
        if holder.count():
            pass


        # 1. Verify agent is speaking to the account holder.
        verified = 'Yes' if q['speaking_to_account_holder'] else 'No'

        # Diagnostic: inspect radio buttons on the account-holder page.
        # This intentionally excludes customer field values.
        radio_details = frame.locator(
            'input[type="radio"]'
        ).evaluate_all("""
            elements => elements.map((el, index) => ({
                index: index,
                name: el.name,
                value: el.value,
                id: el.id,
                checked: el.checked,
                visible: !!(
                    el.offsetWidth ||
                    el.offsetHeight ||
                    el.getClientRects().length
                ),
                labels: Array.from(el.labels || [])
                    .map(label => label.innerText.trim()),
                parentText: (
                    el.parentElement?.innerText || ''
                ).trim().slice(0, 200)
            }))
        """)

        print("\\n[ACCOUNT HOLDER RADIO DIAGNOSTIC]")
        print(json.dumps(radio_details, indent=2))

        self._choose_radio_by_label(
            frame, 'verified', rf'^{verified}$'
        )

        if q['speaking_to_account_holder']:
            # Wait for fields revealed after selecting Yes.
            phone_field = frame.get_by_label('Contact phone')
            email_field = frame.get_by_label('Email Address')

            phone_field.wait_for(state='visible', timeout=15000)
            email_field.wait_for(state='visible', timeout=15000)

            self._human_type(phone_field, data['customer']['phone'])
            self._human_type(email_field, data['customer']['email'])

        # 2. Current ProviderXX customer.
        current_choice = (
            'Yes' if q['existing_provider_customer'] else 'No'
        )
        self._choose_radio_by_label(
            frame, 'current', rf'^{current_choice}$'
        )

        # 3. EZ-Enroll.
        ez_choice = 'Yes' if q['ez_enroll'] else 'No'
        self._choose_radio_by_label(
            frame, 'ez', rf'^{ez_choice}$'
        )

        
        # 4. Automatic Payments and Paperless Billing.
        expected_autopay = (
            'Yes' if q['autopay_paperless_discount'] else 'No'
        )

        autopay_radios = frame.locator(
            'input[type="radio"][name="autopay"]'
        )

        selected_radio = None

        # Identify the radio using its actual associated label.
        for index in range(autopay_radios.count()):
            radio = autopay_radios.nth(index)

            label_text = radio.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => label.innerText.trim())
                    .join(' ')
            """)

            if label_text.strip().casefold() == expected_autopay.casefold():
                selected_radio = radio
                break

        if selected_radio is None:
            raise RuntimeError(
                f'Automatic Payments option {expected_autopay} '
                'was not found.'
            )

        # If already selected, verify it. Otherwise select it only
        # when the portal allows the action.
        if not selected_radio.is_checked():
            if not selected_radio.is_enabled():
                raise RuntimeError(
                    f'Automatic Payments option {expected_autopay} '
                    'is disabled and not selected.'
                )

            self._human_check(selected_radio)

        if not selected_radio.is_checked():
            raise RuntimeError(
                'Automatic Payments selection could not be verified.'
            )

        self._step(
            f'Automatic Payments selection verified: {expected_autopay}'
        )

        
            # 5. Step 2 – EZ-Enroll disclosures.
        # The current portal displays TWO Read checkboxes when EZ-Enroll = Yes.
        # Do not expect three checkboxes based on the number of API acknowledgements.

        ez_enroll_selected = bool(q.get('ez_enroll', False))

        if not q.get('autopay_paperless_disclosure_acknowledged', False):
            raise RuntimeError(
                'Automatic Payments and Paperless Billing disclosure '
                'has not been acknowledged.'
            )

        if ez_enroll_selected:
            required_acknowledgements = {
                'account_disclosure_acknowledged': 'Account disclosure',
                'ez_enroll_disclosure_acknowledged': 'EZ-Enroll disclosure',
                'autopay_paperless_disclosure_acknowledged':
                    'Automatic Payments and Paperless Billing disclosure'
            }

            for field_name, label in required_acknowledgements.items():
                if not q.get(field_name, False):
                    raise RuntimeError(
                        f'{label} has not been acknowledged. '
                        'Stopped before selecting Read checkboxes.'
                    )

            expected_read_count = 2
        else:
            expected_read_count = 1

        step2_read_checkboxes = frame.locator(
            'input[type="checkbox"]:visible'
        )

        actual_read_count = step2_read_checkboxes.count()

        if actual_read_count != expected_read_count:
            raise RuntimeError(
                f'Step 2: expected {expected_read_count} visible Read '
                f'checkbox(es), but found {actual_read_count}.'
            )

        for index in range(expected_read_count):
            checkbox = step2_read_checkboxes.nth(index)

            if not checkbox.is_checked():
                self._human_check(checkbox)

            if not checkbox.is_checked():
                raise RuntimeError(
                    f'Step 2 Read checkbox {index + 1} was not selected.'
                )

            self._step(
                f'Step 2 Read checkbox {index + 1} selected and verified'
            )

        self._step(
            f'Step 2 completed - EZ-Enroll '
            f'{"Yes" if ez_enroll_selected else "No"}'
        )



        # 6. Mailing address.
        mailing_choice = (
            'Yes' if q['mailing_same_as_service'] else 'No'
        )
        self._choose_radio_by_label(
            frame, 'mailing', rf'^{mailing_choice}$'
        )

        # 7. Shipping address.
        shipping_choice = (
            'Yes' if q['shipping_same_as_service'] else 'No'
        )
        self._choose_radio_by_label(
            frame, 'shipping', rf'^{shipping_choice}$'
        )

        if (
            not q['mailing_same_as_service']
            or not q['shipping_same_as_service']
        ):
            raise RuntimeError(
                'Separate mailing/shipping addresses require '
                'verified address selectors. Stopped for manual review.'
            )

        self._step('Account-holder qualification selections completed')
        self._review_pause('checkout account-holder and contact information')
        frame.locator(
            'input[type="button"][value*="Forward"]'
        ).click()

        self._step('Continue to installation and payment')

        
        # 1. Credit check - conditional based on EZ-Enroll.
        if q.get('ez_enroll', False):
            self._step('EZ-Enroll selected - credit check not required')
            print(
                '\n[EZ-ENROLL]'
                '\nCredit check is skipped.'
                '\nCustomer credit-card information will be collected '
                'in the payment section.'
            )

        else:
            self._step('Automated Credit Check Required')

            if not identity_data:
                raise RuntimeError(
                    'Encrypted identity handoff is missing. '
                    'Stopped before credit check.'
                )

            ssn_value = identity_data.get('ssn')
            dob_value = identity_data.get('dob')

            if not ssn_value or not dob_value:
                raise RuntimeError(
                    'Identity details are incomplete. '
                    'Stopped before credit check.'
                )

            # The portal's visible labels are not programmatically
            # associated with their input elements. Locate each input
            # using the text label immediately before it.
            
            # Identify the Credit Check panel using its visible heading.
            credit_heading = frame.get_by_text(
                'CREDIT CHECK',
                exact=True
            ).first

            credit_heading.wait_for(
                state='visible',
                timeout=15000
            )

            # Locate the nearest panel containing the credit-check inputs.
            credit_panel = credit_heading.locator(
                "xpath=ancestor::*[.//input"
                "[not(@type='button') and not(@type='submit')]][1]"
            )

            # DOB has a visible, distinctive placeholder in the portal.
            dob_field = credit_panel.locator(
                'input[placeholder="MM/DD/YYYY"]'
            )

            # The SSN field is the other editable input in this panel.
            ssn_field = credit_panel.locator(
                'input:not([type="button"]):not([type="submit"]):not([type="hidden"]):not([placeholder="MM/DD/YYYY"])'
            )

            if (
                dob_field.count() != 1
                or ssn_field.count() != 1
                or not dob_field.is_visible()
                or not ssn_field.is_visible()
                or not dob_field.is_enabled()
                or not ssn_field.is_enabled()
            ):
                raise RuntimeError(
                    'Credit Check SSN/DOB fields could not be identified '
                    'inside the Credit Check panel.'
                )

            self._step('Credit-check identity fields identified')


            # Enter identity directly into the provider portal.
            # Values are not printed, saved, or included in screenshots.
            self._human_type(ssn_field, ssn_value)
            self._human_type(dob_field, dob_value)

            self._step('Credit-check identity fields populated')

            # Locate the Run Credit Check control.
            run_credit_check = frame.get_by_role(
                'button',
                name=re.compile(r'Run Credit Check', re.I)
            )

            if run_credit_check.count() == 0:
                run_credit_check = frame.locator(
                    'input[type="button"][value*="Run Credit Check"], '
                    'input[type="submit"][value*="Run Credit Check"]'
                )

            if (
                run_credit_check.count() != 1
                or not run_credit_check.is_visible()
                or not run_credit_check.is_enabled()
            ):
                raise RuntimeError(
                    'Run Credit Check button was not found uniquely '
                    'or is disabled. Stopped for manual review.'
                )

            self._human_click(run_credit_check)
            self._step('Run Credit Check submitted')

            # Wait for an explicit approved or unsuccessful result.
            try:
                frame.wait_for_function(
                    """() => {
                        const text = document.body.innerText;

                        const approved =
                            /Credit Check Status:\\s*APPROVED/i.test(text) &&
                            /Processing Status:\\s*SUCCESS/i.test(text) &&
                            /LineItem Status:\\s*SUCCESS/i.test(text);

                        const unsuccessful =
                            /Credit Check Status:\\s*(DECLINED|REJECTED|FAILED|ERROR)/i.test(text) ||
                            /Processing Status:\\s*(FAILURE|FAILED|ERROR)/i.test(text) ||
                            /LineItem Status:\\s*(FAILURE|FAILED|ERROR)/i.test(text);

                        return approved || unsuccessful;
                    }""",
                    timeout=120000
                )

            except PlaywrightTimeoutError:
                raise RuntimeError(
                    'Credit-check result was not confirmed within '
                    '120 seconds. Stopped for manual review.'
                )

            # Read only status indicators. Do not log the page contents.
            credit_result = frame.evaluate(
                """() => {
                    const text = document.body.innerText;

                    return {
                        approved:
                            /Credit Check Status:\\s*APPROVED/i.test(text) &&
                            /Processing Status:\\s*SUCCESS/i.test(text) &&
                            /LineItem Status:\\s*SUCCESS/i.test(text),

                        unsuccessful:
                            /Credit Check Status:\\s*(DECLINED|REJECTED|FAILED|ERROR)/i.test(text) ||
                            /Processing Status:\\s*(FAILURE|FAILED|ERROR)/i.test(text) ||
                            /LineItem Status:\\s*(FAILURE|FAILED|ERROR)/i.test(text)
                    };
                }"""
            )

            if not credit_result.get('approved'):
                raise RuntimeError(
                    'Credit check was not approved. '
                    'Stopped for manual review; installation and '
                    'payment workflow will not continue.'
                )

            self._step(
                'Credit Check APPROVED - Processing SUCCESS - LineItem SUCCESS'
            )


        # 2. Select installation.
        installation = data['installation']
        installation_type = installation['installation_type']
        if installation_type == 'PRO_INSTALL':
            self._step('Select Professional Installation')
            self._select_installation_radio(
                frame,
                'PRO_INSTALL',
                'PRO INSTALL'
            )

            if not installation.get(
                'installation_disclosure_acknowledged', False
            ):
                raise RuntimeError(
                    'Professional installation disclosures have not '
                    'both been acknowledged by the customer. '
                    'Stopped before checking either Read box.'
                )

            read_boxes = frame.locator(
                'input[type="checkbox"]:visible'
            )
            if read_boxes.count() != 2:
                raise RuntimeError(
                    'Expected two visible installation disclosure '
                    f'checkboxes, found {read_boxes.count()}.'
                )

            # First installation disclosure.
            first_install_read = read_boxes.nth(0)

            if not first_install_read.is_checked():
                self._human_check(first_install_read)

            if not first_install_read.is_checked():
                raise RuntimeError(
                    'First installation disclosure was not checked.'
                )

            self._step('First installation disclosure acknowledged')

            preferred_date = installation.get('preferred_date')
            if not preferred_date:
                raise RuntimeError(
                    'Professional installation date is missing.'
                )

            date_field = frame.locator(
                'input[type="date"]:visible'
            ).first
            date_field.wait_for(state='visible', timeout=15000)
            self._human_click(date_field)
            date_field.fill(preferred_date)
            self.page.wait_for_timeout(random.randint(500, 900))

            # Verify the date actually selected in the portal.
            actual_date = date_field.input_value()
            if actual_date != preferred_date:
                raise RuntimeError(
                    f'Installation date verification failed. '
                    f'Expected: {preferred_date}, '
                    f'Actual: {actual_date}'
                )

            self._step(
                f'Installation date verified: {actual_date}'
            )

            preferred_time = installation.get('preferred_time')
            if preferred_time not in ('Morning', 'Afternoon', 'Evening'):
                raise RuntimeError(
                    'Invalid installation time. '
                    'Choose Morning, Afternoon or Evening.'
                )

            time_selected = False
            selects = frame.locator('select:visible')
            for i in range(selects.count()):
                select = selects.nth(i)
                option_labels = select.locator('option').all_text_contents()
                if any(
                    preferred_time.lower() in option.lower()
                    for option in option_labels
                ):
                    self._human_select(select, label=preferred_time)

                    # Read back the selected option from the portal.
                    selected_time_label = select.locator(
                        'option:checked'
                    ).inner_text().strip()

                    if preferred_time.casefold() not in selected_time_label.casefold():
                        raise RuntimeError(
                            f'Installation time verification failed. '
                            f'Expected: {preferred_time}, '
                            f'Actual: {selected_time_label}'
                        )

                    self._step(
                        f'Installation time verified: {selected_time_label}'
                    )

                    time_selected = True
                    break


            if not time_selected:
                raise RuntimeError(
                    f'Could not find installation time option: '
                    f'{preferred_time}'
                )
            self._step(
                f'Professional installation configured: '
                f'{preferred_date}, {preferred_time}'
            )

            # Second installation disclosure, after date and time selection.
            second_install_read = read_boxes.nth(1)

            if not second_install_read.is_checked():
                self._human_check(second_install_read)

            if not second_install_read.is_checked():
                raise RuntimeError(
                    'Second installation disclosure was not checked.'
                )

            self._step('Second installation disclosure acknowledged')
        
        elif installation_type == 'STANDARD_SHIPPING':
            self._step('Select Standard Shipping')

            self._select_installation_radio(
                frame,
                'STANDARD_SHIPPING',
                'STANDARD SHIPPING'
            )

            self._step('Standard Shipping selected and verified')

            if not installation.get(
                'installation_disclosure_acknowledged', False
            ):
                raise RuntimeError(
                    'Standard Shipping installation disclosure '
                    'has not been acknowledged.'
                )

            self._step(
                'Standard Shipping installation acknowledgement verified'
            )


        
        
        # Confirm the selected installation type.
        
        # -------------------------------------------------
        # INSTALLATION NAVIGATION - CASE 1 / CASE 2
        # -------------------------------------------------

        self._screenshot('full_flow_03_installation_configured')

        ez_enroll = bool(q.get('ez_enroll', False))

        self._step(
            f'Installation navigation decision: EZ-Enroll={q.get("ez_enroll")}'
        )

        
        if not ez_enroll:
            # Step 3: Confirm Installation
            self._step("Case 1: Confirm Standard Shipping installation")

            confirm = frame.locator(
                'input.cbtn[value="Confirm Installation >"]'
            )

            confirm.wait_for(state="visible", timeout=20000)

            if not confirm.is_enabled():
                raise RuntimeError("Confirm Installation button is disabled.")

            self._human_click(confirm)

            self._step("Case 1: Confirm Installation clicked")

            # Forward appears after Confirm Installation
            forward = frame.locator(
                'input[type="button"][value*="Forward"]:visible'
            ).last

            forward.wait_for(state="visible", timeout=20000)

            if not forward.is_enabled():
                raise RuntimeError("Step 3 Forward button is disabled.")

            self._human_click(forward)

            self._step("Case 1: Forward clicked; waiting for Step 4")

            # Step 4: Authorization
            frame.get_by_text(
                "ORDER REVIEW",
                exact=True
            ).wait_for(state="visible", timeout=30000)

            self._step("Case 1: Step 4 Authorization page loaded")

            # Acknowledge the single visible Read checkbox
            read_checkbox = frame.locator(
                'input[type="checkbox"]:visible'
            )

            if read_checkbox.count() != 1:
                raise RuntimeError(
                    f"Expected one visible Step 4 Read checkbox, "
                    f"found {read_checkbox.count()}."
                )

            if not read_checkbox.is_checked():
                self._human_check(read_checkbox)

            self._step("Case 1: Read checkbox acknowledged")

            # Submit the order
            submit_order = frame.get_by_role(
                "button",
                name="Submit Order",
                exact=True
            )

            if submit_order.count() == 0:
                submit_order = frame.locator(
                    'input[type="button"][value="Submit Order"]:visible'
                )

            submit_order.wait_for(state="visible", timeout=20000)
            self._human_click(submit_order)

            # Complete final submission and extract portal Order ID.
            self._step("Case 1: Order Summary reached")

            result = self._place_order_and_get_portal_id(frame)

            result["message"] = (
                "Case 1 order successfully placed. "
                "Portal confirmation and Order ID received."
            )

            return result

        else:

            # CASE 2: EZ-Enroll YES
            # Confirm Installation opens the payment workflow.

            self._step(
                'Case 2: Confirm selected installation type'
            )

            confirm = frame.locator(
                'input.cbtn[value="Confirm Installation >"]'
            )

            confirm.wait_for(
                state='visible',
                timeout=15000
            )

            if not confirm.is_enabled():
                raise RuntimeError(
                    'Case 2 Confirm Installation button is disabled.'
                )

            self._step('Clicking Confirm Installation')
            self._human_click(confirm)

            self._step('Case 2 installation confirmed')


        # Wait for the payment-hold disclosure.
        payment_hold_box = frame.locator(
            '.box.tinted'
        ).filter(
            has_text='To confirm the card has sufficient funds'
        ).first

        payment_hold_box.wait_for(
            state='visible',
            timeout=20000
        )

        self._step('Payment hold disclosure displayed')

        payment_read = payment_hold_box.locator(
            'label.m-read input[type="checkbox"]'
        )

        if payment_read.count() != 1:
            raise RuntimeError(
                'Expected exactly one payment-hold Read checkbox.'
            )

        if not payment_read.is_checked():
            self._human_check(payment_read)

        if not payment_read.is_checked():
            raise RuntimeError(
                'Payment-hold Read checkbox was not checked.'
            )

        self._step('Payment-hold Read checkbox acknowledged')

        # Wait for Payment Information.
        payment_section = frame.locator('.box.payinfo')

        payment_section.wait_for(
            state='visible',
            timeout=20000
        )

        self._step('Payment Information section displayed')


        
        # Select Add a new credit card.
        add_card_label = payment_section.locator(
            'label.g-opt'
        ).filter(
            has_text='Add a new credit card'
        ).first

        add_card_radio = add_card_label.locator(
            'input[type="radio"]'
        )

        if not add_card_radio.is_checked():
            add_card_label.click()

        if not add_card_radio.is_checked():
            raise RuntimeError(
                'Could not select Add a new credit card.'
            )

        self._step('Add a new credit card selected')

        # Select the credit-card billing address option.
        billing_same = disclosures.get(
            'credit_card_billing_same_as_service',
            True
        )

        billing_option = (
            'Yes' if billing_same else 'No'
        )

        billing_label = payment_section.locator(
            '.billing label'
        ).filter(
            has_text=billing_option
        ).first

        billing_radio = billing_label.locator(
            'input[type="radio"]'
        )

        if not billing_radio.is_checked():
            billing_label.click()

        if not billing_radio.is_checked():
            raise RuntimeError(
                f'Could not select billing address: {billing_option}'
            )

        self._step(
            f'Credit-card billing address selected: {billing_option}'
        )


        # Confirm Installation reveals the payment section.
        
        
        # -------------------------------------------------
        # CHECK WHETHER PRE-PAYMENT IS REQUIRED
        # -------------------------------------------------

        self._step('Inspect payment requirement after installation')

        frame.wait_for_timeout(3000)

        payment_page_text = frame.locator('body').inner_text()

        no_prepayment_required = (
            re.search(
                r'Credit Check Status:\s*APPROVED.*?'
                r'no pre-payment required',
                payment_page_text,
                re.I | re.S
            ) is not None
            and re.search(
                r'Pre-Payment:\s*\$0\.00',
                payment_page_text,
                re.I
            ) is not None
        )

        if no_prepayment_required:
            self._step(
                'Portal confirmed APPROVED - no pre-payment required'
            )

            # Credit approved with no pre-payment.
            # The portal proceeds to Step 4 Authorization.
            self._step('Open Step 4 Authorization')

            forward = frame.locator(
                'input[type="button"][value*="Forward"]:visible'
            ).last

            if not forward.count():
                forward = frame.get_by_role(
                    'button',
                    name=re.compile(r'Forward', re.I)
                ).last

            forward.wait_for(state='visible', timeout=20000)

            if not forward.is_enabled():
                raise RuntimeError(
                    'Forward button is disabled after credit approval.'
                )

            self._human_click(forward)

            # Wait for the actual Authorization page.
            
            # Wait for Step 4 Authorization / Order Review.
            frame.get_by_text(
                'ORDER REVIEW',
                exact=True
            ).wait_for(
                state='visible',
                timeout=30000
            )

            self._step('Step 4 Authorization page loaded')

            # Locate the Step 4 Read checkbox.
            authorization_read = frame.locator(
                'input[type="checkbox"]:visible'
            )

            if authorization_read.count() != 1:
                raise RuntimeError(
                    'Expected exactly one visible Step 4 Read checkbox, '
                    f'but found {authorization_read.count()}.'
                )

            authorization_read = authorization_read.first

            if not authorization_read.is_checked():
                self._human_check(authorization_read)

            if not authorization_read.is_checked():
                raise RuntimeError(
                    'Step 4 authorization Read checkbox was not selected.'
                )

            self._step('Step 4 authorization Read checkbox verified')

            # Find and submit the order.
            submit_order = frame.get_by_role(
                'button',
                name=re.compile(r'^Submit Order$', re.I)
            )

            if submit_order.count() == 0:
                submit_order = frame.locator(
                    'input[type="button"][value="Submit Order"], '
                    'input[type="submit"][value="Submit Order"]'
                )

            if (
                submit_order.count() != 1
                or not submit_order.is_visible()
                or not submit_order.is_enabled()
            ):
                raise RuntimeError(
                    'Submit Order button was not found uniquely or is disabled.'
                )

            self._step('Submitting authorized order')
            self._human_click(submit_order)

            # Wait for the main page to navigate to Order Summary.
            # The checkout iframe is replaced during this navigation.
            self._step("Waiting for Case 2 Order Summary navigation")

            self.page.wait_for_url(
                re.compile(r".*/order-summary(?:/|\?).*"),
                timeout=60000
            )

            self._step(
                f"Case 2 Order Summary page loaded: {self.page.url}"
            )

            result = self._place_order_and_get_portal_id(frame)

            result["message"] = (
                "Case 2 order successfully placed. "
                "Portal confirmation and Order ID received."
            )

            return result


        self._step(
            'Pre-payment required or approval state not confirmed; '
            'continue to secure payment workflow'
        )


        
        # -------------------------------------------------
        # 7. PAYMENT PAGE - EZ-ENROLL
        # -------------------------------------------------

        self._step('Wait for Payment Information section')

        frame.get_by_text(
            'PAYMENT INFORMATION',
            exact=True
        ).wait_for(state='visible', timeout=30000)

        self._screenshot('full_flow_04_payment_page')

        # Payment disclosure appears after Confirm Installation.
        if not disclosures.get('payment_disclosure_acknowledged', False):
            raise RuntimeError(
                'Payment disclosure acknowledgement is not confirmed.'
            )

        payment_heading = frame.get_by_text(
            'PAYMENT INFORMATION', exact=True
        ).first
        payment_heading.wait_for(state='visible', timeout=30000)

        # Scope the checkbox lookup to the Payment Information panel.
        # Step 2's three checkboxes must never be counted or reused here.
        payment_section = payment_heading.locator(
            'xpath=ancestor::*[.//input[@type="checkbox"]][1]'
        )
        payment_checkboxes = payment_section.locator(
            'input[type="checkbox"]:visible'
        )
        count = payment_checkboxes.count()

        if count != 1:
            raise RuntimeError(
                'Expected exactly one Step 3 Payment Information Read checkbox, '
                f'but found {count} inside the Payment Information section.'
            )

        payment_read = payment_checkboxes.first

        if not payment_read.is_checked():
            self._human_check(payment_read)

        if not payment_read.is_checked():
            raise RuntimeError(
                'Card-payment disclosure Read checkbox was not checked.'
            )

        self._step('Card-payment disclosure acknowledged')

        # 2. Click Add a New Credit Card. Some portal builds render this
        # as a button; others render it as a radio option with that label.
        add_card_button = frame.get_by_role(
            'button', name=re.compile(r'Add a New Credit Card', re.I)
        )
        if add_card_button.count() == 0:
            add_card_button = frame.locator(
                'input[type="button"][value*="Add a New Credit Card"], '
                'input[type="submit"][value*="Add a New Credit Card"]'
            )

        if add_card_button.count() == 1 and add_card_button.is_visible():
            self._human_click(add_card_button)
        else:
            add_card_radios = frame.locator(
                'input[type="radio"][name="addcard"]'
            )
            add_card_selected = False
            for index in range(add_card_radios.count()):
                radio = add_card_radios.nth(index)
                label_text = radio.evaluate("""
                    el => Array.from(el.labels || [])
                        .map(label => label.innerText.trim()).join(' ')
                """)
                if re.search(r'Add a New Credit Card', label_text, re.I):
                    self._human_check(radio)
                    add_card_selected = radio.is_checked()
                    break
            if not add_card_selected:
                raise RuntimeError(
                    'Add a New Credit Card button/option was not found or selected.'
                )

        self._step('Add a new credit card selected')

        # 3. Select billing address only when customer confirms.
        billing_choice = disclosures.get(
            'credit_card_billing_same_as_service'
        )

        if billing_choice is not True:
            raise RuntimeError(
                'Customer has not confirmed that card billing address '
                'matches service address. Stopped for manual review.'
            )

        billing_radios = frame.locator(
            'input[type="radio"][name="billing"]'
        )

        billing_yes = None

        for i in range(billing_radios.count()):
            radio = billing_radios.nth(i)

            label = radio.evaluate("""
                el => {
                    const labels = Array.from(el.labels || []);
                    return labels.map(x => x.innerText).join(' ').trim();
                }
            """)

            if label.casefold() == 'yes':
                billing_yes = radio
                break

        if billing_yes is None:
            raise RuntimeError(
                'Billing address Yes option was not found.'
            )

        self._human_check(billing_yes)

        if not billing_yes.is_checked():
            raise RuntimeError(
                'Billing address Yes selection failed.'
            )

        self._step('Card billing address confirmed as service address')

        # 4. Activate secure card fields.
        edit_secure = frame.locator(
            'input[type="button"][value*="Edit Secure Fields"], '
            'button:has-text("Edit Secure Fields")'
        )

        edit_secure.wait_for(
            state='visible',
            timeout=20000
        )

        self._human_click(edit_secure)


        # Diagnose secure card fields without reading or printing
        # any card number, CVV, or entered field values.
        self._step('Inspect secure card field selectors')

        self.page.wait_for_timeout(1500)

        secure_field_details = frame.locator(
            'input:visible, select:visible'
        ).evaluate_all("""
            elements => elements.map((el, index) => ({
                index: index,
                tag: el.tagName,
                type: el.getAttribute('type') || '',
                id: el.id || '',
                name: el.getAttribute('name') || '',
                placeholder: el.getAttribute('placeholder') || '',
                aria_label: el.getAttribute('aria-label') || '',
                autocomplete: el.getAttribute('autocomplete') || '',
                labels: Array.from(el.labels || [])
                    .map(label => label.innerText.trim()),
                class_name: String(el.className || '')
            }))
        """)

        print('\\n[SECURE CARD FIELD SELECTORS]')
        print(json.dumps(secure_field_details, indent=2))


        card_type_dropdown = frame.locator('select:visible').last

        card_type_dropdown.wait_for(
            state='visible',
            timeout=15000
        )

        card_options = card_type_dropdown.locator('option').evaluate_all("""
            options => options.map(option => ({
                label: option.textContent.trim(),
                value: option.value,
                disabled: option.disabled
            }))
        """)

        print('[CARD TYPE OPTIONS]')
        print(json.dumps(card_options, indent=2))
        self._step('Secure card fields activated')

        # 5. Manual secure card entry.
        
        # 5. Populate simulator card details.
        # Credentials are supplied at runtime and are never logged.
        self._step('Populate secure simulator card fields')

        # Disable screenshots once sensitive card information is used.
        self._sensitive_data_active = True

        if not isinstance(payment_data, dict) or not cvv:
            raise RuntimeError(
                'Decrypted payment details and transient CVV were not supplied '
                'to the browser automation.'
            )

        # These values are decrypted upstream and passed only in memory.
        card_type = str(payment_data.get('card_type', '')).strip()
        card_number = str(payment_data.get('card_number', '')).strip()
        cardholder_name = str(payment_data.get('cardholder_name', '')).strip()
        exp_month = str(payment_data.get('expiry_month', '')).strip()
        exp_year = str(payment_data.get('expiry_year', '')).strip()
        cvv = str(cvv).strip()

        allowed_card_types = {
            'Visa',
            'MasterCard',
            'American Express',
            'Discover'
        }

        if card_type not in allowed_card_types:
            raise RuntimeError('Invalid or missing simulator card type.')

        card_number = re.sub(r'[\s-]', '', card_number)

        if not card_number.isdigit() or not 12 <= len(card_number) <= 19:
            raise RuntimeError('Simulator card number is missing or invalid.')

        if not cardholder_name:
            raise RuntimeError('Simulator cardholder name is missing.')

        if not cvv.isdigit() or len(cvv) not in (3, 4):
            raise RuntimeError('Simulator CVV is missing or invalid.')

        if not exp_month.isdigit() or not 1 <= int(exp_month) <= 12:
            raise RuntimeError('Simulator expiration month is invalid.')

        if not re.fullmatch(r'\d{4}', exp_year):
            raise RuntimeError('Simulator expiration year must have four digits.')

        # Locate the exact fields identified by the DOM diagnostic.
        card_type_field = frame.get_by_label('Card Type')
        card_number_field = frame.get_by_label('Card Number')
        cardholder_field = frame.get_by_label('Card Holder Name')
        cvv_field = frame.get_by_label('CVV Code')
        month_field = frame.get_by_label('Expiration month')
        year_field = frame.get_by_label('Expiration year')

        fields = [
            card_type_field,
            card_number_field,
            cardholder_field,
            cvv_field,
            month_field,
            year_field
        ]

        if any(field.count() != 1 or not field.is_visible()
               for field in fields):
            raise RuntimeError(
                'One or more secure card fields were not found uniquely.'
            )

        # Select card type.
        card_type_field.select_option(label=card_type)

        # Fill each secure field and move focus away to trigger portal validation.
        card_number_field.fill(card_number)
        card_number_field.press('Tab')
        cardholder_field.fill(cardholder_name)
        cardholder_field.press('Tab')
        cvv_field.fill(cvv)
        cvv_field.press('Tab')
        month_field.fill(exp_month.zfill(2))
        month_field.press('Tab')
        year_field.fill(exp_year)
        year_field.press('Tab')

        # Verify presence without reading or printing sensitive values.
        if not all([
            bool(card_type_field.input_value()),
            bool(card_number_field.input_value()),
            bool(cardholder_field.input_value()),
            bool(cvv_field.input_value()),
            bool(month_field.input_value()),
            bool(year_field.input_value())
        ]):
            raise RuntimeError(
                'Secure card field population could not be verified.'
            )

        self._step('Simulator card fields populated and verified')

        # Clear local references as soon as field population is complete.
        card_number = None
        cvv = None
        cardholder_name = None
        exp_month = None
        exp_year = None


       
        # -------------------------------------------------
        # 8. CONTINUE TO STEP 4 AUTHORIZATION
        # -------------------------------------------------

        forward = frame.locator(
            'input[type="button"][value*="Forward"]:visible'
        ).last

        forward.wait_for(
            state='visible',
            timeout=20000
        )

        if not forward.is_enabled():
            raise RuntimeError(
                'Payment Forward button is disabled.'
            )

        self._step('Continue from payment page to Step 4 Authorization')
        self._human_click(forward)

        # Wait for Step 4 Order Review.
        frame.get_by_text(
            'ORDER REVIEW',
            exact=True
        ).wait_for(
            state='visible',
            timeout=30000
        )

        self._step('Step 4 Authorization page loaded')

        # -------------------------------------------------
        # 9. STEP 4 AUTHORIZATION READ CHECKBOX
        # -------------------------------------------------

        authorization_checkboxes = frame.locator(
            'input[type="checkbox"]:visible'
        )

        authorization_count = authorization_checkboxes.count()

        if authorization_count != 1:
            raise RuntimeError(
                'Expected exactly one visible Step 4 Read checkbox, '
                f'but found {authorization_count}.'
            )

        authorization_read = authorization_checkboxes.first

        if not authorization_read.is_checked():
            self._human_check(authorization_read)

        if not authorization_read.is_checked():
            raise RuntimeError(
                'Step 4 authorization Read checkbox was not selected.'
            )

        self._step('Step 4 authorization Read checkbox verified')

        # -------------------------------------------------
        # 10. SUBMIT ORDER
        # -------------------------------------------------

        submit_order = frame.get_by_role(
            'button',
            name=re.compile(r'^Submit Order$', re.I)
        )

        if submit_order.count() == 0:
            submit_order = frame.locator(
                'input[type="button"][value="Submit Order"], '
                'input[type="submit"][value="Submit Order"]'
            )

        if (
            submit_order.count() != 1
            or not submit_order.is_visible()
            or not submit_order.is_enabled()
        ):
            raise RuntimeError(
                'Submit Order button was not found uniquely or is disabled.'
            )

        self._step('Submitting Case 2 simulator order')
        self._human_click(submit_order)

        # -------------------------------------------------
        # 11. WAIT FOR FINAL ORDER SUMMARY
        # -------------------------------------------------

        # -------------------------------------------------
        # 11. WAIT FOR FINAL ORDER SUMMARY
        # -------------------------------------------------

        self._step(
            "Waiting for Case 2 Order Summary navigation"
        )

        # The checkout iframe is detached when the portal
        # navigates to the parent-page Order Summary.
        # Always wait using self.page, never the old frame.

        self.page.wait_for_url(
            re.compile(r".*/order-summary(?:/|\?).*"),
            timeout=60000
        )

        self._step(
            f"Case 2 Order Summary page loaded: {self.page.url}"
        )

        # Continue to the final Place Order page action.
        result = self._place_order_and_get_portal_id(frame)

        result["message"] = (
            "Case 2 order successfully placed. "
            "Payment and authorization completed; portal Order ID received."
        )

        return result



    def run_full_order(
        self,
        data: dict[str, Any],
        identity_data: dict[str, str] | None = None,
        payment_data: dict[str, str] | None = None,
        cvv: str | None = None
    ):
        with sync_playwright() as p:
            self.playwright = p
            
            self.browser = p.chromium.launch(
                headless=False,
                args=[
                    "--window-size=1580,600",
                    "--window-position=0,0"
                ]
            )

            self.context = self.browser.new_context(
                viewport={
                "width": 1580,
                "height": 800
                }
            )


            self.page = self.context.new_page()

            self._sensitive_data_active = (
                identity_data is not None
                or payment_data is not None
                or cvv is not None
            )

            try:
                self._login_and_start()
                self._fill_basic_information(data)
                self._select_customer_type(data['order'])
                self._select_provider_and_plan(data['order'])
                result = self._checkout_and_account(
                    data,
                    identity_data=identity_data,
                    payment_data=payment_data,
                    cvv=cvv
                )
                self._run_succeeded = True
                return result
            except Exception as exc:
                try:
                    self._screenshot('full_flow_error')
                except Exception:
                    pass
                print('[AUTOMATION] Browser will remain open for 120 seconds for inspection.')
                try:
                    self.page.wait_for_timeout(120000)
                except Exception:
                    pass
                return {
                    "status": "MANUAL_REVIEW_REQUIRED",
                    "error": str(exc),
                    "current_url": self.page.url if self.page else None,
                    "steps": self.steps,
                    "screenshot": (
                        None if self._sensitive_data_active
                        else str(DATA_DIR / "full_flow_error.png")
                    )
                }
            finally:
                # On failure keep the visible browser open briefly so the portal state
                # can be inspected. Successful runs close normally.
                if self.context and self.steps and getattr(self, '_run_succeeded', False):
                    self.context.close()
                    if self.browser:
                        self.browser.close()
