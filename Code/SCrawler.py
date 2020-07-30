import logging
import os
import sys
from ast import literal_eval
from typing import List, Any

import psutil as psutil
import selenium
import urllib3
import certifi
import time
import threading
import random
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from threading import Lock
import http
from bs4 import BeautifulSoup
import itertools
import errno
from datetime import datetime

# Global settings
HEADLESS = True
RESET = False
SHUFFLE = True
HEAD_WAIT = 23

_TOOFILE = False


# Writing to the DataFrame while threading
data_lock = Lock()
# Load the DataFrame
df = pd.read_csv('assets/DataFrame.csv', converters={"Host": literal_eval,
                                                     "cookie_first": literal_eval,
                                                     "cookie_accept": literal_eval,
                                                     "cookie_decline": literal_eval
                                                     })

# # DF RESET # #
if RESET:
    df['banner_provider'] = ["" for _ in range(len(df))]
    df['options_available'] = False
    df['cookie_first'] = [{} for _ in range(len(df))]
    df['cookie_accept'] = [{} for _ in range(len(df))]
    df['click_found'] = False
    df['done'] = False

    cols = ['Website', 'Host', 'banner_provider', 'options_available', 'cookie_first',
            'click_found_a', 'cookie_accept', 'click_found_d', 'cookie_decline', 'done'
            ]
    df = df[cols]


# Biggest website providers
providers = ['squarespace', 'wix', 'weebly', 'jimdo', 'shopify',
             'bigcommerce', 'webnode', 'wordpress', 'medium-com',
             'Sitebuilder', 'joomla']

languages = {}
alpha = 'abcdefghijklmnopqrstuvwxyz'
for i in range(len(alpha)):
    for j in range(len(alpha)):
        lan_1 = alpha[i] + alpha[j]
        lan_2 = 'en'
        languages[lan_1] = lan_2


# Mainly for debugging, this method highlights the element passed, with the color passed
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


# Searching the current element for certain search words
def xpath_search_words(search_element, search_words):
    contains_xpath = './/{}[text()[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ",' \
                     ' "abcdefghijklmnopqrstuvwxyz"), "{}")]]'
    exact_xpath = './/{}[text()[translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ",' \
                  ' "abcdefghijklmnopqrstuvwxyz") = "{}"]]'

    els = ['div', 'a', 'button', '*']

    # Loop through the words that might give consent and make a list out of it
    g_xpath = ""
    for word in search_words:
        # OK with contains will also fire on coOKie
        if (word == 'ok') | (word == 'yes') | (word == 'no'):
            a_xpath = exact_xpath
        else:
            a_xpath = contains_xpath

        for e in els:
            g_xpath += a_xpath.format(e, word)
            g_xpath += ' | '
    g_xpath = g_xpath[:-3]

    found_list = search_element.find_elements_by_xpath(g_xpath)
    found_list = [el for el in found_list if len(el.text) < 25]
    found_list = [el for el in found_list if "privacy" not in el.text]
    return found_list


def find_links(search_element, search_words, s_all, website):
    if not HEADLESS:
        print("No buttons, let's search links?")
    links = search_element.find_elements_by_tag_name("a")
    found_list = []
    for a in links:
        link_url = str(a.get_attribute("href"))
        link_url = link_url.split(sep='/')

        onclick = a.get_attribute('onclick')
        if onclick is not None:
            if 'cookie' in onclick:
                found_list.append(a)
                continue
            if 'dismiss' in onclick:
                found_list.append(a)
                continue

        linkclass = a.get_attribute('class')
        if linkclass is not None:
            if 'cookie' in linkclass:
                found_list.append(a)
                continue
            if 'dismiss' in linkclass:
                found_list.append(a)
                continue
            if 'accept' in linkclass:
                found_list.append(a)
                continue

        if len(a.text) > 0:
            if a.text not in search_words:
                # print("lna:", a.text)
                continue
            if s_all:
                if a.text in search_words:
                    found_list.append(a)
                    continue

        if s_all:
            if len(link_url) > 2:
                if link_url[2] == ('www.' + website):
                    if link_url[3] == '#':
                        if not HEADLESS:
                            print('l', link_url[3])
                        found_list.append(a)
                    elif link_url[3] == '':
                        if not HEADLESS:
                            print('l', link_url[3])
                        found_list.append(a)
            elif len(link_url) == 1:
                if 'javascript' in link_url[0]:
                    if not HEADLESS:
                        print('l', link_url)
                    found_list.append(a)
                if 'None' in link_url[0]:
                    if not HEADLESS:
                        print('l', link_url)
                    found_list.append(a)
            else:
                print("Not filtered", link_url)
    found_list = [el for el in found_list if "privacy" not in el.text]
    found_list = [el for el in found_list if len(el.text) < 25]

    if len(found_list) == 0:
        # Last resort, searching images...
        imgs = search_element.find_elements_by_xpath(".//img")
        for i in imgs:
            found_list.append(i)
    return found_list


# Search for a button that is clickable, but doesn't lead to another website
def button_search(search_element, website):
    if not HEADLESS:
        print("Button search")

    accept_words = [
        'accept',
        'allow',
        'agree',
        'ok',
        'okay',
        'yes',
        'got it',
        'browse now',
        'consent',
        'understand',
        'dismiss',
        'continue',
        'opt in',
        'fine',
        "don't show again",
        'roger that'
    ]

    decline_words = [
        'refuse',
        'reject',
        'decline',
        'no',
        'opt out'
    ]

    options_words = [
        'settings',
        'choose',
        'options',
        'preferences'
        'manage cookies'
    ]

    accept_list = xpath_search_words(search_element, accept_words)
    decline_list = xpath_search_words(search_element, decline_words)
    options_list = xpath_search_words(search_element, options_words)

    # Check for all links in the element (and whether they link away from the current url)
    if len(accept_list) == 0:
        accept_list.extend(find_links(search_element, accept_words, True, website))
    elif len(decline_list) == 0:
        decline_list.extend(find_links(search_element, decline_words, False, website))

    # See if they provide options or if you consent by using the website already
    use_consent_list = ['using our website, you agree', 'use our site you consent', 'by continuing to browse']
    use_consent = xpath_search_words(search_element, use_consent_list)
    # TODO Save whether they give you a choice or by browsing you consent

    # Sorting on length (text goes before buttons without text)
    accept_list.sort(key=lambda x: len(x.text), reverse=True)
    options_list.sort(key=lambda x: len(x.text), reverse=True)
    options_list = [o for o in options_list if len(o.text) > 0]
    decline_list.sort(key=lambda x: len(x.text), reverse=True)

    if not HEADLESS:
        print_butn = [b.text for b in accept_list]
        print('btns:', print_butn)
        print_opts = [o.text for o in options_list]
        print('opts:', print_opts)
        print_decl = [d.text for d in decline_list]
        print('decl:', print_decl)

    return accept_list, options_list, decline_list


# Try to click the WebElement passed
def click_element(driver, element):
    try:
        # element.click()
        driver.execute_script("arguments[0].click();", element)
        # if not HEADLESS:
        #     print("Clicked!")
        return True
    except selenium.common.exceptions.ElementNotInteractableException:
        if not HEADLESS:
            print("Could not click element - Not interactable")
        return False
    except selenium.common.exceptions.ElementClickInterceptedException:
        if not HEADLESS:
            print("Could not click element - Intercepted")
        return False
    except selenium.common.exceptions.StaleElementReferenceException:
        if not HEADLESS:
            print("Could not click element - Stale element")
        return False


# Search for website host keywords in the html to categorize all the websites
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


# The crawler menu, setting up the method to be used and the websites to be searched
def crawler():
    if not HEADLESS:
        print("Method: ", end='')
        method = input()

        target = web_opener
        index_list = list(df.index)

        if method == '1':  # get host by HTML
            random.shuffle(index_list)
            target = html_getter

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
            if SHUFFLE:
                random.shuffle(index_list)
            target = web_opener

        else:
            print("Not a valid method")
            exit(1)
    if HEADLESS:
        index_list = list(df.index)
        target = web_opener
        if SHUFFLE:
            random.shuffle(index_list)

    # Do some threading
    thread_list = []

    for index in index_list:
        while threading.active_count() > HEAD_WAIT:
            time.sleep(5)
        if _TOOFILE:
            print("TOO MANY FILES")
            time.sleep(30)
            restart_program(thread_list)
            break
        t = threading.Thread(target=target, args=(index,), daemon=True)
        t.start()
        thread_list.append(t)

        # t2 = threading.Thread(target=target, args=(index, False,), daemon=True)
        # t2.start()
        # thread_list.append(t2)

        if not HEADLESS:
            t.join()

    if HEADLESS:
        for t in thread_list:
            t.join()


def parent_search(driver, element):
    accept_list = {}
    options_list = {}
    decline_list = {}
    if not HEADLESS:
        print("searching from:", element.text[:50])

    iter_element = element
    for level in range(1, 10):
        # Get the parent element of our cookie text
        try:
            iter_element = iter_element.find_element_by_xpath('..')
        except selenium.common.exceptions.StaleElementReferenceException:
            break
        if iter_element.tag_name == 'body':
            break

        accept_list[level] = []
        options_list[level] = []
        decline_list[level] = []

        if not HEADLESS:
            # Make it yellow to show the search area
            highlight(iter_element, 'yellow')

        # Find possible buttons
        accept_list_t, options_list_t, decline_list_t = button_search(iter_element, driver.current_url)

        # If the new button is not in any list yet, we add it
        for button in accept_list_t:
            if level == 1:
                accept_list[level].append(button)
            elif button not in accept_list[level-1]:
                accept_list[level].append(button)

        for button in options_list_t:
            if level == 1:
                options_list[level].append(button)
            elif button not in options_list[level-1]:
                options_list[level].append(button)

        for button in decline_list_t:
            if level == 1:
                decline_list[level].append(button)
            elif button not in decline_list[level-1]:
                decline_list[level].append(button)

        # print('a', [a.text for a in accept_list[level]])
        # print('o', [a.text for a in options_list[level]])

        if len(accept_list[level]) > 0 & len(options_list) > 0:
            break
        if level > 2:
            if len(accept_list[level]) > 0:
                if (len(options_list[level-1]) >= len(options_list[level])) \
                        & (len(accept_list[level-1]) >= len(accept_list[level])):
                    del accept_list[level], options_list[level], decline_list[level]
                    break

    return accept_list, options_list, decline_list


# Opening the web-page and searching for a button
def web_opener(index):
    global _TOOFILE
    # Get the site by index
    this_site = df.iloc[index]
    website = this_site['Website']
    current_time = datetime.now().strftime("%H:%M:%S")

    # See if it is already done in earlier runs
    if (this_site['click_found']) & HEADLESS:
        # print(website, 'already done')
        return 0

    if not HEADLESS:
        print(website + ':')

    # Setting chrome options
    options = Options()
    options.add_argument("--lang=en")

    if HEADLESS:
        options.add_argument("--headless")
    options.binary_location = '/Users/abel/Documents/School/Year 3/Semester 2/Thesis/Chrome/' \
                              'Google Chrome.app/Contents/MacOS/Google Chrome'

    prefs = {
        "translate_whitelists": languages,
        "translate": {"enabled": "true"}
    }
    options.add_experimental_option("prefs", prefs)
    try:
        driver = webdriver.Chrome(executable_path='/usr/local/Caskroom/chromedriver/80.0.3987.106/chromedriver',
                                options=options)
    except OSError as err:
        if err.errno == errno.EMFILE:
            with data_lock:
                _TOOFILE = True
                return -1

    # Moving the screen to the second monitor
    if not HEADLESS:
        driver.set_window_size(1194, 834)
        driver.set_window_position(-1194, 0)

    # Loading the webpage
    driver.get("https://" + website)
    # driver.maximize_window()
    driver.implicitly_wait(1)

    # SSL problems with chrome
    if "Your connection is not private" in driver.page_source:
        driver.close()
        return 1
    # Other problems in chrome, these sites are untrustworthy
    if "This site can't" in driver.page_source:
        driver.close()
        return 1

    try:
        # Getting the first initial cookie and save it (or print it)
        cookies = driver.get_cookies()
        with data_lock:
            if HEADLESS:
                df.at[index, 'cookie_first'] = cookies
            else:
                print(cookies)
        # After saving, the cookie is hashed for readability/comparability
        cookies = hash(str(cookies))

        clicked = False

        # Company called Trust Arc which provides cookie notices for websites (zoom.us)
        trustarc = driver.find_elements_by_xpath("//iframe[contains(@src, 'trustarc')]")

        # Company called Trust Arc which provides cookie notices for websites (zoom.us)
        onetrust = driver.find_elements_by_xpath("//div[contains(@class, 'optanon-alert-box-wrapper')]")
        onetrust.extend(driver.find_elements_by_xpath("//div[contains(@id, 'onetrust')]"))

        # Cybot cookie
        cybotcookiebot = driver.find_elements_by_id("CybotCookiebotDialogBody")
        if len(trustarc) != 0:
            #print("Found trustarc")
            with data_lock:
                df.at[index, 'banner_provider'] = "TrustArc"
                df.at[index, 'options_available'] = True
            # TODO Interact with trustarc popup

        elif len(onetrust) != 0:
            with data_lock:
                df.at[index, 'banner_provider'] = "OneTrust"
                df.at[index, 'options_available'] = True

            return 0

        elif len(cybotcookiebot) != 0:
            with data_lock:
                df.at[index, 'banner_provider'] = "Cybot"
                df.at[index, 'options_available'] = True

        # If the text 'cookie' appears somewhere in the page's source code
        if "cookie" in driver.page_source:
            t_xpath = './/*[text()[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", ' \
                      '"abcdefghijklmnopqrstuvwxyz"), "cookie")]]'
            body = driver.find_element_by_tag_name('body')
            cookie_text = body.find_elements_by_xpath(t_xpath)

            # Scripts don't count as cookie banner
            for element in list(cookie_text):
                if len(element.text) == 0:
                    cookie_text.remove(element)
                elif element.tag_name == 'script':
                    cookie_text.remove(element)
                elif element.tag_name == 'noscript':
                    cookie_text.remove(element)
            cookie_text.sort(key=lambda x: len(x.text), reverse=True)

            if not HEADLESS:
                # If nowhere on the website the word 'cookie' is mentioned, they're probably not asking
                if len(cookie_text) == 0:
                    print('No cookie text on the page!')
                    driver.close()
                    driver.quit()
                    return 1

                # # If we found some elements with cookies, highlight them for us to see
                # if len(cookie_text) > 0:
                #     for element in cookie_text:
                #         highlight(element, 'red')

            elif HEADLESS:
                if len(cookie_text) == 0:
                    with data_lock:
                        df.at[index, 'click_found_a'] = False
                        df.at[index, 'cookie_accept'] = [None]

                        driver.close()
                        driver.quit()
                        return 1

            for element in list(cookie_text):
                if not HEADLESS:
                    highlight(element, 'red')
                accept_list, options_list, decline_list = parent_search(driver, element)
                # print('lists:\n ', accept_list, '\n', options_list, '\n', decline_list)

                for i in range(1, len(options_list)+1):
                    # If we found options
                    if len(options_list[i]) > 0:
                        for button in options_list[i]:
                            tmp_clicked_o = click_element(driver, button)
                            if tmp_clicked_o:
                                # find consensu iframe (idg.com.au)
                                # consensu_interact(driver, iframe[0]) # idg.com.au
                                print("Found options!")
                                with data_lock:
                                    df.at[index, 'banner_provider'] = "Unknown"
                                    df.at[index, 'options_available'] = True

                button_list = accept_list

                for n in range(1, len(button_list)+1):
                    if len(button_list[n]) > 0 & (not clicked):
                        # ...try to click them
                        for button in button_list[n]:
                            if not HEADLESS:
                                # ...and show them
                                highlight(button, 'green')
                                print(button.get_attribute("onclick"))
                            tmp_clicked = click_element(driver, button)
                            driver.implicitly_wait(1)

                            # Now get the current cookie
                            new_cookies = hash(str(driver.get_cookies()))
                            # and if it is different from our initial cookie we found it and stop
                            if (cookies != new_cookies) & tmp_clicked:
                                clicked = True
                                break
                            else:
                                continue
                    if clicked:
                        break
                    else:
                        continue
                if clicked:
                    break
                else:
                    continue

                # TODO think about multiple click cookie walls (like the washingtonpost.com)

        # If none of these options work, there must simply not be a banner
        else:
            if not HEADLESS:
                print("No cookies in the source!")
                # TODO Save that this website does not show any banner
            driver.close()
            return 1

        # Waiting for the user to finish on the website and continue
        if not HEADLESS:
            if not clicked:
                t = input('clicked:')
                if t.lower() == 'y':
                    print(driver.get_cookies())
            elif clicked:
                print(driver.get_cookies())
                input('continue?')
            print('-'*50)

        # Saving the new accepted cookies in the dataframe
        if HEADLESS:
            with data_lock:
                accepted_cookies = driver.get_cookies()
                if clicked:
                    if HEADLESS:
                        df.at[index, 'cookie_accept'] = accepted_cookies
                        df.at[index, 'click_found_a'] = True

                else:
                    df.at[index, 'click_found_a'] = False

        driver.close()
        driver.quit()

        new_time = datetime.now().strftime("%H:%M:%S")
        print(website, ' done', current_time, new_time)
        with data_lock:
            df.at[index, 'done'] = True

    # Both these exceptions are thrown when closing the program (and thus the connection, we can safely catch them)
    except urllib3.exceptions.ProtocolError:
        driver.close()
        driver.quit()
        return 0
    except http.client.RemoteDisconnected:
        driver.close()
        driver.quit()
        return 0
    except OSError as err:
        print("OS error: {0}".format(err))
        print(err.errno)
        if err.errno == errno.EBADF:
            return -1


def main():
    global _TOOFILE
    _TOOFILE = False
    crawler()
    print("Visited all the websites (unlikely)")
    df.to_csv('assets/DataFrame.csv', index=False)


def restart_program(thread_list):
    """Restarts the current program, with file objects and descriptors
       cleanup
    """

    try:
        p = psutil.Process(os.getpid())
        for handler in p.open_files() + p.connections():
            os.close(handler.fd)
    except Exception as e:
        logging.error(e)

    print('*'*20, 'RESTART', '*'*20)
    global _TOOFILE
    _TOOFILE = False
    time.sleep(10)
    python = sys.executable
    os.execl(python, python, *sys.argv)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        df.to_csv('assets/DataFrame.csv', index=False)
        print('Interrupted')
        print('accept:', df['click_found_a'].sum())
        print('decline:', df['click_found_d'].sum())
        print('options:', df['options_available'].sum())
        print('done:', df['done'].sum())
        # restart_program()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
