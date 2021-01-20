import json
import os
import threading
from collections import defaultdict
from datetime import datetime, timedelta
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
import chromedriver_autoinstaller

__VERSION__ = '2.2.2'
__FIGLET__ = r'''
           @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
           @@@@@@@@@@@@@@@@@800GGGGGGGG00088@@@@@@@@@@@@@@@@@
           @@@@@@@@@@@@@@0GG00888@@@@@@8880GGG8@@@@@@@@@@@@@@
           @@@@@@@@@@@@0C08@@@@@@@@@@@@@@@@@@0CC@@@@@@@@@@@@@
           @@@@@@@@@@@0C8@@@@@@@@@@@@@@@@@@@@@@0L8@@@@@@@@@@@
           @@@@@@@@@@8L8@@@@@@@@@@@@@@@@@@@@@@@@0L8@@@@@@@@@@
           @@@@@@@@@@GG@@@@@@@@@@@@@@@@@@@@@@@@@@GC@@@@@@@@@@
           @@@@@@@@@0fLGGGGGGGGGGGGGGGGGGGGGGGGGGCt0@@@@@@@@@
           @@@@@@@@@t,,:,,,,,,,,,::::::,,,,,,,,,,:.t@@@@@@@@@
           @@@@@@@8CCtCi:,,,,,,:iG000001:,,,,,,,;GtCC8@@@@@@@
           @@@@@@@i,0CG:     .:1C88@@88C1:.     ,0f8i1@@@@@@@
           @@@@@@@i,0LCG;::itfL0@@@@@@@@0Cfti::;C8f8;i@@@@@@@
           @@@@@@@0fGfLG800GC0@@@@@@@@@@@@0CG008GGtGf0@@@@@@@
           @@@@@@@@0L1G0GGG0@@@@80CGGfL0@@@@8GGG08tLC@@@@@@@@
           @@@@@@@CL00f8@@@@@@0fL:.GC :GtC@@@@@@8CGGLL8@@@@@@
           @@@@@@LCCC0GLC08@8Li:LttCCi1G;,L8@@8GCGGLLCL@@@@@@
           @@@@@8f@0fLG0LffCtL08@@@@@@@8GCLtCLfC0GGGG@f8@@@@@
           @@@@@8f8@GCCG0888GG@@@80GG00@@@CC8880GCCG@@f8@@@@@
           @@@@@@GL8CG8@@@@@@0C8C0C;:f0C8CG@@@@@@@0CGGC@@@@@@
           @@@@@@@0fC@@@@800G0CfGG;  ,fGLf00G008@@@@fG@@@@@@@
           @@@@@@@@Gf@@8G8L;:iG8G:    .180C;,;CC8@@8t8@@@@@@@
           @@@@@@@@@LL80L8L;:188f      ,00G;:;GL8@0fG@@@@@@@@
           @@@@@@@@@@GLCLLCLLLLLfti,,:ttGGGGGGCGGCC0@@@@@@@@@
           @@@@@@@@@@@@0GCCCCCG0@@@888@@80GGCCGG08@@@@@@@@@@@
           @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  _____                    _   _                           _
 |  ___|__  _ __ _ __ ___ | | | | __ _ _ ____   _____  ___| |_ ___ _ __
 | |_ / _ \| '__| '_ ` _ \| |_| |/ _` | '__\ \ / / _ \/ __| __/ _ \ '__|
 |  _| (_) | |  | | | | | |  _  | (_| | |   \ V /  __/\__ \ ||  __/ |
 |_|  \___/|_|  |_| |_| |_|_| |_|\__,_|_|    \_/ \___||___/\__\___|_|
 
                          ░▀▀▄░░░░▀▀▄░░░░▀▀▄
                          ░▄▀░░░░░▄▀░░░░░▄▀░
                          ░▀▀▀░▀░░▀▀▀░▀░░▀▀▀
'''


class Bot(SeleniumBot):
    # CSS
    GOOGLE_LINKS = '//*[@id="search"]//a[@data-ved and contains(@href, "http")]'  # xpath
    GOOGLE_LINKS_ADS = '//*[@id="search"]//a[@data-ved and contains(@href, "http")] | //a[@data-pcu]'  # xpath
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
            self.bot_print(f'[Page Timer] {round(elapsed, 2)}')
            if elapsed >= self.max_time:
                self.crawl = False
                return
            time.sleep(1)

    def bot_print(self, message, is_input=False, figlet=False):
        if figlet:
            self.c.print(__FIGLET__, style='#00eeff')
        else:
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

    def log_remaining_pages(self):
        with open('remaining_google_pages.json', 'w') as f:
            json.dump(self.remaining_pages_log, f)

    def get_remaining_pages(self):
        if os.path.exists('remaining_google_pages.json'):
            with open('remaining_google_pages.json') as f:
                self.remaining_pages_log = json.load(f)

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

        self.driver.quit()
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

    def google_timer_thread(self):
        end_time = datetime.now() + timedelta(minutes=self.GOOGLE_TIMER)
        while datetime.now() < end_time:
            self.bot_print(f'[Google Timer] {datetime.now()} -> {end_time}')
            time.sleep(1)

    def google_popup_check(self):
        iframe = self.css('iframe[src*="consent"]', wait=3)
        if iframe:
            self.driver.switch_to.frame(iframe)
            btns = self.css('div[role=button]', getall=True)
            if btns:
                self.click(btns[1])
        self.driver.switch_to.default_content()

    def check_google_captcha(self):
        self.bot_print('Checking Google captcha...')
        while True:
            search_exists = self.css('input[type="text"]')
            if search_exists:
                return
            else:
                if self.CAPTCHA_SLEEP:
                    self.bot_print(f'Captcha found! Sleeping for {self.CAPTCHA_SLEEP} minutes.')
                    self.driver.quit()
                    time_in_seconds = int(self.CAPTCHA_SLEEP * 60)
                    time.sleep(time_in_seconds)
                    self.create_driver()
                    self.wait_google_timer()
                    self.get(f'https://www.google.com/search?q={self.google_query}&filter=0')
                    if self.current_page:
                        self.start_at_x_page(self.current_page)
                else:
                    self.bot_print('Please solve the captcha to continue.', is_input=True)
                    return

    def wait_google_timer(self):
        if self.google_timer:
            self.bot_print('Waiting for last Google search...')
            self.get('https://onlineclock.net/')
            self.google_timer.join()
            self.google_timer = None

    def start_at_x_page(self, page_n):
        if page_n == 1:
            return

        last_page = 10
        while True:
            page = self.css(self.GOOGLE_PAGE.format(str(page_n)))
            if page:
                self.click(page)
                self.random_sleep(self.MIN_DELAY, self.MAX_DELAY)
                break
            else:
                self.click(self.GOOGLE_PAGE.format(str(last_page)), css=True)
                self.random_sleep(self.MIN_DELAY, self.MAX_DELAY)
                last_page += 4

    def scrape_google(self, start_page, page_count):

        scraped_links = []
        self.remaining_pages_log[self.google_term] = list(range(start_page, start_page + page_count))
        self.log_remaining_pages()
        self.start_at_x_page(start_page)
        remaining_pages = list(self.remaining_pages_log[self.google_term])
        for page in remaining_pages:
            self.current_page = page
            # Scrape links and go to next page
            if self.skip_ads:
                scraped_links.extend(
                    self.xpath(self.GOOGLE_LINKS, getall=True, attr='href')
                )
            else:
                scraped_links.extend(
                    self.xpath(self.GOOGLE_LINKS_ADS, getall=True, attr='href')
                )

            self.remaining_pages_log[self.google_term].remove(page)
            self.log_remaining_pages()
            scraped_links = self.filter_links(scraped_links)
            self.write_progress(scraped_links, google=False)

            next_btn = self.css(self.GOOGLE_NEXT, wait=1)
            if next_btn:
                self.click(next_btn)
                self.random_sleep(self.MIN_DELAY, self.MAX_DELAY)
                self.check_google_captcha()
            else:
                break

        self.google_timer = threading.Thread(
            target=self.google_timer_thread,
        )
        self.google_timer.start()
        return scraped_links

    def start_process_google(self, google_list):
        self.wait_google_timer()

        self.google_term = google_list.pop(0)
        self.bot_print(self.google_term)

        self.google_query = quote_plus(self.google_term)
        time.sleep(3)
        self.get(f'https://www.google.com/search?q={self.google_query}&filter=0')

        self.check_google_captcha()
        self.google_popup_check()

        remaining_pages = self.remaining_pages_log.get(self.google_term)
        if remaining_pages:
            scraped_links = self.scrape_google(remaining_pages[0], len(remaining_pages))
        else:
            scraped_links = self.scrape_google(self.start_page, self.max_google_pages)

        if not scraped_links:
            return None

        self.update_progress(self.google_term, 'DONE', google=True)
        return scraped_links

    def filter_links(self, scraped_links):
        scraped_links = [get_root_url(i) for i in scraped_links]  # map by root url
        scraped_links = list(set(scraped_links))  # duplicate filter
        scraped_links = filter_scraped_links(self.keywords, scraped_links)  # keyword filter
        website_log = self.get_website_log()
        scraped_links = [i for i in scraped_links if i not in website_log]  # filter by global log
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

        self.driver = webdriver.Chrome(options=chrome_options)

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
        self.bot_print(__FIGLET__, figlet=True)

        self.bot_print('Checking/updating chromedriver...')
        chromedriver_autoinstaller.install(cwd=True)

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
        self.CAPTCHA_SLEEP = config.getint('google', 'captcha_sleep')
        self.GOOGLE_TIMER = config.getint('google', 'search_timer')

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
        self.google_term = None
        self.google_query = None
        self.google_timer = None
        self.current_page = None
        self.remaining_pages_log = defaultdict(list)
        self.get_remaining_pages()

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
                bot.bot_print('Done!', is_input=True)
        except Exception as e:
            bot.close()
            print(e)
