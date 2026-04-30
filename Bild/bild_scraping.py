import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from constants import Article_object, Utils, RSS, Categories, Kategorien


def scrape_bild_article(link):
    try:
        dom = requests.get(link)
        soup = BeautifulSoup(dom.text, "html.parser")

        paragraphs = soup.select("div.article-body p")

        publish_at_tag = soup.find("time")
        if publish_at_tag and 'datetime' in publish_at_tag.attrs:
            raw_dt = publish_at_tag['datetime']
            try:
                dt = datetime.fromisoformat(raw_dt.replace('Z', '+00:00'))
                publish_at = dt.replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                return None, None, None
        else:
            publish_at = None

        title = soup.find("span", class_="headline")
        title = title.text.strip() if title else None

        content = ""
        for p in paragraphs:
            content += p.text.strip() + " "

        return content.strip(), publish_at, title

    except TypeError:
        return None, None, None


def check_bild_exclusiv(link):
    dom = requests.get(link)
    soup = BeautifulSoup(dom.text, "html.parser")
    exclusiv = soup.find(True, class_='offer-module')
    return True if exclusiv else False


def get_bild_articles(limit=None):
    links = Utils.fetch_article_links(RSS.bild_rss)
    articles = Utils.process_german_articles(
        "Bild",
        "de",
        links,
        scrape_bild_article,
        check_bild_exclusiv
    )
    return articles
