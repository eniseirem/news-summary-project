import requests
from bs4 import BeautifulSoup
from constants import Article_object, Static_values, Utils
from datetime import datetime,timezone

def scrape_SCMP_econ_article(url):
    dom = requests.get(url, headers=Static_values.headers)
    soup = BeautifulSoup(dom.text,"html.parser")
    content_container = soup.find("div", attrs={'data-qa':'GenericArticle-Content'})
    paragraphs = content_container.find_all(attrs={'data-qa':'Component-Component'})
    title = soup.find("h1", attrs={'data-qa':'ContentHeadline-ContainerWithTag'})
    title = title.find("span", attrs={'data-qa':'ContentHeadline-Headline'}).text
    publish_at = soup.select("time")[0]
    publish_date = publish_at['datetime'].replace('.000','')
    content=""
    for p in paragraphs:
        content += p.text.strip()
    if content=="":
        return None,None,None
    return content, publish_date, title

def get_scmp_econ_articles(limit = None):
    links = Utils.fetch_article_links("https://www.scmp.com/rss/318421/feed/")
    articles = Utils.process_articles("South Morning China Post","en",links,scrape_SCMP_econ_article, paywall_detecter_function=None)
    return articles
  