from __future__ import annotations
import os, re, json, random
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()
PORTAL_URL = os.getenv('PORTAL_URL', 'https://lemon-forest-0915c3c1e.6.azurestaticapps.net/allconnect')
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
        if c.get('prefix'): self.page.locator('#namePrefixList').select_option(label=c['prefix'])
        self.page.locator('#firstName').fill(c['first_name'])
        if c.get('middle_initial'): self.page.locator('#middleName').fill(c['middle_initial'])
        self.page.locator('#lastName').fill(c['last_name'])
        if c.get('suffix'): self.page.locator('#nameSuffixList').select_option(label=c['suffix'])
        # Portal field ssZipCode is the initial ZIP prompt, not a Social Security Number field.
        self.page.locator('#ssZipCode').fill(a['zip_code'][:5])
        self.page.locator('#ssZipCode').press('Tab')
        self.page.wait_for_function("() => { const e=document.querySelector('#address1'); return e && !e.disabled; }", timeout=30000)
        self.page.locator('#address1').fill(a['address_line_1'])
        if a.get('unit_type'): self.page.locator('#unitTypeList').select_option(label=a['unit_type'])
        if a.get('unit_number'): self.page.locator('#unitNumber').fill(a['unit_number'])
        self.page.locator('#city').fill(a['city'])
        state = a['state'].upper()
        self.page.locator('#stateList').select_option(label=STATE_NAMES.get(state, state))
        self.page.locator('#zipcode').fill(a['zip_code'])
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

    def _select_customer_type(self, order: dict[str, Any]):
        self._step('Select New or Transfer customer')
        value = 'New' if order['customer_type'] == 'NEW' else 'Transfer'
        radio = self.page.locator(f'input[type="radio"][value="{value}"]:visible').first
        radio.check()
        if not radio.is_checked(): raise RuntimeError(f'Could not select customer type {value}.')
        self._forward_main()
        self.page.locator('#content_header span.pageTitle').filter(has_text='Recommendations').wait_for(state='visible', timeout=60000)
        self._review_pause('Customer Type Selection')

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

        # The first recommendation card is ProviderXX (#goldTable).
        provider_card = recommendations_frame.locator('#goldTable')

        provider_card.wait_for(state='visible', timeout=30000)

        self._step('Click ProviderXX recommendation card')

        # Click the provider heading area in the first card.
        provider_card.click(
            position={'x': 150, 'y': 35},
            timeout=15000
        )


        self._step('Wait for ProviderXX confirmation or direct catalogue navigation')
        yes = self.page.locator('#providerxxYes')
        products_button = self.page.locator('#ProviderXXProductsButton')
        details_buttons = self.page.locator('input.ViewDetailsBtn:visible')

        # The simulator can either show a confirmation layer or navigate directly.
        try:
            yes.wait_for(state='visible', timeout=8000)
        except PlaywrightTimeoutError:
            pass

        if yes.count() and yes.is_visible():
            input_type = (yes.get_attribute('type') or '').lower()
            if input_type in ('radio', 'checkbox'):
                yes.check()
            else:
                yes.click()
            products_button.wait_for(state='visible', timeout=15000)
            products_button.click()
        else:
            # If no confirmation appeared, only continue if the catalogue is actually
            # visible. Do not click a guessed navigation control.
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
                    'Clicked the ProviderXX card, but neither the confirmation dialog '
                    'nor the Internet catalogue appeared. '
                    f'Visible controls: {diagnostics}'
                )

        # On some portal builds the confirmation button opens the catalogue directly.
        if not self.page.locator('input.ViewDetailsBtn:visible').count():
            internet_link = self.page.locator('a:visible').filter(
                has_text=re.compile(r'^\s*Internet\s*$', re.I)
            )
            if internet_link.count():
                internet_link.first.click()

        self.page.locator('input.ViewDetailsBtn:visible').first.wait_for(
            state='visible', timeout=30000
        )

        self._step('Open Internet plans')
        speed = int(order['internet_speed_mbps'])
        term = order['pricing_term']
        buttons = self.page.locator('input.ViewDetailsBtn:visible')
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
                speed_patterns.get(speed, rf'(?<!\d){speed}\s*(?:mbps|mb|meg)'),
                normalized
            ) is not None
            year_match = (
                re.search(r'1[- ]year(?: pricing)?', normalized) is not None
                if term == '1_YEAR'
                else re.search(r'5[- ]year(?: price guarantee)?', normalized) is not None
            )
            if speed_match and year_match:
                match_index = i
                break

        if match_index is None:
            raise RuntimeError(
                f'Internet catalogue opened, but no {speed} Mbps / {term} plan matched. '
                f'Visible product cards: {visible_cards}'
            )

        self._step(f'Open details for {speed} Mbps {term} plan')
        buttons.nth(match_index).click()
        self.page.locator('#addToOrderAndCheckout').wait_for(
            state='visible', timeout=30000
        )
        self._screenshot('full_flow_02_product_details')
        self._step('Add selected plan to order and proceed to checkout')
        self._review_pause('Provider and Internet Plan Selection')
        self.page.locator('#addToOrderAndCheckout').click()
        self.page.wait_for_url(re.compile(r'.*/checkout/.*'), timeout=60000)

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
                    radio.check()
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
                    radio.check()
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
        forward.click()
        self._review_pause('checkout service selections')
        frame.wait_for_timeout(500)
        # Broadband labels: select only the choice supplied in the API request.
        label_choice = disclosures['broadband_label_choice']
        self._choose_radio_by_label(frame, 'labels', r'Customer requested' if label_choice == 'REQUESTED' else r'Customer did not request')
        if not disclosures.get('broadband_label_acknowledged', False):
            raise RuntimeError('Customer broadband-label acknowledgement is false; stopped without checking the Read box.')
        # Acknowledgement is represented by the visible Read checkbox on this page.
        read_box = frame.get_by_role('checkbox').first
        read_box.check()
        equipment_pattern = r'Leased Gateway' if order['equipment_type']=='LEASED_GATEWAY' else r'EQUIPMENT OWN'
        self._choose_radio_by_label(frame, 'equipment', equipment_pattern)
        if order.get('now_tv', False): self._choose_radio_by_label(frame, 'nowtv', r'NOW TV')
        self._review_pause('checkout broadband label and equipment selections')
        forward = frame.locator('input[type="button"][value*="Forward"]')
        forward.click()
        
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

            phone_field.fill(data['customer']['phone'])
            email_field.fill(data['customer']['email'])

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

        # 5. Account-holder disclosure.
        if not q.get('account_disclosure_acknowledged', False):
            raise RuntimeError(
                'Account-holder disclosure acknowledgement '
                'is not confirmed.'
            )

        # Locate the visible Read checkbox for the account-holder disclosure.
        read_checkbox = frame.locator('input[type="checkbox"]:visible')

        if read_checkbox.count() == 0:
            raise RuntimeError(
                "Account-holder disclosure Read checkbox was not found."
            )

        checked = False

        for i in range(read_checkbox.count()):
            checkbox = read_checkbox.nth(i)

            label = checkbox.evaluate("""
                el => {
                    const labels = Array.from(el.labels || []);
                    return labels.map(x => x.innerText).join(' ');
                }
            """)

            if 'Read' in label:
                checkbox.check()
                checked = True
                break

        if not checked:
            raise RuntimeError(
                "Could not identify the account-holder disclosure Read checkbox."
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
        # Continue to installation.
        frame.locator(
            'input[type="button"][value*="Forward"]'
        ).click()
        
        self._step('Continue to installation and payment')

        # -------------------------------------------------
        # 1. SECURE MANUAL CREDIT CHECK
        # -------------------------------------------------
        
        # -------------------------------------------------
        # 1. SECURE MANUAL CREDIT CHECK
        # -------------------------------------------------
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

            # Verify the actual portal result.
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

            self._step(
                'Credit Check APPROVED - Processing SUCCESS'
            )

        else:
            raise RuntimeError(
                'Credit check section was not found. '
                'Stopped for manual review.'
            )

        # Do not continue if the portal has not confirmed approval.


        # -------------------------------------------------
        # 2. SELECT PROFESSIONAL INSTALLATION
        # -------------------------------------------------
        installation = data['installation']

        installation_type = installation['installation_type']

        if installation_type == 'PRO_INSTALL':

            self._step('Select Professional Installation')

            self._choose_radio_by_label(
                frame,
                'itype',
                r'PRO_INSTALL'
            )

            # -------------------------------------------------
            # 3. CHECK INSTALLATION DISCLOSURES
            # -------------------------------------------------
            # Both acknowledgements must be confirmed by the customer.
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

            # First Read: Someone over 18 must be present.
            if not read_boxes.nth(0).is_checked():
                read_boxes.nth(0).check()

            # Second Read: Installation availability disclosure.
            if not read_boxes.nth(1).is_checked():
                read_boxes.nth(1).check()

            # -------------------------------------------------
            # 4. SELECT INSTALLATION DATE
            # -------------------------------------------------
            preferred_date = installation.get('preferred_date')

            if not preferred_date:
                raise RuntimeError(
                    'Professional installation date is missing.'
                )

            date_field = frame.locator(
                'input[type="date"]:visible'
            ).first

            date_field.wait_for(
                state='visible',
                timeout=15000
            )

            # HTML date input expects YYYY-MM-DD.
            date_field.fill(preferred_date)

            # -------------------------------------------------
            # 5. SELECT PREFERRED TIME
            # -------------------------------------------------
            preferred_time = installation.get('preferred_time')

            if preferred_time not in (
                'Morning', 'Afternoon', 'Evening'
            ):
                raise RuntimeError(
                    'Invalid installation time. '
                    'Choose Morning, Afternoon or Evening.'
                )

            time_selected = False

            selects = frame.locator('select:visible')

            for i in range(selects.count()):
                select = selects.nth(i)

                option_labels = select.locator(
                    'option'
                ).all_text_contents()

                if any(
                    preferred_time.lower() in option.lower()
                    for option in option_labels
                ):
                    select.select_option(label=preferred_time)
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

        elif installation_type == 'STANDARD_SHIPPING':

            self._step('Select Standard Shipping')

            self._choose_radio_by_label(
                frame,
                'itype',
                r'STANDARD_SHIPPING'
            )

        else:
            raise RuntimeError(
                f'Unsupported installation type: {installation_type}'
            )

        # -------------------------------------------------
        # 6. CONFIRM INSTALLATION
        # -------------------------------------------------
        self._screenshot('full_flow_03_installation_configured')

        
        # Confirm the installation selection.
        confirm = frame.locator(
            'input[type="button"][value*="Confirm Installation"]'
        )

        if not confirm.count() or not confirm.is_visible():
            raise RuntimeError(
                'Confirm Installation button was not found.'
            )

        confirm.click()

        self._step('Installation selection confirmed')

        # Wait for the portal's next Forward button.
        forward = frame.locator(
            'input[type="button"][value*="Forward"]'
        )

        forward.wait_for(
            state='visible',
            timeout=30000
        )

        if not forward.is_enabled():
            raise RuntimeError(
                'Forward button appeared but is disabled.'
            )
        self._review_pause('checkout installation confirmation')
        self._step('Click Forward after installation confirmation')

        forward.click()

        self._step('Wait for Order Summary')
        self.page.wait_for_url(re.compile(r'.*/order-summary/.*'), timeout=60000)
        self._screenshot('full_flow_03_order_summary')
        self._step('Order Summary reached')

        print(
            '\nOrder Summary displayed. '
            'Keeping browser open for 120 seconds.'
        )

        self.page.wait_for_timeout(120000)
        return {
            'status': 'ORDER_SUMMARY_REACHED',
            'current_url': self.page.url,
            'steps': self.steps,
            'screenshot': str(DATA_DIR / 'full_flow_03_order_summary.png'),
            'message': 'Portal Order Summary reached. No final order submission or payment was performed.',
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
