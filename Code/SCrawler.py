import csv
import os
import sys
from ast import literal_eval

import selenium
import urllib3
import certifi
import time
import threading
import random
import pandas as pd
import numpy as np
from contextlib import closing
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from threading import Lock
from bs4 import BeautifulSoup
import http

HEADLESS = True
HEAD_WAIT = 15


data_lock = Lock()
df = pd.read_csv('assets/DataFrame.csv', converters={"Host": literal_eval,
                                                     "cookie_first": literal_eval,
                                                     "cookie_second": literal_eval
                                                     })
# DF RESET
# df['cookie_second'] = [{} for x in range(len(df))]
# df['cookie_first'] = [{} for x in range(len(df))]
# df['click_found'] = False

providers = ['squarespace', 'wix', 'weebly', 'jimdo', 'shopify',
             'bigcommerce', 'webnode', 'wordpress', 'medium-com',
             'Sitebuilder', 'joomla']

global_done = 0
global_notdone = 0
global_count = 0

def crawler():
    print("Method: ", end='')
    method = input()

    # Do some threading
    thread_list = []

    if method == '1':  # get host by HTML
        index_list = list(df.index)
        random.shuffle(index_list)
        for index in index_list:
            while threading.active_count() > 2000:
                time.sleep(.2)
            t = threading.Thread(target=html_getter, args=(index,), daemon=True)
            t.start()
            thread_list.append(t)

    elif method == '2':  # Selenium crawler
        print("Provider: ", end='')
        provider = input()

        if provider == 'any':
            index_list = list(df.index)

        elif provider == 'custom':
            print("Website: ", end='')
            website = input()
            index_list = list(df[df['Website'] == website].index)

        else:
            mask = df['Host'].apply(lambda x: provider in x)
            p_df = df[mask]
            index_list = list(p_df.index)

        random.shuffle(index_list)

        for index in index_list:
            while threading.active_count() > HEAD_WAIT:
                time.sleep(2)
            t = threading.Thread(target=web_opener, args=(index,), daemon=True)
            t.start()
            thread_list.append(t)

            if not HEADLESS:
                t.join()

    else:
        print("Not a valid method")
        exit(1)

    if HEADLESS:
        for t in thread_list:
            t.join()


def web_opener(index):
    try:
        this_site = df.iloc[index]
        website = this_site['Website']
        if this_site['cookie_second'] != {}:
            print(website, 'already done')
            return 0
        if not HEADLESS:
            print(website+':')
        options = Options()
        options.add_argument("--lang=en")

        if HEADLESS:
            options.add_argument("--headless")
        options.binary_location = '/Users/abel/Documents/School/Year 3/Semester 2/Thesis/Chrome/Google Chrome.app/Contents/MacOS/Google Chrome'
        driver = webdriver.Chrome(executable_path='/usr/local/Caskroom/chromedriver/80.0.3987.106/chromedriver',
                                  options=options)


        # driver.set_window_size(1440, 900)
        # driver.set_window_position(-1440, 0)
        driver.get("https://" + website)
        driver.maximize_window()
        driver.implicitly_wait(2)

        cookies = driver.get_cookies()
        with data_lock:
            if HEADLESS:
                df.at[index, 'cookie_first'] = cookies
            else:
                print(cookies)

        clicked = False

        # driver.implicitly_wait(50)

        # SSL problems with chrome
        if "Your connection is not private" in driver.page_source:
            driver.close()
            return 1
        # Other problems in chrome, these sites are untrustworthy
        if "This site can't" in driver.page_source:
            driver.close()
            return 1

        # Company called trustarc which provides cookie notices for websites (zoom.us)
        iframe = driver.find_elements_by_xpath("//iframe[contains(@src, 'trustarc')]")
        if len(iframe) != 0:
            print("Found trustarc!")
            # TODO Interact with trustarc popup

        elif "cookie" in driver.page_source:
            # cookie_div = driver.find_elements_by_xpath("//div[contains(@class, 'cookie')]")

            t_xpath = '//*[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", ' \
                      '"abcdefghijklmnopqrstuvwxyz"), "cookie")]'
            cookie_text = driver.find_elements_by_xpath(t_xpath)

            if not HEADLESS:
                # If nowhere on the website the word 'cookie' is mentioned, they're probably not asking
                if len(cookie_text) == 0:
                    print('No cookie text, they are not even asking!')
                    driver.close()
                    driver.quit()
                    return 1

                # If we found some elements with cookies, highlight them for us to see
                if len(cookie_text) > 0:
                    # print('2', cookie_text)
                    for element in cookie_text:
                        highlight(element, 'red')
            elif HEADLESS:
                if len(cookie_text) == 0:
                    with data_lock:
                        df.at[index, 'click_found'] = False
                        df.at[index, 'cookie_second'] = {'cookie': None}

            accept_div = []
            cookies = hash(str(driver.get_cookies()))
            for element in cookie_text:
                el_accept_div = []
                while len(el_accept_div) == 0:
                    try:
                        parent_element = element.find_element_by_xpath('..')
                        new_buttons = button_search(parent_element, driver.current_url)
                        for button in new_buttons:
                            if (button not in accept_div) & (button not in el_accept_div):
                                el_accept_div.append(button)
                        if len(new_buttons) > 0:
                            break
                        element = parent_element

                    except selenium.common.exceptions.InvalidSelectorException:
                        print("Upper level reached, so no possible buttons")
                        driver.close()
                        driver.quit()
                        return 1

                    finally:
                        accept_div.extend(el_accept_div)

                        # Highlight the buttons to see if they're found
                        if not HEADLESS:
                            for button in el_accept_div:
                                highlight(button, 'green')

                        for button in el_accept_div:
                            click_element(button)
                            driver.implicitly_wait(2)
                            new_cookies = hash(str(driver.get_cookies()))
                            if cookies != new_cookies:
                                clicked = True
                                break
                new_cookies = hash(str(driver.get_cookies()))
                if cookies != new_cookies:
                    break

                # TODO think about multiple click cookie walls (like the washingtonpost.com)

            # Save whether buttons were found
            if HEADLESS:
                with data_lock:
                    if clicked:
                        df.at[index, 'click_found'] = True
                    else:
                        df.at[index, 'click_found'] = False

        else:
            if not HEADLESS:
                print("No cookies anywhere!")
                return 1

        # Waiting for the user to finish on the website and continue
        if not HEADLESS:
            if not clicked:
                print('clicked', end=':')
                t = input()
                if t.lower() == 'y':
                    print(driver.get_cookies())
            elif clicked:
                print(driver.get_cookies())
                print('continue?', end='')
                input()
            print('-'*50)

        # Saving the new accepted cookies in the dataframe
        if HEADLESS:
            if clicked:
                accepted_cookies = driver.get_cookies()
                with data_lock:
                    if HEADLESS:
                        df.at[index, 'cookie_second'] = accepted_cookies


        driver.close()
        driver.quit()
        print(website, ' done')
        # with data_lock:
        #     global global_count
        #     global_count += 1
        #     if clicked:
        #         global global_done
        #         global_done += 1
        #     else:
        #         global global_notdone
        #         global_notdone += 1
        #     print(website)
        #     print("Count:", global_count)
        #     print("Done", global_done)
        #     print("Not done", global_notdone)
        #     print("-"*10)

    except urllib3.exceptions.ProtocolError:
        return 0
    except http.client.RemoteDisconnected:
        return 0
    except Exception as e:
        print(e)
        return 1


def click_element(element):
    try:
        element.click()
        if not HEADLESS: print("Clicked!")
        return True
    except selenium.common.exceptions.ElementNotInteractableException:
        if not HEADLESS: print("Could not click element - Not interactable")
        return False
    except selenium.common.exceptions.ElementClickInterceptedException:
        if not HEADLESS: print("Could not click element - Intercepted")
        return False
    except selenium.common.exceptions.StaleElementReferenceException as e:
        if not HEADLESS: print("Could not click element - Stale element")
        return False


def html_getter(index):
    this_site = df.iloc[index]
    website = this_site['Website']
    if this_site['Host checked']:
        # print(f"Got {website} already")
        return 0

    poolmanager = urllib3.PoolManager(
        cert_reqs='CERT_REQUIRED',
        ca_certs=certifi.where()
    )

    try:
        r = poolmanager.request('GET', website)
        # print(website, end=': ')
        # print(r.data)
        for p in providers:
            if p in str(r.data):
                print(f'{website} is hosted by {p}')
                with data_lock:
                    df.at[index, 'Host'].append(p)
        del r

    except urllib3.exceptions.MaxRetryError:
        # with data_lock:
        #     df.at[index, 'Host'].append('Retry ERROR')
        return 0
        # print(f'ERROR -- {website} -- ERROR')
    except urllib3.exceptions.LocationValueError:
        # with data_lock:
        #     df.at[index, 'Host'].append('Value ERROR')
        return
    with data_lock:
        df.at[index, 'Host checked'] = True


def highlight(element, color):
    """Highlights (blinks) a Selenium Webdriver element"""
    try:
        driver = element._parent
        def apply_style(s):
            driver.execute_script("arguments[0].setAttribute('style', arguments[1]);",
                                  element, s)
        original_style = element.get_attribute('style')
        style = "border: 10px solid {};".format(color)
        apply_style(style)
        time.sleep(1)
        apply_style(original_style)
    except selenium.common.exceptions.StaleElementReferenceException:
        print("No highlighting here")


def button_search(driver, website):

    website = "https://www."+website+"/"
    accept_div = []
    accept_words = [
        'accept',
        'agree',
        'ok',
        'okay',
        'yes',
        'got it',
        'browse now',
        'consent',
        'select all'
    ]

    contains_xpath = '//{}[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ",' \
                     ' "abcdefghijklmnopqrstuvwxyz"), "{}")]'
    exact_xpath = '//{}[translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ",' \
                  ' "abcdefghijklmnopqrstuvwxyz") = "{}"]'

    # Loop through the words that might give consent and make a list out of it
    for word in accept_words:
        # OK with contains will also fire on coOKie
        if (word == 'ok') | (word == 'yes'):
            a_xpath = exact_xpath
        else:
            a_xpath = contains_xpath

        # We look for divs
        div_word = driver.find_elements_by_xpath(a_xpath.format('div', word))
        # print(word, div_word)
        buttons = div_word

        # and links
        a_word = driver.find_elements_by_xpath(a_xpath.format('a', word))
        # print(word, a_word)
        buttons.extend(a_word)

        # and buttons
        button_word = driver.find_elements_by_xpath(a_xpath.format('button', word))
        # print(word, button_word)
        buttons.extend(button_word)

        # And we add all found buttons to the big list
        accept_div.extend(buttons)

        for element in accept_div:
            text = str(element.text).lower()
            if ("user" in text) | ("privacy" in text):
                accept_div.remove(element)

    # Check for all links in the element (and whether they link away from the current url)
    links = driver.find_elements_by_tag_name("a")
    for a in links:
        link_url = str(a.get_attribute("href"))
        link_url = link_url.split(sep='/')

        if len(link_url) > 2:
            if link_url[2] == ('www.'+website):
                if link_url[3] == '#':
                    if not HEADLESS: print(link_url[3])
                    accept_div.append(a)
                elif link_url[3] == '':
                    if not HEADLESS: print(link_url[3])
                    accept_div.append(a)
        elif len(link_url) == 1:
            if 'javascript' in link_url[0]:
                if not HEADLESS: print(link_url)
                accept_div.append(a)
            if 'None' in link_url[0]:
                if not HEADLESS: print(link_url)
                accept_div.append(a)
        else:
            print("Not filtered", link_url)

    # TODO check for buttons in the recursive search as well (slideshare.net)
    buttons = driver.find_elements_by_tag_name("button")
    for b in buttons:
        accept_div.append(b)
    return accept_div


def main():

    crawler()
    print("Visited all the websites (unlikely)")
    df.to_csv('assets/DataFrame.csv', index=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        df.to_csv('assets/DataFrame.csv', index=False)
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
