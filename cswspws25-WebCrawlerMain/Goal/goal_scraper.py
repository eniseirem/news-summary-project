import requests
from bs4 import BeautifulSoup
from constants import Static_values, Utils, RSS


def get_article_links(url):
    links = [] 
    dom = requests.get(url, headers=Static_values.headers)
    soup = BeautifulSoup(dom.text,"html.parser")
    content = soup.find("section", attrs= {'card-group-type':"TOP_STORIES"})
    articles = content.find_all("li", attrs={'data-type':'CardComponent'})
    for article in articles:
        href = article.select("article")[0].find("div").find('a')['href']
        if href:
            link = url+str(href)
            links.append(link)
    return links

def scrape_goal_article(link):
    dom = requests.get(link)
    soup = BeautifulSoup(dom.text,"html.parser")
    try:
        title = soup.find("h1", attrs={'data-testid':'article-title'})
        title = str(title).split('</h1>')[0].split('>')[1]
        main_content = soup.find("div", attrs={'data-testid':'article-body'})
        ul = soup.find("ul", attrs={'aria-label':'List'})
        if ul:
            li_elems = ul.find_all('li',attrs={'aria-label':'Standard Slide'})
        paragraphs = main_content.find_all("p")
        content = ""
        for p in paragraphs:
            content+=p.text.strip()
        if ul and li_elems:
            for li in li_elems:
                paragraphs = li.find_all("p")
                for p in paragraphs:
                    content+=p.text.strip()
        publish_at = soup.find("time", attrs={'data-testid':'publish-time'})['datetime']
        publish_at = publish_at.replace('.000','')
    except Exception as e:
        print(f"exception in scrape-article: {e}")
        return None, None, None
    return content, publish_at, title

def get_goal_articles():
    links = get_article_links(Static_values.goal_url)
    articles = Utils.process_articles(
        "Goal",
        "en",
        links,
        scrape_goal_article,
        paywall_detecter_function=None,
        forced_category="sports")
    return articles

        

