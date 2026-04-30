import requests
import datetime
from bs4 import BeautifulSoup
from constants import Article_object, Static_values, Utils, Categories
from datetime import datetime,timezone

def scrape_tass_article(url):
    dom = requests.get(url, headers=Static_values.headers)
    soup = BeautifulSoup(dom.text,"html.parser")
    content_container = soup.find("div", attrs={'data-io-article-url':url})
    paragraphs = content_container.find("div", attrs={'class':'text-content'}).find_all("p")
    title = soup.find("h1", attrs={'class':'news-header__title'}).text
    publish_at = soup.find("div", attrs={'class':'news-header__date'})
    publish_at = publish_at.find("span")
    publish_at = publish_at.find("dateformat")
    timevalue = publish_at['time']
    dt_object_utc = str(datetime.fromtimestamp(int(timevalue), tz=timezone.utc))
    publish_date = dt_object_utc.replace('+00:00','Z')
    publish_date = publish_date.split(' ')[0]+'T'+publish_date.split(' ')[1]
    content = ""
    for p in paragraphs:
        content += p.text.strip()
    return content, publish_date, title

def get_all_links():
    homepage = "https://tass.com"
    dom = requests.get(homepage, headers=Static_values.headers)
    soup = BeautifulSoup(dom.text,"html.parser")
    topstories = soup.find("div", attrs={"class":"main-news__top-news"})
    top_stories_links = topstories.find_all("a")
    top_stories_links = [homepage+link['href'] for link in top_stories_links]
    news = soup.find("div", attrs={'class':'news-list'})
    news_links = news.find_all("a")
    news_links = [homepage+link['href'] for link in news_links]
    return top_stories_links+news_links
    

def get_tass_articles(limit = None):
    links = get_all_links()
    articles = Utils.process_articles("Tass","en",links,scrape_tass_article, paywall_detecter_function=None)
    return articles