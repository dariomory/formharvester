import os
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
from utils import filter_scraped_links, EMAIL_RGX
from dbc_api_python3.deathbycaptcha import SocketClient
from rich import pretty
from rich.console import Console
from rich.progress import track

__VERSION__ = 1.1


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
        with open(filename) as f:
            return [i.strip() for i in f.readlines() if i.strip()]

    def bot_print(self, message, is_input=False):
        msg = f"[bold red][FormHarvester {__VERSION__}][/bold red] {message}"
        self.c.print(msg)
        if is_input:
            input()

    def load_progress(self):
        filename = f'data/{self.mode}_progress.txt'
        if not os.path.exists(filename):
            open(filename, 'w').close()
        progress = self.load_txt(filename)
        return [p.split('|') for p in progress]

    def write_progress(self, url_list):
        with open(f'data/{self.mode}_progress.txt', 'w') as f:
            for url in url_list:
                f.write(url + '|\n')

    def update_progress(self, url, status):
        progress = self.load_progress()
        for arr in progress:
            if arr[0] == url:
                arr[1] = status
                break
        with open(f'data/{self.mode}_progress.txt', 'w') as f:
            for arr in progress:
                f.write(f'{arr[0]}|{arr[1]}\n')

    def get_progress(self):
        """
        Return urls without progress
        :return: list
        """
        progress = self.load_progress()
        output = []
        for arr in progress:
            if not arr[1]:
                output.append(arr)
        return output

    def log_website(self, url):
        self.visited_websites.append(url)
        with open('data/website_log.txt', 'a') as f:
            f.write(url + '\n')

    def export_emails(self, filename='scraped_emails'):
        existing_emails = self.load_txt(f'data/{filename}_emails.txt')

        with open(f'data/{filename}_emails.txt', 'a') as f:
            for (email, url) in self.scraped_emails:
                if email not in existing_emails:
                    f.write(email + '\n')

        if self.generate_email_sources:
            with open(f'data/{filename}_emails_sources.txt', 'a') as f:
                for (email, url) in self.scraped_emails:
                    if email not in existing_emails:
                        f.write(f'{email} ({url})' + '\n')

    def run(self):
        self.bot_print('Running...')
        for query in self.google_queries:
            query = quote_plus(query)
            self.get(f'https://www.google.com/search?q={query}&filter=0')
            scraped_links = []

            if self.start_page > 1:
                backup_page = 10
                while True:
                    page = self.css(self.GOOGLE_PAGE.format(str(self.start_page)))
                    if page:
                        self.click(page)
                        break
                    else:
                        self.click(self.GOOGLE_PAGE.format(str(backup_page)), css=True)
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
                else:
                    break
            # Process scraped links
            scraped_links = filter_scraped_links(self.keywords, scraped_links)
            self.write_progress(scraped_links)
            self.start_process(scraped_links)
        self.bot_print(f'Done.', is_input=True)

    def resume(self, url_list):
        self.bot_print('Resuming harvest...')
        self.start_process(url_list)
        self.bot_print(f'Done.', is_input=True)

    def start_process(self, url_list):
        for url in track(url_list, description='Processing...'):
            try:
                if url in self.visited_websites:
                    self.update_progress(url, status='VISITED')
                    continue
                self.process_url(url)
            except:
                self.update_progress(url, status='ERROR')
                e = traceback.format_exc()
                bot.log(screenshot=True, error=e)
                self.restart_driver()
            self.export_emails(filename=self.mode)

    def scrape_emails(self):
        emails = set(re.findall(EMAIL_RGX, str(self.driver.page_source)))
        emails = [
            i for i in emails if
            not any(
                x for x in ['/', 'unpkg', 'sentry.wixpress.com', 'static.', 'indexOf', '.js', '//'] if x in i
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
                        self.get(full_url, sleep=1, timeout=10)
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
        self.name_filled = False
        self.scraped_emails = set()
        self.visited_links.clear()

        contact_url = urljoin(url, '/contact/')
        contact = self.get(contact_url, sleep=1)
        self.scrape_emails()
        # Switch to first tab
        self.driver.switch_to.window(self.driver.window_handles[0])

        self.cms_check()
        inputs = self.wait_get_inputs()

        if contact and not self.css('textarea'):
            inputs = self.find_contact_page(url)

        if not self.css('textarea'):
            self.get(url, sleep=1, timeout=10)
            self.scrape_emails()
            # Switch to first tab
            self.driver.switch_to.window(self.driver.window_handles[0])
            self.cms_check()
            inputs = self.wait_get_inputs()
            if not self.css('textarea'):
                inputs = self.find_contact_page(url)

        if not self.send_form:
            self.update_progress(url, status='VISITED')
            return

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

                self.log_website(url)
                self.update_progress(url, status='SUBMITTED')
            elif btn and self.DEBUG:
                self.highlight(btn)
                self.log_website(url)
            else:
                self.update_progress(url, status='BUTTON_NOT_FOUND')

            time.sleep(3)
            return True
        else:
            self.update_progress(url, status='FORM_NOT_FOUND')
            return False

    def create_driver(self):

        chrome_options = webdriver.ChromeOptions()

        if self.DEV_SETTINGS:
            chrome_options.add_argument('--fast-start')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--window-position=1072,642')

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
        self.max_google_pages = config.getint('settings', 'max_google_pages')
        self.skip_ads = config.getboolean('settings', 'skip_ads')
        self.start_page = config.getint('settings', 'start_page')
        self.send_form = config.getboolean('settings', 'send_form')
        self.generate_email_sources = config.getboolean('settings', 'generate_email_sources')

        self.DEV_SETTINGS = config.getboolean('dev', 'enabled')
        self.DEBUG = config.getboolean('dev', 'debug_form')

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

        self.name_filled = False
        self.visited_links = []  # visited links within a site
        self.scraped_emails = set()
        self.create_driver()


if __name__ == '__main__':
    bot = Bot()
    remaining_urls = bot.get_progress()
    if remaining_urls:
        urls = [i[0] for i in remaining_urls]
        bot.resume(urls)
    else:
        bot.run()
