from ast import literal_eval

import urllib3
import requests
from contextlib import closing
from selenium import webdriver
import codecs
import csv
import pandas as pd


def main():
    #arsen_php()
    majestic()
    arsen_df = pd.read_csv('assets/web_list_2.csv', converters={"Host": literal_eval})
    majestic_df = pd.read_csv('assets/Majestic.csv', converters={"Host": literal_eval})


def arsen_php():
    php_list = "http://93.190.139.218/abel.php"

    http = urllib3.PoolManager()
    r = http.request(url=php_list, method='GET')
    data = str(r.data)
    sites = data.split('<br>')
    sites[0] = sites[0].split('\\n')[-1]
    print(f'Grabbed {len(sites)} websites')

    #write to csv
    writer = csv.writer(open('assets/web_list_2.csv', 'w'))
    for site in sites:
        writer.writerow([site])


def majestic():
    # Download the csv file and save it to a local version
    majestic_million = "http://downloads.majestic.com/majestic_million.csv"
    with closing(requests.get(majestic_million, stream=True)) as r:
        cr = csv.reader(codecs.iterdecode(r.iter_lines(), 'utf-8'), delimiter=',')
        web_list = list(cr)
        writer = csv.writer(open('assets/Majestic.csv', 'w'))
        firstrow = True
        for row in web_list:
            if not firstrow:
                new_row = [row[2], '[]']
                writer.writerow(new_row)
            else:
                firstrow = False


if __name__ == "__main__":
    main()
