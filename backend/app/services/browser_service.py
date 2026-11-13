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
        if self.page:
            self.page.screenshot(path=str(DATA_DIR / f'{name}.png'), full_page=True)

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

        if c.get('prefix'):
            self._human_select(
                self.page.locator('#namePrefixList'),
                label=c['prefix']
            )

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


    def _checkout_and_account(self, data: dict[str, Any]):
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
        autopay_choice = (
            'Yes' if q['autopay_paperless_discount'] else 'No'
        )
        self._choose_radio_by_label(
            frame, 'autopay', rf'^{autopay_choice}$'
        )

        # 5. EZ-Enroll and Automatic Payments disclosures.
        if q.get('ez_enroll', False):
            if not q.get('ez_enroll_disclosure_acknowledged', False):
                raise RuntimeError(
                    'EZ-Enroll disclosure acknowledgement is not confirmed.'
                )

            if not q.get('autopay_paperless_disclosure_acknowledged', False):
                raise RuntimeError(
                    'Automatic Payments and Paperless Billing disclosure '
                    'acknowledgement is not confirmed.'
                )

            # Locate the visible Read checkboxes in displayed order.
            read_checkboxes = frame.locator(
                'input[type="checkbox"]:visible'
            )

            checkbox_count = read_checkboxes.count()

            print(f'[DEBUG] Visible disclosure checkboxes: {checkbox_count}')

            if checkbox_count < 2:
                raise RuntimeError(
                    'Expected two visible disclosure Read checkboxes, '
                    f'but found {checkbox_count}.'
                )

            # First checkbox: EZ-Enroll disclosure.
            ez_read = read_checkboxes.nth(0)
            self._human_check(ez_read)
            self._step('EZ-Enroll disclosure Read checkbox selected')

            # Second checkbox: Automatic Payments disclosure.
            autopay_read = read_checkboxes.nth(1)
            self._human_check(autopay_read)
            self._step('Automatic Payments disclosure Read checkbox selected')

            if not ez_read.is_checked():
                raise RuntimeError('EZ-Enroll Read checkbox was not checked.')

            if not autopay_read.is_checked():
                raise RuntimeError(
                    'Automatic Payments Read checkbox was not checked.'
                )

            self._step('Both EZ-Enroll disclosures verified')
        else:
            # Existing non-EZ-Enroll account disclosure flow.
            if not q.get('account_disclosure_acknowledged', False):
                raise RuntimeError(
                    'Account-holder disclosure acknowledgement is not confirmed.'
                )

            read_checkbox = frame.locator(
                'input[type="checkbox"]:visible'
            )

            if read_checkbox.count() == 0:
                raise RuntimeError(
                    'Account-holder disclosure Read checkbox was not found.'
                )

            self._human_check(read_checkbox.first)

            if not read_checkbox.first.is_checked():
                raise RuntimeError(
                    'Account-holder disclosure Read checkbox was not checked.'
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
            # EZ-Enroll explicitly skips the credit check.
            self._step('EZ-Enroll selected - credit check not required')
            print(
                '\n[EZ-ENROLL]'
                '\nCredit check is skipped.'
                '\nCustomer credit-card information will be collected '
                'in the payment section.'
            )
        else:
            # Standard enrollment requires manual credit check.
            self._step('Manual Credit Check Required')

            ssn = frame.get_by_label('Social Security Number')
            dob = frame.get_by_label('Date of Birth')

            if ssn.count() and dob.count():
                print("\n======================================")
                print("MANUAL CREDIT CHECK REQUIRED")
                print("Enter customer SSN and DOB directly")
                print("into the secure portal.")
                print("Click Run Credit Check.")
                print("Wait for APPROVED and SUCCESS.")
                print("======================================\n")

                input(
                    "After completing the credit check in the portal, "
                    "press ENTER to verify its result..."
                )

                frame.wait_for_function(
                    """() => {
                        const text = document.body.innerText;

                        return (
                            /Credit Check Status:\\s*APPROVED/i.test(text) &&
                            /Processing Status:\\s*SUCCESS/i.test(text) &&
                            /LineItem Status:\\s*SUCCESS/i.test(text)
                        );
                    }""",
                    timeout=120000
                )

                self._step('Credit Check APPROVED - Processing SUCCESS')
            else:
                raise RuntimeError(
                    'Credit check section was not found for standard enrollment. '
                    'Stopped for manual review.'
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
        self._step('Wait for payment section after installation confirmation')

        frame.get_by_text(
            'PAYMENT INFORMATION',
             exact=True
        ).wait_for(state='visible', timeout=30000)

        self._step('Payment Information section opened')
        self._screenshot('full_flow_04_payment_page')

        
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
        print(
            '\n======================================'
            '\nSECURE CARD ENTRY REQUIRED'
            '\nEnter card type and card details directly'
            '\nin the secure portal fields.'
            '\nDo not send card details through the API.'
            '\nDo not submit payment or place the order.'
            '\n======================================\n'
        )

        input(
            'After selecting the card type and entering the authorized '
            'test card details directly in the secure portal, '
            'press ENTER to continue...'
        )

        self._step('Secure card entry completed by operator')

        # Require operator confirmation before continuing.
        # The portal disclosure states that card entry may place a hold.
        input(
            '\nConfirm that the customer has authorized the card hold '
            'and the applicable payment terms. '
            'Press ENTER only after confirmation...'
        )

        self._step('Operator confirmed payment authorization')

        # Continue to Order Summary.
        forward = frame.locator(
            'input[type="button"][value*="Forward"]:visible'
        ).last

        forward.wait_for(state='visible', timeout=20000)

        if not forward.is_enabled():
            raise RuntimeError(
                'Payment Forward button is disabled.'
            )

        self._review_pause('Secure payment details and billing address')

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

    def run_full_order(self, data: dict[str, Any]):
        with sync_playwright() as p:
            self.playwright = p
            self.browser = p.chromium.launch(headless=False)
            self.context = self.browser.new_context(viewport={'width':1600,'height':900})
            self.page = self.context.new_page()
            try:
                self._login_and_start()
                self._fill_basic_information(data)
                self._select_customer_type(data['order'])
                self._select_provider_and_plan(data['order'])
                result = self._checkout_and_account(data)
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
                return {'status':'MANUAL_REVIEW_REQUIRED','error':str(exc),'current_url':self.page.url if self.page else None,'steps':self.steps,'screenshot':str(DATA_DIR / 'full_flow_error.png')}
            finally:
                # On failure keep the visible browser open briefly so the portal state
                # can be inspected. Successful runs close normally.
                if self.context and self.steps and getattr(self, '_run_succeeded', False):
                    self.context.close()
                    if self.browser:
                        self.browser.close()
                        self.browser.close()
