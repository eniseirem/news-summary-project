import requests
from bs4 import BeautifulSoup
from constants import Article_object, Static_values, RSS, Utils
from datetime import datetime,timezone

def scrape_yahoofinance_article(url):
    dom = requests.get(url, headers=Static_values.headers)
    soup = BeautifulSoup(dom.text,"html.parser")
    paragraphs = soup.select("div.bodyItems-wrapper p")
    title = soup.select("h1.cover-title")
    try:
        title = str(title).split('</h1>')[0].split('>')[1]
    except IndexError:
        return None, None, None
    publish_at = soup.find("time")
    if publish_at and 'datetime' in publish_at.attrs:
        publish_at = publish_at['datetime'].replace(".000","")
    else:
        publish_at=None
    content=""
    for p in paragraphs:
        content += p.text.strip()
    return content, publish_at, title

def get_yahoofinance_articles(limit = None):
    links =Utils.fetch_article_links(RSS.yahoofinance_rss)
    articles = Utils.process_articles(
        "YahooFinance",
        "en",
        links,
        scrape_yahoofinance_article,
        paywall_detecter_function=None)
    return articles