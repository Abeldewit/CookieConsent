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
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from threading import Lock
import http

# Global settings
HEADLESS = True
RESET = False
HEAD_WAIT = 15


# Writing to the DataFrame while threading
data_lock = Lock()
# Load the DataFrame
df = pd.read_csv('assets/DataFrame.csv', converters={"Host": literal_eval,
                                                     "cookie_first": literal_eval,
                                                     "cookie_second": literal_eval
                                                     })

# # DF RESET # #
if RESET:
    df['cookie_second'] = [{} for x in range(len(df))]
    df['cookie_first'] = [{} for x in range(len(df))]
    df['click_found'] = False

# Biggest website providers
providers = ['squarespace', 'wix', 'weebly', 'jimdo', 'shopify',
             'bigcommerce', 'webnode', 'wordpress', 'medium-com',
             'Sitebuilder', 'joomla']


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


# Search for a button that is clickable, but doesn't lead to another website
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
                    if not HEADLESS:
                        print(link_url[3])
                    accept_div.append(a)
                elif link_url[3] == '':
                    if not HEADLESS:
                        print(link_url[3])
                    accept_div.append(a)
        elif len(link_url) == 1:
            if 'javascript' in link_url[0]:
                if not HEADLESS:
                    print(link_url)
                accept_div.append(a)
            if 'None' in link_url[0]:
                if not HEADLESS:
                    print(link_url)
                accept_div.append(a)
        else:
            print("Not filtered", link_url)

    # TODO check for buttons in the recursive search as well (slideshare.net)
    buttons = driver.find_elements_by_tag_name("button")
    for b in buttons:
        accept_div.append(b)
    return accept_div


# Try to click the WebElement passed
def click_element(element):
    try:
        element.click()
        if not HEADLESS:
            print("Clicked!")
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
    print("Method: ", end='')
    method = input()

    # Do some threading
    thread_list = []

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

        # random.shuffle(index_list)
        target = web_opener

    elif method == '3':
        print("Provider: ", end='')
        provider = input()

        mask = df['Host'].apply(lambda x: provider in x)
        p_df = df[mask]
        index_list = list(p_df.index)
        target = extension_opener

    else:
        print("Not a valid method")
        exit(1)

    for index in index_list:
        while threading.active_count() > HEAD_WAIT:
            time.sleep(2)
        t = threading.Thread(target=target, args=(index,), daemon=True)
        t.start()
        thread_list.append(t)

        if not HEADLESS:
            t.join()

    if HEADLESS:
        for t in thread_list:
            t.join()


# Opening the webpage and searching for a button
def web_opener(index):
    try:

        # Get the site by index
        this_site = df.iloc[index]
        website = this_site['Website']

        # See if it is already done in earlier runs
        if (this_site['cookie_second'] != {}) & HEADLESS:
            print(website, 'already done')
            return 0
        if not HEADLESS:
            print(website+':')

        # Setting chrome options
        options = Options()
        options.add_argument("--lang=en")

        if HEADLESS:
            options.add_argument("--headless")
        options.binary_location = '/Users/abel/Documents/School/Year 3/Semester 2/Thesis/Chrome/' \
                                  'Google Chrome.app/Contents/MacOS/Google Chrome'
        driver = webdriver.Chrome(executable_path='/usr/local/Caskroom/chromedriver/80.0.3987.106/chromedriver',
                                  options=options)

        # driver.set_window_size(1440, 900)
        # driver.set_window_position(-1440, 0)

        # Loading the webpage
        driver.get("https://" + website)
        driver.maximize_window()
        driver.implicitly_wait(2)

        # Getting the first initial cookie and save it (or print it)
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

        # Company called Trust Arc which provides cookie notices for websites (zoom.us)
        iframe = driver.find_elements_by_xpath("//iframe[contains(@src, 'trustarc')]")
        if len(iframe) != 0:
            print("Found trustarc!")
            # TODO Interact with trustarc popup

        # If the text 'cookie' appears somewhere in the page's source code
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

        # If none of these options work, there must simply not be a banner
        else:
            if not HEADLESS:
                print("No cookies anywhere!")
                driver.close()
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

    # Both these exceptions occur when closing the program (and thus the connection, we can safely catch them)
    except urllib3.exceptions.ProtocolError:
        return 0
    except http.client.RemoteDisconnected:
        return 0
    except Exception as e:
        print(e)
        return 1


# Open a website in chrome with an extension loaded
def extension_opener(index):
    this_site = df.iloc[index]
    website = this_site['Website']

    print(website + ':')
    options = Options()
    options.add_argument("--lang=en")

    if HEADLESS:
        options.add_argument("--headless")
    options.binary_location = '/Users/abel/Documents/School/Year 3/Semester 2/Thesis/Chrome/' \
                              'Google Chrome.app/Contents/MacOS/Google Chrome'
    driver = webdriver.Chrome(executable_path='/usr/local/Caskroom/chromedriver/80.0.3987.106/chromedriver',
                              options=options)

    driver.get("https://" + website)
    driver.implicitly_wait(4)
    cookies = driver.get_cookies()
    print(cookies)

    if not HEADLESS:
        print("clicked: ", end='')
        input()
    print(driver.get_cookies())
    driver.close()

    options.add_extension('/Users/abel/Documents/School/Year 3/Semester 2/Thesis/Chrome/extension_3_1_8_0.crx')
    driver = webdriver.Chrome(executable_path='/usr/local/Caskroom/chromedriver/80.0.3987.106/chromedriver',
                              options=options)
    driver.get("https://" + website)
    driver.implicitly_wait(4)

    cookies = driver.get_cookies()
    print(cookies)
    if not HEADLESS:
        input()
    driver.close()


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
