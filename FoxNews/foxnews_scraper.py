import requests
from bs4 import BeautifulSoup
from constants import RSS, Static_values, Utils
from datetime import datetime, timezone


def scrape_foxnews_article(url):
    dom = requests.get(url)
    soup = BeautifulSoup(dom.text,"html.parser")
    paragraphs = soup.find("div",attrs={'class':'article-body'}).findChildren("p", recursive=True)
    title = soup.select("h1.headline")
    title = str(title).split('</h1>')[0].split('>')[1]
    publish_at = soup.find("time")['datetime']
    dt = datetime.fromisoformat(publish_at)
    publish_at_utc = dt.astimezone(timezone.utc)
    publish_at_utc = publish_at_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    content=""
    for p in paragraphs[:-1]:
        if not p.find("a", recursive=False):
            content += p.text.strip()
    content = Utils.clean_body(content, Static_values.encoding_artifacts, Static_values.foxnews_unrelevant_content)
    return content, publish_at_utc, title

def get_foxnews_articles(limit = None):
    links = Utils.fetch_article_links(RSS.foxnews_rss)
    articles = Utils.process_articles("FoxNews","en",links,scrape_foxnews_article, paywall_detecter_function=None)
    return articles