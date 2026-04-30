import requests
from bs4 import BeautifulSoup
from constants import Article_object, Static_values, RSS, Utils
from datetime import datetime,timezone

def scrape_guardian_sport_article(url):
    dom = requests.get(url)
    soup = BeautifulSoup(dom.text,"html.parser")
    maincontent = soup.find("div", id="maincontent")
    paragraphs = maincontent.find_all("p")
    title = soup.select("h1")
    title = str(title).split('</h1>')[0].split('>')[1]
    publish_at  = soup.find('details', attrs={'data-gu-name': 'dateline'})
    publish_at = publish_at.find("span")
    publish_at = str(publish_at).split('</span>')[0].split(">")[1].split(" ")
    year = int(publish_at[3])
    month = Static_values.months.index(publish_at[2])
    day = int(publish_at[1])
    hour = int(publish_at[4].split('.')[0])
    minute = int(publish_at[4].split('.')[1])
    tz = publish_at[-1]
    publish_date = Utils.to_iso8601(year,month,day,hour,minute,tz)
    content=""
    for p in paragraphs:
        content += p.text.strip()
    return content, publish_date, title

def get_guardiansport_articles(limit = None):
    links = Utils.fetch_article_links(RSS.guardiansport_rss)
    articles = Utils.process_articles(
        "GuardianSport",
        "en",
        links,
        scrape_guardian_sport_article,
        paywall_detecter_function=None,
        forced_category="sports")
    return articles
 

