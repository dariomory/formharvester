import os
import threading
from urllib.parse import urljoin, quote_plus
from selenium import webdriver
from SeleniumBot import SeleniumBot
import traceback
import time
import re
import random
import pandas as pd
from selenium.webdriver.common.keys import Keys
import configparser
import csv
import platform
from utils import filter_scraped_links, EMAIL_RGX, get_root_url
from dbc_api_python3.deathbycaptcha import SocketClient
from rich import pretty
from rich.console import Console

__VERSION__ = '1.3.3'


class Bot(SeleniumBot):
    # CSS
    GOOGLE_LINKS = '.r>a'
    GOOGLE_NEXT = '#pnnext'
    GOOGLE_PAGE = '[aria-label="Page {}"]'  # format

    # xPath
    AD_XPATH = './ancestor::*[contains(@class, "ads")]'  # node

    @staticmethod
    def clean_text(text):
        return text.replace('-', '').lower()

    @staticmethod
    def load_txt(filename):
        if not os.path.exists(filename):
            open(filename, 'w').close()
            return []

        with open(filename) as f:
            return [i.strip() for i in f.readlines() if i.strip()]

    def check_time(self):
        start = time.time()
        while True:
            elapsed = time.time() - start
            self.bot_print(round(elapsed, 2))
            if elapsed >= self.max_time:
                self.crawl = False
                return
            time.sleep(.1)

    def bot_print(self, message, is_input=False):
        msg = f"[bold red][FormHarvester {__VERSION__}][/bold red] {message}"
        self.c.print(msg)
        if is_input:
            input()

    def get_progress_file(self, google):
        if google:
            return f'data/{self.mode}_progress_google.txt'
        else:
            return f'data/{self.mode}_progress.txt'

    def load_progress(self, google):
        filename = self.get_progress_file(google)
        progress = self.load_txt(filename)
        return [p.split('|') for p in progress]

    def write_progress(self, term_list, google):
        filename = self.get_progress_file(google=google)
        new_list = self.filter_unique(term_list, flat=True)  # filter duplicates
        if google:
            new_list = self.filter_duplicates_from_file(new_list, google=True)

        with open(filename, 'a') as f:
            for url in new_list:
                f.write(url + '|\n')

    def update_progress(self, term, status, google):

        filename = self.get_progress_file(google)
        progress = self.load_progress(google=google)
        progress = self.filter_unique(progress)

        for arr in progress:
            if arr[0] == term:
                arr[1] = status
                break
        with open(filename, 'w') as f:
            for arr in progress:
                f.write(f'{arr[0]}|{arr[1]}\n')

    @staticmethod
    def filter_unique(term_list, flat=False):
        unique = set()
        output = []

        if flat:
            for i in term_list:
                if i in unique:
                    continue
                unique.add(i)
                output.append(i)
        else:
            for li in term_list:
                if li[0] in unique:
                    continue
                unique.add(li[0])
                output.append(li)

        return output

    def filter_duplicates_from_file(self, term_list, google=False):
        progress = self.load_progress(google=google)
        terms = [i[0] for i in progress]
        return [i for i in term_list if i not in terms]

    def get_no_progress(self, is_google=False):
        """
        Return urls with no progress
        :return: list
        """
        progress = self.load_progress(is_google)
        output = []
        for arr in progress:
            if not arr[1]:
                output.append(arr)
        return output

    def log_website(self, url):
        url = get_root_url(url)
        self.visited_websites.append(url)
        with open('data/website_log.txt', 'a') as f:
            f.write(url + '\n')

    def get_website_log(self):
        return self.load_txt('data/website_log.txt')

    def export_emails(self, filename='scraped_emails'):
        existing_emails = self.load_txt(f'data/{filename}_emails.txt')

        logged = set()
        with open(f'data/{filename}_emails.txt', 'a') as f:
            for (email, url) in self.scraped_emails:
                if email not in existing_emails and email not in logged:
                    f.write(email + '\n')
                    logged.add(email)

        if self.generate_email_sources:
            logged = set()
            with open(f'data/{filename}_emails_sources.txt', 'a') as f:
                for (email, url) in self.scraped_emails:
                    if email not in existing_emails:
                        f.write(f'{email} ({url})' + '\n')
                        logged.add(email)

    def run(self):
        self.bot_print('Running...')
        self.write_progress(self.google_queries, google=True)

        while self.google_queries:
            scraped_links = self.start_process_google(self.google_queries)
            # Process scraped links
            if scraped_links:
                self.start_process_url(scraped_links)

        self.bot_print(f'Done!', is_input=True)

    def resume(self, url_list, google_list):
        self.bot_print('Resuming harvest...')

        # Finish remaining urls first
        if url_list:
            self.start_process_url(url_list)
            url_list.clear()

        while google_list:
            scraped_links = self.start_process_google(google_list)
            if scraped_links:
                self.start_process_url(scraped_links)

        self.bot_print(f'Done!', is_input=True)

    def start_process_url(self, url_list):
        self.bot_print('Processing URLs...')

        for url in url_list:
            self.crawl = True
            try:
                if url in self.visited_websites:
                    self.update_progress(url, status='VISITED', google=False)
                    continue
                status = self.process_url(url)
                if status is None:
                    self.update_progress(url, status='VISITED', google=False)
            except:
                self.update_progress(url, status='ERROR', google=False)
                e = traceback.format_exc()
                bot.log(screenshot=True, error=e)
                self.restart_driver()
            self.export_emails(filename=self.mode)
            # Wait for thread to finish
            if self.threads:
                t = self.threads.pop()
                t.join()
            # Re-enable crawl
            self.crawl = True

    def google_popup_check(self):
        iframe = self.css('iframe[src*="consent"]', wait=3)
        if iframe:
            self.driver.switch_to.frame(iframe)
            btns = self.css('div[role=button]', getall=True)
            if btns:
                self.click(btns[1])
        self.driver.switch_to.default_content()

    def start_process_google(self, google_list):

        google_term = google_list.pop(0)
        self.bot_print(google_term)

        query = quote_plus(google_term)
        time.sleep(3)
        self.get(f'https://www.google.com/search?q={query}&filter=0')

        while True:
            exists = self.check_captcha()
            if exists:
                if self.CAPTCHA_SLEEP:
                    self.driver.quit()
                    self.bot_print(f'Captcha found! Sleeping for {self.CAPTCHA_SLEEP // 60} minutes.')
                    time.sleep(self.CAPTCHA_SLEEP)
                    self.create_driver()
                    self.get(f'https://www.google.com/search?q={query}&filter=0')
                else:
                    self.bot_print('Please solve the captcha to continue.', is_input=True)
                    break
            else:
                break

        self.google_popup_check()

        scraped_links = []

        # Start at X page
        if self.start_page > 1:
            backup_page = 10
            while True:
                page = self.css(self.GOOGLE_PAGE.format(str(self.start_page)))
                if page:
                    self.click(page)
                    self.random_sleep(self.MIN_DELAY, self.MAX_DELAY)
                    break
                else:
                    self.click(self.GOOGLE_PAGE.format(str(backup_page)), css=True)
                    self.random_sleep(self.MIN_DELAY, self.MAX_DELAY)
                    backup_page += 4

        for _ in range(self.max_google_pages):
            # Scrape links and go to next page
            if self.skip_ads:
                no_ads = []
                els = self.css(self.GOOGLE_LINKS, getall=True)
                for el in els:
                    if self.xpath(self.AD_XPATH, node=el):
                        continue
                    else:
                        no_ads.append(el.get_attribute('href'))
                scraped_links.extend(no_ads)
            else:
                scraped_links.extend(self.css(self.GOOGLE_LINKS, attr='href', getall=True))
            next_btn = self.css(self.GOOGLE_NEXT, wait=1)
            if next_btn:
                self.click(next_btn)
                self.random_sleep(self.MIN_DELAY, self.MAX_DELAY)
            else:
                break

        if not scraped_links:
            return None

        scraped_links = [get_root_url(i) for i in scraped_links]  # map by root url
        scraped_links = list(set(scraped_links))  # duplicate filter
        scraped_links = filter_scraped_links(self.keywords, scraped_links)  # keyword filter

        website_log = self.get_website_log()
        scraped_links = [i for i in scraped_links if i not in website_log]  # filter by global log

        self.write_progress(scraped_links, google=False)
        self.update_progress(google_term, 'DONE', google=True)

        return scraped_links

    def scrape_emails(self):
        emails = set(re.findall(EMAIL_RGX, str(self.driver.page_source).lower()))
        emails = [
            i for i in emails if
            not any(
                x for x in
                ['.svg', '.png', '.jpg', '/', 'unpkg', 'sentry.wixpress.com', 'static.', 'indexOf', '.js'] if
                x in i
            )
        ]
        if emails:
            self.scraped_emails.update([(e, self.driver.current_url) for e in emails])

    def wait_get_inputs(self):
        self.wait_show_element('input', wait=3)
        return self.css('input', getall=True)

    def find_radio_divs(self):
        radios = self.css('input[type=radio]', getall=True)
        radio_divs = set()
        for radio in radios:
            x = self.xpath('./ancestor::div[1]', node=radio)
            radio_divs.add(x)
        return list(radio_divs)

    def check_calculation_captcha(self):
        match = re.findall(r'(\d+)\s([+\-*])\s(\d+)(\s=)?', self.driver.page_source)
        if match:
            match = match[0]
            no1 = int(match[0])
            op = match[1]
            no2 = int(match[2])
            if op == '+':
                return str(no1 + no2)
            elif op == '-':
                return str(no1 - no2)
            elif op == '*':
                return str(no1 * no2)

    def check_and_fill(self, element, field_type=None):
        if field_type == 'number':
            random_n = str(random.randint(1, 5))
            element.send_keys(random_n)
            return True

        tag = element.get_attribute('outerHTML')

        ancestor = self.xpath(
            './preceding::label[1]',
            node=element,
            attr='outerHTML',
        )
        if not ancestor:
            ancestor = ''

        fields = [
            self.clean_text(tag),
            self.clean_text(ancestor),
        ]

        element.clear()

        for field in fields:
            if 'email' in field:
                element.send_keys(
                    self.details['email']
                )
                return True
            elif bool(re.findall(r'(captcha)', field)):
                calc_res = self.check_calculation_captcha()
                if calc_res:
                    element.send_keys(calc_res)
                    return True
                captcha_text = self.check_solve_captchas(image=True)
                if captcha_text:
                    element.send_keys(captcha_text)
                    return True
            elif 'phone' in field:
                element.send_keys(
                    self.details['phone']
                )
                return True
            elif 'city' in field:
                element.send_keys(
                    self.details['city']
                )
                return True
            elif 'state' in field:
                element.send_keys(
                    self.details['state']
                )
                return True
            elif bool(re.findall(r'(location|address)', field)):
                element.send_keys(
                    self.details['location']
                )
            elif bool(re.findall(r'(location|address)', field)):
                element.send_keys(
                    self.details['location']
                )
            elif bool(re.findall(r'(subject|topic)', field)):
                element.send_keys(
                    self.details['subject']
                )
                return True
            elif bool(re.findall(r'(firstname|givenname|fname|first)', field)):
                element.send_keys(
                    self.details['first_name']
                )
                self.name_filled = True
                return True
            elif bool(re.findall(r'(lastname|lname|surname|last)', field)):
                element.send_keys(
                    self.details['last_name']
                )
                self.name_filled = True
                return True
        if any(['name' in i for i in fields]) and not self.name_filled:
            element.send_keys(
                f"{self.details['first_name']} {self.details['last_name']}"
            )
            self.name_filled = True
            return True
        else:
            element.send_keys(
                f"N/A"
            )
            return True

    def find_contact_page(self, url):
        contact_links = []
        contact_links.extend(
            self.xpath(
                '''//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'contact')]'''
                , getall=True
            )
        )
        contact_links.extend(
            self.css('a[href*="contact"]', getall=True)
        )
        print(contact_links)
        if not contact_links:
            return []

        contact_hrefs = [i.get_attribute('href') for i in set(contact_links)]

        try:
            self.click(contact_links[0])
        except:
            pass

        inputs = self.wait_get_inputs()
        if not self.css('textarea'):
            if contact_hrefs:
                for href in contact_hrefs:
                    full_url = urljoin(url, href)

                    if full_url in self.visited_links:
                        continue
                    else:
                        x = self.get(full_url, sleep=1, timeout=10)
                        if not x:
                            return

                        self.scrape_emails()
                        # Switch to first tab
                        self.driver.switch_to.window(self.driver.window_handles[0])
                        self.cms_check()
                        self.visited_links.append(full_url)
                        inputs = self.wait_get_inputs()
                        if len(inputs) > 2:
                            break
        return inputs

    def find_submit_button(self):
        possible_css = [
            'input[type=submit]',
            'input[name=submit]',
            'input[value=submit]',
            'button[class=submit]',
            'button[name=submit]',
        ]
        possible_names = [
            'submit',
            'send',
            'enviar',
            'inviare',
            'book now',
        ]

        for css in possible_css:
            found = self.css(css)
            if found:
                return found

        for name in possible_names:
            found = self.xpath(
                f'''
                //button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'send')] | //input[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{name}')]
                '''
            )
            if found:
                return found

        return None

    def submit_button(self, btn):
        try:
            self.click(btn)
        except:
            try:
                btn.click()
            except:
                try:
                    form = self.css('form')
                    if form:
                        self.script('arguments[0].submit();', form)
                except:
                    return False

    def cms_check(self):
        existing = []
        existing.extend(
            self.xpath('//script[contains(text(), "squarespace")]', getall=True)
        )
        if not existing:
            # Popup check
            self.press_key(Keys.ESCAPE)
            time.sleep(1)

    def process_url(self, url):
        time.sleep(1)
        self.bot_print(url)
        self.log_website(url)  # global log for url

        self.name_filled = False
        self.scraped_emails = set()
        self.visited_links.clear()

        contact_url = urljoin(url, '/contact/')
        contact = self.get(contact_url, sleep=1, check=True)
        if not contact:
            return

        # Start time thread
        t = threading.Thread(target=self.check_time)
        self.threads.append(t)
        t.start()

        self.scrape_emails()
        # Switch to first tab
        self.driver.switch_to.window(self.driver.window_handles[0])

        self.cms_check()
        inputs = self.wait_get_inputs()

        if contact and not self.css('textarea'):
            inputs = self.find_contact_page(url)

        if not self.crawl:
            return

        if not self.css('textarea'):
            x = self.get(url, sleep=1, timeout=10)
            if not x:
                return

            self.scrape_emails()
            # Switch to first tab
            self.driver.switch_to.window(self.driver.window_handles[0])
            self.cms_check()
            inputs = self.wait_get_inputs()
            if not self.css('textarea'):
                inputs = self.find_contact_page(url)

        if not self.crawl:
            return

        if not self.send_form:
            self.update_progress(url, status='VISITED', google=False)
            return True

        if inputs:
            # Fill text/email inputs
            for i in inputs:
                if i.get_attribute('type') in ['text', 'email', 'tel']:
                    try:
                        self.check_and_fill(i)
                    except:
                        continue
                if i.get_attribute('type') in ['number']:
                    try:
                        self.check_and_fill(i, field_type='number')
                    except:
                        continue

            # Check any radios
            radio_divs = self.find_radio_divs()
            for div in radio_divs:
                radios = self.css('input[type=radio]',
                                  node=div,
                                  getall=True,
                                  )
                for radio in radios[::-1]:
                    try:
                        self.click(radio)
                        time.sleep(.5)
                        break
                    except:
                        continue

            # Select any options
            selects = self.css('form select', getall=True)
            for select in selects:
                options = self.css('option', node=select, getall=True)
                for option in options[::-1]:
                    try:
                        option.click()
                        break
                    except:
                        continue

            # Fill message textarea
            textarea = self.css('textarea')
            if textarea:
                self.click(textarea)
                self.write(textarea, self.details['message'])

            # Sleep
            time.sleep(3)

            captcha_solved = self.check_solve_captchas(recaptcha=True)

            # Submit
            btn = self.find_submit_button()
            if btn and not self.DEBUG:
                self.submit_button(btn)

                if not captcha_solved:
                    captcha_solved = self.check_solve_captchas(recaptcha=True)
                    if captcha_solved:
                        self.submit_button(btn)
                self.update_progress(url, status='SUBMITTED', google=False)
            elif btn and self.DEBUG:
                self.highlight(btn)
            else:
                self.update_progress(url, status='BUTTON_NOT_FOUND', google=False)
            return True
        else:
            self.update_progress(url, status='FORM_NOT_FOUND', google=False)
            return False

    def create_driver(self):

        chrome_options = webdriver.ChromeOptions()

        if self.DEV_SETTINGS:
            chrome_options.add_argument('--fast-start')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--window-position=1072,642')

        if self.HEADLESS:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument("--silent")
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-infobars')
        # chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument("--disable-plugins-discovery")
        # chrome_options.add_argument('--profile-directory=default')
        chrome_options.add_experimental_option("excludeSwitches",
                                               ["enable-automation",
                                                # "ignore-certificate-errors",
                                                "safebrowing-disable-auto-update",
                                                "disable-client-side-phishing-detection",
                                                "safebrowsing-disable-download-protection",
                                                "enable-logging"  # Disable logging
                                                ])

        # Multi-platform support
        if platform.system() == 'Windows':
            exe_path = 'drivers/chromedriver.exe'
        elif platform.system() == 'Darwin':
            exe_path = 'drivers/mac_chromedriver'
        elif platform.system() == 'Linux':
            exe_path = 'drivers/linux_chromedriver'
        else:
            exe_path = None

        self.driver = webdriver.Chrome(executable_path=exe_path,
                                       options=chrome_options)

        self.driver.maximize_window()

    @staticmethod
    def read_csv(filename):
        with open(filename, encoding='utf-8-sig') as f:
            data = csv.DictReader(f)
            return list(data)

    @staticmethod
    def export_csv(obj, filename='output.csv'):
        df = pd.DataFrame(obj)
        df.to_csv(filename, index=False)

    def spawn_driver(self):
        if not self.driver:
            self.create_driver()

    def restart_driver(self):
        if self.driver:
            self.close()
            time.sleep(3)
        self.create_driver()

    def __init__(self):
        pretty.install()
        self.c = Console()

        config = configparser.ConfigParser()
        config.read('config.txt')
        self.mode = config.get('settings', 'mode')
        self.skip_ads = config.getboolean('settings', 'skip_ads')
        self.send_form = config.getboolean('settings', 'send_form')
        self.generate_email_sources = config.getboolean('settings', 'generate_email_sources')
        self.max_time = config.getint('settings', 'max_time')

        self.HEADLESS = config.getboolean('settings', 'hide_browser')
        self.DEV_SETTINGS = config.getboolean('dev', 'enabled')
        self.DEBUG = config.getboolean('dev', 'debug_form')

        self.start_page = config.getint('google', 'start_page')
        self.max_google_pages = config.getint('google', 'max_google_pages')
        self.MIN_DELAY = config.getint('google', 'min_delay')
        self.MAX_DELAY = config.getint('google', 'max_delay')
        self.CAPTCHA_SLEEP = config.getint('google', 'captcha_sleep') * 60

        dbc_user = config.get('captcha', 'dbc_user')
        dbc_pass = config.get('captcha', 'dbc_password')
        if dbc_user and dbc_pass:
            self.captcha_client = SocketClient(dbc_user, dbc_pass)
        else:
            self.captcha_client = None

        self.visited_websites = self.load_txt('data/website_log.txt')  # visited urls globally (scraper)

        obj_list = self.read_csv(f'input/{self.mode}.csv')
        self.details = {
            'first_name': obj_list[0].get('First Name'),
            'last_name': obj_list[0].get('Last Name'),
            'phone': obj_list[0].get('Phone'),
            'email': obj_list[0].get('Email'),
            'location': obj_list[0].get('Location'),
            'city': obj_list[0].get('City'),
            'state': obj_list[0].get('State'),
            'subject': obj_list[0].get('Subject'),
            'message': obj_list[0].get('Message'),
        }
        self.google_queries = [i.get('Google Queries') for i in obj_list if i.get('Google Queries')]
        self.keywords = [i.get('Keywords') for i in obj_list if i.get('Keywords')]
        self.write_progress(self.google_queries, google=True)

        self.name_filled = False
        self.visited_links = []  # visited links within a site
        self.scraped_emails = set()

        self.crawl = True  # stop current page crawl
        self.threads = []

        self.create_driver()


if __name__ == '__main__':
    while True:
        bot = Bot()
        try:
            remaining_google = bot.get_no_progress(is_google=True)
            remaining_urls = bot.get_no_progress()
            if remaining_urls or remaining_google:
                urls = [i[0] for i in remaining_urls]
                googles = [i[0] for i in remaining_google]
                bot.resume(urls, googles)
            else:
                bot.bot_print('Done.')
        except Exception as e:
            bot.close()
            print(e)
