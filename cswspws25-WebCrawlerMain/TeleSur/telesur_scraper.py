import requests
from bs4 import BeautifulSoup
from constants import Article_object, Static_values, Utils, Categories
from datetime import datetime,timezone

def scrape_telesur_article(url):
    dom = requests.get(url, headers=Static_values.headers)
    soup = BeautifulSoup(dom.text,"html.parser")
    content_container = soup.find("div", class_="content-area__text__full") 
    paragraphs = content_container.find_all("p", recursive=False)
    title = soup.find("h1", class_="content-area__title").text.strip()
    publish_at = soup.find("div", class_='date-header').text.strip()
    year = int(publish_at.split(',')[1])
    month = Static_values.months.index(publish_at.split(',')[0].split(' ')[0][:3])
    day = int(publish_at.split(',')[0].split(' ')[1])
    hour = 0
    minute = 0
    tz = "GMT"
    publish_date = Utils.to_iso8601(year,month,day,hour,minute,tz)
    content=""
    for p in paragraphs[:-3]:
        content += p.text.strip()
    if content=="":
        return None,None,None
    return content, publish_date, title


def get_telesur_articles(limit = None):
    links = Utils.fetch_article_links("https://www.telesurenglish.net//rss")
    articles = Utils.process_articles("TeleSur","en",links,scrape_telesur_article, paywall_detecter_function=None)
    return articles