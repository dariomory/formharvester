from selenium import webdriver
from SeleniumBot import SeleniumBot
import traceback
import time
import re
import random
import pandas as pd
from selenium.webdriver.common.keys import Keys
import threading
import configparser
import csv
import platform


class Bot(SeleniumBot):
    # CSS

    # xPath

    DEV_SETTINGS = True

    # DATA_DIR = r'User Data'

    def run(self):
        self.get('https://www.google.com')
        print()

    def create_driver(self):

        chrome_options = webdriver.ChromeOptions()

        if self.HEADLESS:
            chrome_options.add_argument("--headless")

        if self.INCOGNITO:
            chrome_options.add_argument('--incognito')

        if self.DISABLE_IMAGES:
            chrome_options.add_argument('blink-settings=imagesEnabled=false')
            chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})

        if self.REMOTE_DEBUGGING:
            os.system('start chromedriver.exe --remote-debugging-port=9515')
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9515")

        if self.HIDE_EXTENSION:
            chrome_options.add_extension(self.create_hide_extension())

        if self.SINGLE_PROXY:
            chrome_options.add_argument(f'--proxy-server={self.SINGLE_PROXY}')

        if self.PROXY_LIST:
            chrome_options.add_argument(f'--proxy-server={random.choice(self.PROXY_LIST)}')

        if self.PROXY_AUTH:
            chrome_options.add_extension(self.create_proxy_extension(self.PROXY_AUTH))

        if self.USERAGENT:
            chrome_options.add_argument(f'--user-agent={self.USERAGENT}')

        if self.DEV_SETTINGS:
            chrome_options.add_argument('--fast-start')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--window-position=1072,642')

        if self.FLASH:
            prefs = {
                "profile.default_content_setting_values.plugins": 1,
                "profile.content_settings.plugin_whitelist.adobe-flash-player": 1,
                "profile.content_settings.exceptions.plugins.*,*.per_resource.adobe-flash-player": 1,
                "PluginsAllowedForUrls": self.FLASH,
            }
            chrome_options.add_experimental_option("prefs", prefs)

        if self.DATA_DIR:
            chrome_options.add_argument(f'--user-data-dir={self.DATA_DIR}')
            chrome_options.add_argument(f'--profile-directory={self.PROFILE if self.PROFILE else "Default"}')

        if self.EXTENSIONS:
            for ext in self.EXTENSIONS:
                chrome_options.add_extension(f'{ext}.zip')

        # chrome_options.add_argument("--silent")
        # chrome_options.add_argument('--no-sandbox')
        # chrome_options.add_argument('--disable-gpu')
        # chrome_options.add_argument("--log-level=3")
        # chrome_options.add_argument('--start-maximized')
        # chrome_options.add_argument('--disable-infobars')
        # # chrome_options.add_argument("--disable-extensions")
        # chrome_options.add_experimental_option('useAutomationExtension', False)
        # chrome_options.add_argument('--disable-notifications')
        # chrome_options.add_argument("--disable-plugins-discovery")
        # # chrome_options.add_argument('--profile-directory=default')
        # chrome_options.add_experimental_option("excludeSwitches",
        #                                        ["enable-automation",
        #                                         # "ignore-certificate-errors",
        #                                         "safebrowing-disable-auto-update",
        #                                         "disable-client-side-phishing-detection",
        #                                         "safebrowsing-disable-download-protection",
        #                                         "enable-logging"  # Disable logging
        #                                         ])

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
        with open(filename) as f:
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

    def __init__(self,
                 api_key=None,
                 user=None,
                 pw=None,
                 single_proxy=None,
                 proxy_list=None,
                 ):
        self.SINGLE_PROXY = single_proxy
        self.PROXY_LIST = proxy_list
        # self.captcha_client = SocketClient(user, pw)
        # self.captcha_http_client = HttpClient(user, pw)
        # self.client = AnticaptchaClient(api_key)
        self.create_driver()


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.txt')
    username = config.get('credentials', 'username')
    password = config.get('credentials', 'password')

    bot = Bot(single_proxy='localhost:8888')
    bot.run()
