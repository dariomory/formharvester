import json
import os
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    MoveTargetOutOfBoundsException,
    WebDriverException,
    NoSuchFrameException,
)
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
import time
import random
import sys
import numpy as np
import scipy.interpolate as si
from glob import glob
from hashlib import md5
from PIL import Image
import html
import re
from urllib.parse import urlparse, urljoin, parse_qs
from os.path import sep
import zipfile
import pickle


class SeleniumBot:
    driver = None
    captcha_client = None

    DEV_SETTINGS = None
    COOKIES_PROFILE = None
    HEADLESS = None
    INCOGNITO = None
    DISABLE_IMAGES = None
    REMOTE_DEBUGGING = None
    HIDE_EXTENSION = None
    SINGLE_PROXY = None
    PROXY_LIST = None
    PROXY_AUTH = None
    USERAGENT = None
    FLASH = None
    DATA_DIR = None
    PROFILE = None

    EXTENSIONS = []

    WAIT = 99999

    TIMEOUT = 5
    MAX_SLEEP = 5

    MIN_RAND = 0.64
    MAX_RAND = 1.27
    MIN_RAND_LONG = 4.78
    MAX_RAND_LONG = 11.1

    NUM_MOUSE_MOVES = 10

    def get(self, page, pre_sleep=0, sleep=0, timeout=False):
        if timeout:
            self.driver.set_page_load_timeout(timeout)

        time.sleep(pre_sleep)
        try:
            self.driver.get(page)
            time.sleep(sleep)
            if timeout:
                self.driver.set_page_load_timeout(-1)
            return True
        except Exception as e:
            print(e)
            if timeout:
                self.driver.set_page_load_timeout(-1)
            return False

    def get_wait(self, url, selector, wait=9999):
        self.get(url)
        return self.wait_show_element(selector, wait=wait)

    def reload(self):
        self.driver.refresh()

    def close(self):
        if self.COOKIES_PROFILE:
            self.save_cookies()
        self.driver.quit()

    def script(self, script, *args):
        return self.driver.execute_script(script, *args)

    def css(self, selector, node=None, getall=False, attr=None,
            wait=None, wait_for=None,
            ):

        if wait:
            w = self.wait_show_element(selector, wait=wait)
            if not w:
                return None
        if wait_for:
            w = self.wait_for_element(selector, wait=wait_for)
            if not w:
                return None

        if getall:
            el = self.get_elements_from(node if node else self.driver, selector)
        else:
            el = self.get_element_from(node if node else self.driver, selector)

        if attr and el:
            el = self.extract_attributes(el, attr)

        return el

    def xpath(self, selector, node=None, getall=False, attr=None, wait=None):
        if wait:
            w = self.wait_show_element(selector, xpath=True, wait=wait)
            if not w:
                return None

        if getall:
            el = self.get_elements_from(node if node else self.driver, selector, xpath=True)
        else:
            el = self.get_element_from(node if node else self.driver, selector, xpath=True)

        if attr and el:
            el = self.extract_attributes(el, attr)

        return el

    def get_attr(self, el, attr):
        if type(attr) == list:
            output = []
            for a in attr:
                if a == 'text':
                    output.append(el.text)
                else:
                    output.append(el.get_attribute(a))
        else:
            if attr == 'text':
                output = el.text
            else:
                output = el.get_attribute(attr)
        return output

    def extract_attributes(self, el, attr):
        if type(el) == list:
            return [self.get_attr(i, attr) for i in el]
        else:
            return self.get_attr(el, attr)

    def contains_text(self, text):
        try:
            return self.driver.find_element_by_xpath(f'//*[contains(text(), "{text}")]')
        except NoSuchElementException:
            return None

    def contains_regex(self, regex):
        page_text = self.css('body').text
        if re.findall(rf'{regex}', page_text):
            return True
        else:
            return False

    def submit_form(self, element):
        try:
            element.submit()
            return True
        except TimeoutException:
            return False

    def wait_page_load(self):
        while True:
            page_state = self.script(
                'return document.readyState;')
            self.driver.implicitly_wait(1)
            if page_state == 'complete':
                break
        return

    def wait_for_text(self, text, wait=99999):
        try:
            wait = WebDriverWait(self.driver, wait)
            element = wait.until(EC.presence_of_element_located((By.XPATH, f'//*[contains(text(), "{text}")]')))
            return element
        except:
            return None

    def wait_for_regex(self, regex):
        while True:
            if self.contains_regex(regex):
                return True
            time.sleep(.5)

    def wait_for_element(self, selector, xpath=False, wait=99999):
        try:
            wait = WebDriverWait(self.driver, wait)
            if xpath:
                element = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
            else:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return element
        except:
            return None

    def wait_show_element(self, selector, xpath=False, wait=99999):
        try:
            wait = WebDriverWait(self.driver, wait)
            if xpath:
                element = wait.until(EC.visibility_of_element_located((By.XPATH, selector)))
            else:
                element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
            return element
        except:
            return None

    def wait_hide_element(self, selector, wait):
        try:
            wait = WebDriverWait(self.driver, wait)
            element = wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, selector)))
            return element
        except:
            return None

    def wait_click_element(self, selector, wait):
        try:
            wait = WebDriverWait(self.driver, wait)
            element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            return element
        except:
            return None

    def element_is_present(self, selector):
        try:
            self.driver.find_element_by_css_selector(selector)
            return True
        except NoSuchElementException:
            return False

    def verify_element_present(self, selector):
        if not self.element_is_present(selector):
            raise Exception('Element %s not found' % selector)

    def get_element_from(self, fromObject, selector, xpath=False):
        try:
            if xpath:
                return fromObject.find_element_by_xpath(selector)
            else:
                return fromObject.find_element_by_css_selector(selector)
        except NoSuchElementException:
            return None

    def get_elements_from(self, fromObject, selector, xpath=False):
        try:
            if xpath:
                return fromObject.find_elements_by_xpath(selector)
            else:
                return fromObject.find_elements_by_css_selector(selector)
        except NoSuchElementException:
            return []

    def get_element_from_value(self, fromObject, selector):
        element = self.get_element_from(fromObject, selector)
        if element:
            return element.text
        return None

    def get_element_value(self, selector):
        element = self.css(selector)
        if element:
            return element.text
        return None

    def get_element_from_attribute(self, fromObject, selector, attribute):
        element = self.get_element_from(fromObject, selector)
        if element:
            return element.get_attribute(attribute)
        return None

    def get_element_attribute(self, selector, attribute):
        element = self.css(selector)
        if element:
            return element.get_attribute(attribute)
        return None

    def get_parent_levels(self, node, levels):
        path = '..'
        if levels > 1:
            for i in range(1, levels):
                path = path + '/..'
        return node.find_element_by_xpath(path)

    def get_parent_node(self, node):
        return node.find_element_by_xpath('..')

    def get_child_nodes(self, node):
        return node.find_elements_by_xpath('./*')

    def write(self, field, text,
              css=False,
              xpath=False,
              name=False,
              wait=False,
              clear=False,
              human=False,
              submit=False,
              ):

        if wait:
            self.wait_show_element(field, wait=self.WAIT, xpath=xpath)

        if css:
            field = self.css(field)
        elif xpath:
            field = self.xpath(field)
        elif name:
            field = self.driver.find_element_by_name(field)

        if clear:
            if human:
                while field.get_attribute('value') != '':
                    field.send_keys(Keys.BACKSPACE)
                    time.sleep(random.uniform(.05, .1))
                self.random_sleep()
            else:
                field.clear()

        if human:
            for letter in text:
                field.send_keys(letter)
                time.sleep(random.uniform(.05, .2))
        else:
            field.send_keys(text)

        if submit:
            field.send_keys(Keys.ENTER)

        return field

    def press_key(self, key):
        webdriver.ActionChains(self.driver).send_keys(key).perform()

    def press_enter(self, field_object):
        field_object.send_keys(Keys.RETURN)
        return field_object

    def click(self,
              element,
              wait=False,
              css=False,
              xpath=False,
              js_click=False,
              sleep=False,
              double=False):

        if wait:
            w = self.wait_show_element(element, wait=wait, xpath=xpath)
            if not w:
                return None

        if sleep:
            time.sleep(sleep)

        if css:
            element = self.css(element)
        elif xpath:
            element = self.xpath(element)

        if double:
            rng = 2
        else:
            rng = 1

        for _ in range(rng):
            try:
                # use Selenium's built in click function
                actions = webdriver.ActionChains(self.driver)
                actions.move_to_element(element)
                actions.click(element)
                actions.perform()
                return element

            except Exception:
                print('JS click')
                # try `execute_script` as a last resort
                # print("attempting last ditch effort for click, `execute_script`")
                self.script("arguments[0].click();", element)
                return element

    def select_checkbox(self, selector, name, deselect=False):
        found_checkbox = False
        checkboxes = self.css(selector, getall=True)
        for checkbox in checkboxes:
            if checkbox.get_attribute('name') == name:
                found_checkbox = True
                if not deselect and not checkbox.is_selected():
                    checkbox.click()
                if deselect and checkbox.is_selected():
                    checkbox.click()
        if not found_checkbox:
            raise Exception('Checkbox %s not found.' % name)

    def select_option(self, selector, value):
        found_option = False
        options = self.css(selector, getall=True)
        for option in options:
            if option.get_attribute('value') == str(value):
                found_option = True
                option.click()
        if not found_option:
            raise Exception('Option %s not found' % (value))

    def select_dropdown(self, value, xpath=False):
        if xpath:
            elem = Select(self.driver.find_element_by_xpath(value))
        else:
            elem = Select(self.driver.find_element_by_css_selector(value))
        return elem

    def get_selected_option(self, selector):
        options = self.css(selector)
        for option in options:
            if option.is_selected():
                return option.get_attribute('value')

    def is_option_selected(self, selector, value):
        options = self.css(selector)
        for option in options:
            if option.is_selected() != (value == option.get_attribute('value')):
                print(option.get_attribute('value'))
                return False
        return True

    def drag_drop(self, drag, drop):
        drag_item = self.css(drag)
        target_item = self.css(drop)
        action_chains = webdriver.ActionChains(self.driver)
        action_chains.drag_and_drop(drag_item, target_item).perform()

    def move_to_element(self, element):
        self.driver.execute_script("return arguments[0].scrollIntoView();", element)
        actions = webdriver.ActionChains(self.driver)
        actions.move_to_element(element)
        actions.perform()

    def check_title(self, title):
        return self.driver.title == title

    def save_screenshot(self, path=f"{str(int(time.time()))}.png"):
        self.driver.save_screenshot(path)

    def scroll_up(self, y=100):
        scroll = self.driver.execute_script('return document.documentElement.scrollTop')
        self.driver.execute_script(f'scrollTo(0, {scroll - y})')

    def scroll_down(self, y=400):
        scroll = self.driver.execute_script('return document.documentElement.scrollTop')
        self.driver.execute_script(f'scrollTo(0, {scroll + y})')

    def log(self, screenshot=False, error=None):
        try:
            timestamp = str(int(time.time()))
            filename = os.path.join('log', timestamp)
            output = ''

            if not os.path.exists('log'):
                os.mkdir('log')

            if screenshot:
                self.save_screenshot(f'{filename}.png')

            output += str(self.driver.current_url) + '\n\n'

            if error:
                output += f'{error}\n\n'

            output += str(self.driver.page_source)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            output += str(soup.prettify()) + '\n\n'

            with open(f'{filename}.log', 'w', encoding='utf8') as f:
                f.write(output)

        except Exception as e:
            print(e)

    def highlight(self, element,
                  css=False):
        if css:
            element = self.css(element)
        self.driver.execute_script("arguments[0].style.border='6px groove green'", element)

# dario@mory.dev :)
