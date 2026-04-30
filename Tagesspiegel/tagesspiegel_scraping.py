import requests
from bs4 import BeautifulSoup
#local import
from constants import Article_object, Static_values, Utils, Categories, Kategorien

def scrape_tagesspiegel_article(url):
    try:
        article = f"{url}"
        dom = requests.get(article)
        soup = BeautifulSoup(dom.text, "html.parser")
        paragraphs = soup.find_all("p")
        publish_at = soup.find("time")
        if publish_at and 'datetime' in publish_at.attrs:
            publish_at = publish_at['datetime'].split('T')[0]
        else:
            publish_at=None
        content = ""
        title=soup.select_one("h1").get_text()
        for p in paragraphs[1:-2]:
            content +=p.text.strip()
        content = content.replace(Static_values.tagesspiegel_data_privacy,' ')
        return content, publish_at, title
    except TypeError:
        return None,None,None

def scrape_article_links():
    outlet = "https://www.tagesspiegel.de/"
    dom = requests.get(outlet)
    soup = BeautifulSoup(dom.text, "html.parser")
    articles = soup.find_all("article")
    article_references = []
    for article in articles:
        links = article.find_all('a')
        for link in links:
            href = link.get("href")
            if href!=None:
                article_references.append(outlet+href)
    return article_references

def check_article_existence(link):
    dom = requests.get(link)
    soup = BeautifulSoup(dom.text, "html.parser")
    exclusiv = soup.find_all(True,id='paywall')
    return False if exclusiv else True
  
def get_all_articles_content(limit = None):
    links = scrape_article_links()
    articles = Utils.process_german_articles("Tagesspiegel","de",links,scrape_tagesspiegel_article, check_article_existence)
    return articles