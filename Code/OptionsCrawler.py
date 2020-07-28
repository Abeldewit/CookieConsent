import os
import sys
from ast import literal_eval
from typing import List, Any

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

# Global settings
HEADLESS = True
RESET = False
SHUFFLE = True
HEAD_WAIT = 15


# Writing to the DataFrame while threading
data_lock = Lock()
# Load the DataFrame
global_df = pd.read_csv('assets/DataFrame.csv', converters={"Host": literal_eval,
                                                     "cookie_first": literal_eval,
                                                     "cookie_second": literal_eval
                                                     })


def option_crawler(row):
    try:
        website = row['Website']

        # See if it is already done in earlier runs
        if (row['cookie_second'] != {}) & HEADLESS:
            # print(website, 'already done')
            return 0

        print(website + ':')

        # Setting chrome options
        options = Options()

        options.binary_location = '/Users/abel/Documents/School/Year 3/Semester 2/Thesis/Chrome/' \
                                  'Google Chrome.app/Contents/MacOS/Google Chrome'
        alpha = 'abcdefghijklmnopqrstuvwxyz'
        languages = {}
        for i in range(len(alpha)):
            for j in range(len(alpha)):
                lan_1 = alpha[i] + alpha[j]
                lan_2 = 'en'
                languages[lan_1] = lan_2
        prefs = {
            "translate_whitelists": languages,
            "translate": {"enabled": "true"}
        }
        options.add_experimental_option("prefs", prefs)
        driver = webdriver.Chrome(executable_path='/usr/local/Caskroom/chromedriver/80.0.3987.106/chromedriver',
                                  options=options)

        driver.set_window_size(1194, 834)
        driver.set_window_position(-1194, 0)

        # Loading the webpage
        driver.get("https://" + website)
        driver.implicitly_wait(5)

        pref_words = ['settings', 'preferences', 'options']

        xpath = ""
        for name in pref_words:
            xpath += './/*[text()[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", ' \
                          '"abcdefghijklmnopqrstuvwxyz"), "{}")]]'.format(name)
            xpath += '|'
        xpath = xpath[:-1]

        settings = driver.find_elements_by_xpath(xpath)
        i = 0
        driver.execute_script("arguments[0].click();", settings[i])
        while input("found settings") != 'y':
            i += 1
            driver.execute_script("arguments[0].click();", settings[i])
        print(settings)

        input("continue?")
        driver.close()
        driver.quit()
    except Exception as e:
        print(e)


def main():
    opt_df = global_df[(global_df['options_available'] == True) & (global_df['banner_provider'] == 'Unknown')]
    for index, row in opt_df.iterrows():
        option_crawler(row)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)