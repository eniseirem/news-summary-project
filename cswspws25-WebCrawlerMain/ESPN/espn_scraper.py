import requests
import time
from bs4 import BeautifulSoup
from constants import Static_values, RSS, Utils

def scrape_espn_article(url):
    dom = requests.get(url, headers=Static_values.headers)
    soup = BeautifulSoup(dom.text,"html.parser")
    paragraphs = soup.find("div",attrs={'class':'article-body'}).find_all("p", recursive=False)
    title = soup.select("header.article-header h1")
    title = str(title).split('</h1>')[0].split('>')[1]
    publish_at = soup.select("div.article-meta span.timestamp")
    publish_at = str(publish_at).split('</span>')[0].split(">")[1].split(',')
    year = int(publish_at[1])
    month = Static_values.months.index(publish_at[0].split(' ')[0])
    day = int(publish_at[0].split(' ')[1])
    hour = int(publish_at[-1].split(':')[0])
    pm_am = publish_at[-1].split(':')[1].split(' ')[1]
    hour = hour if pm_am=='am' else hour+12
    minute = int(publish_at[-1].split(':')[1].split(' ')[0])
    tz = publish_at[-1].split(':')[1].split(' ')[2]
    publish_date = Utils.to_iso8601(year, month, day, hour, minute,tz)
    content=""
    for p in paragraphs:
        content += p.text.strip()
    return content, publish_date, title

def get_espn_articles(limit = None):
    links = Utils.fetch_article_links(RSS.espn_rss)
    articles = Utils.process_articles(
        "ESPN",
        "en",
        links,
        scrape_espn_article,
        paywall_detecter_function=None,
        forced_category="sports")
    return articles