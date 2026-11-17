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

    
    def _choose_radio_by_label(self, frame, name: str, pattern: str, required=True):
        radios = frame.locator(
            f'input[type="radio"][name="{name}"]'
        )

        for i in range(radios.count()):
            radio = radios.nth(i)

            value = radio.get_attribute("value") or ""

            # First match the actual radio value.
            if re.search(pattern, value, re.I):
                if radio.is_visible() and radio.is_enabled():
                    self._human_check(radio)
                    return

            # Otherwise inspect the labels associated with this radio.
            label_text = radio.evaluate("""
                el => {
                    const labels = Array.from(el.labels || []);
                    if (labels.length) {
                        return labels.map(label => label.innerText).join(' ');
                    }

                    return el.parentElement?.innerText || '';
                }
            """)

            # Remove exact-match anchors when checking surrounding label text.
            flexible_pattern = pattern.replace('^', '').replace('$', '')

            if re.search(flexible_pattern, label_text, re.I):
                if radio.is_visible() and radio.is_enabled():
                    self._human_check(radio)
                    return

        if required:
            raise RuntimeError(
                f'Could not select {name} radio option matching {pattern!r}. '
                f'Available values: '
                f'{[radios.nth(i).get_attribute("value") for i in range(radios.count())]}'
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


    def _checkout_and_account(
        self,
        data: dict[str, Any],
        identity_data: dict[str, str] | None = None
    ):
        order, q, disclosures = data['order'], data['qualification'], data['disclosures']
        frame = self._checkout_frame()


        # Diagnostic: inspect checkout radio controls.
        # Do not collect customer or payment field values.
        radio_details = frame.locator(
            'input[type="radio"]'
        ).evaluate_all("""
            elements => elements.map((el, index) => ({
                index: index,
                name: el.name,
                value: el.value,
                checked: el.checked,
                disabled: el.disabled,
                visible: !!(
                    el.offsetWidth ||
                    el.offsetHeight ||
                    el.getClientRects().length
                ),
                labels: Array.from(el.labels || [])
                    .map(label => label.innerText.trim()),
                parent_text: (
                    el.parentElement?.innerText || ''
                ).trim().slice(0, 200)
            }))
        """)

        print('\\n[CHECKOUT RADIO DIAGNOSTIC]')
        print(json.dumps(radio_details, indent=2))

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

        # Account holder is pre-populated from Basic Information.
        holder = frame.get_by_role('combobox', name='Account holder')
        if holder.count():
            pass

        # 1. Verify agent is speaking to the account holder.
        verified = 'Yes' if q['speaking_to_account_holder'] else 'No'

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

        
        # 5. Step 2 contains exactly two Read checkboxes,
        # regardless of whether EZ-Enroll is Yes or No.
        #
        # Both disclosures must have been reviewed and acknowledged.
        if not q.get('account_disclosure_acknowledged', False):
            raise RuntimeError(
                'First Step 2 disclosure has not been acknowledged.'
            )

        if not q.get(
            'autopay_paperless_disclosure_acknowledged', False
        ):
            raise RuntimeError(
                'Second Step 2 disclosure has not been acknowledged.'
            )

        read_checkboxes = frame.locator(
            'input[type="checkbox"]:visible'
        )

        read_count = read_checkboxes.count()

        if read_count != 2:
            raise RuntimeError(
                'Expected exactly two visible Step 2 Read checkboxes, '
                f'but found {read_count}. '
                'Stopped before clicking Forward.'
            )

        for index in range(2):
            checkbox = read_checkboxes.nth(index)

            if not checkbox.is_checked():
                self._human_check(checkbox)

            if not checkbox.is_checked():
                raise RuntimeError(
                    f'Step 2 Read checkbox {index + 1} '
                    'could not be verified.'
                )

            self._step(
                f'Step 2 Read checkbox {index + 1} verified'
            )

        if not all(
            read_checkboxes.nth(i).is_checked()
            for i in range(2)
        ):
            raise RuntimeError(
                'Both Step 2 Read checkboxes were not verified.'
            )

        self._step(
            'Both Step 2 disclosure acknowledgements completed'
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

            ssn_field = frame.get_by_label('Social Security Number')
            dob_field = frame.get_by_label('Date of Birth')

            if (
                ssn_field.count() != 1
                or dob_field.count() != 1
                or not ssn_field.is_visible()
                or not dob_field.is_visible()
            ):
                raise RuntimeError(
                    'Credit-check identity fields were not found uniquely. '
                    'Stopped for manual review.'
                )

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
            self._choose_radio_by_label(frame, 'itype', r'PRO_INSTALL')

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
            self._choose_radio_by_label(
                frame, 'itype', r'STANDARD_SHIPPING'
            )
        else:
            raise RuntimeError(
                f'Unsupported installation type: {installation_type}'
            )

        self._screenshot('full_flow_03_installation_configured')
        confirm = frame.locator(
            'input[type="button"][value*="Confirm Installation"]'
        )
        if not confirm.count() or not confirm.is_visible():
            raise RuntimeError(
                'Confirm Installation button was not found.'
            )
        self._human_click(confirm)
        self._step('Installation selection confirmed')

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

            # Do not enter card details when the portal explicitly
            # confirms that no pre-payment is required.
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

            self._step(
                'Continue from approved no-prepayment page'
            )

            self._human_click(forward)

            # Verify that Order Summary actually loads.
            self.page.wait_for_url(
                re.compile(r'.*/order-summary/.*'),
                timeout=60000
            )

            self._step('Order Summary page loaded')

            # Sensitive identity data was used during this run.
            # Do not capture screenshots of the page.
            self.page.wait_for_timeout(120000)

            return {
                'status': 'ORDER_SUMMARY_REACHED',
                'current_url': self.page.url,
                'steps': self.steps,
                'screenshot': None,
                'message': (
                    'Order Summary reached after approved credit check. '
                    'No pre-payment was required. '
                    'Final order submission and payment were not performed.'
                )
            }

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

        payment_checkboxes = frame.locator(
            'input[type="checkbox"]:visible'
        )

        count = payment_checkboxes.count()

        print(f'[PAYMENT] Visible Read checkboxes after confirmation: {count}')

        if count < 1:
            raise RuntimeError(
                'Payment disclosure Read checkbox was not found.'
            )

        # The last visible Read checkbox belongs to the newly opened
        # card-payment disclosure.
        payment_read = payment_checkboxes.last

        if not payment_read.is_checked():
            self._human_check(payment_read)

        if not payment_read.is_checked():
            raise RuntimeError(
                'Card-payment disclosure Read checkbox was not checked.'
            )

        self._step('Card-payment disclosure acknowledged')

        # 2. Select Add a new credit card.
        add_card_radios = frame.locator(
            'input[type="radio"][name="addcard"]'
        )

        add_card_selected = False

        for i in range(add_card_radios.count()):
            radio = add_card_radios.nth(i)

            label = radio.evaluate("""
                el => {
                    const labels = Array.from(el.labels || []);
                    return labels.map(x => x.innerText).join(' ');
                }
            """)

            if 'Add a new credit card' in label:
                self._human_check(radio)
                add_card_selected = True
                break

        if not add_card_selected:
            raise RuntimeError(
                'Add a new credit card option was not found.'
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

        card_type = os.getenv('SIM_CARD_TYPE', '').strip()
        card_number = os.getenv('SIM_CARD_NUMBER', '').strip()
        cardholder_name = os.getenv('SIM_CARDHOLDER_NAME', '').strip()
        cvv = os.getenv('SIM_CVV', '').strip()
        exp_month = os.getenv('SIM_EXP_MONTH', '').strip()
        exp_year = os.getenv('SIM_EXP_YEAR', '').strip()

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

        # Fill the secure fields.
        card_number_field.fill(card_number)
        cardholder_field.fill(cardholder_name)
        cvv_field.fill(cvv)
        month_field.fill(exp_month.zfill(2))
        year_field.fill(exp_year)

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


        # Continue to Order Summary.
        forward = frame.locator(
            'input[type="button"][value*="Forward"]:visible'
        ).last

        forward.wait_for(state='visible', timeout=20000)

        if not forward.is_enabled():
            raise RuntimeError(
                'Payment Forward button is disabled.'
            )

        self._step('Continue from payment page to Order Summary')
        self._human_click(forward)

        self.page.wait_for_url(
            re.compile(r'.*/order-summary/.*'),
            timeout=60000
        )

        self._step('Order Summary page loaded')

        self._screenshot('full_flow_06_order_summary')

        self.page.wait_for_timeout(120000)

        return {
            'status': 'ORDER_SUMMARY_REACHED',
            'current_url': self.page.url,
            'steps': self.steps,
            'screenshot': str(DATA_DIR / 'full_flow_06_order_summary.png'),
            'message': (
                'Order Summary reached. Final order submission '
                'and payment completion were not performed.'
            )
        }

    def run_full_order(
        self,
        data: dict[str, Any],
        identity_data: dict[str, str] | None = None
    ):
        with sync_playwright() as p:
            self.playwright = p
            self.browser = p.chromium.launch(headless=False)
            self.context = self.browser.new_context(viewport={'width':1600,'height':900})
            self.page = self.context.new_page()
            self._sensitive_data_active = identity_data is not None
            try:
                self._login_and_start()
                self._fill_basic_information(data)
                self._select_customer_type(data['order'])
                self._select_provider_and_plan(data['order'])
                result = self._checkout_and_account(
                    data,
                    identity_data=identity_data
                )
                self._run_succeeded = True
                return result
            except Exception as exc:
                try: self._screenshot('full_flow_error')
                except Exception: pass
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
                        self.browser.close()
