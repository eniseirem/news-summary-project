import requests
from bs4 import BeautifulSoup
#local import
from constants import Static_values, Utils,  RSS, Kategorien


def scrape_spiegel_article(url):
    article = f"{url}"
    dom = requests.get(article)
    soup = BeautifulSoup(dom.text, "html.parser")
    header = soup.find("header", attrs={'data-area':'intro'})
    title = header.find('h2').get_text(strip=True)
    publish_at = header.find_all('time')[0]['datetime']
    publish_at = publish_at.split(' ')
    publish_at_ISO = publish_at[0]+'T'+publish_at[1]+'Z'
    body = soup.find('div', attrs={'data-area':'body'})
    body_elements = body.find_all('div', attrs={'data-sara-click-el':'body_element'})
    content = ''
    for elem in body_elements:
        content+= elem.get_text(strip=True)
    if content==Static_values.spiegel_paywall:
        return None,None,None
    return content, publish_at_ISO, title

def get_spiegel_articles(limit = None):
    links = Utils.fetch_article_links(RSS.spiegel_rss)
    articles = Utils.process_german_articles(
        "Spiegel",
        "de",
        links,
        scrape_spiegel_article,
        paywall_detecter_function=None)
    return articles
