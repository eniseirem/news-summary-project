import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
# local import
from constants import Article_object, Static_values, Utils, Categories, Kategorien, RSS


def scrape_welt_article(url):
	dom = requests.get(url)
	soup = BeautifulSoup(dom.text, "html.parser")

	title_tag = soup.find("title")
	title = title_tag.get_text(strip=True) if title_tag else None

	now_utc = datetime.now(timezone.utc).replace(microsecond=0)
	publish_at = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')

	body = soup.find('div', attrs={'class':'c-article-page__text'})
	body_elements = body.find_all('p') if body else []

	content = ''
	for elem in body_elements:
		content += elem.get_text(strip=True) + " "

	content = content.strip()

	# HACKY just remove empty body articles
	if not content:
		return None, None, None

	return content, publish_at, title


def check_for_paywall(link):
	dom = requests.get(link)
	soup = BeautifulSoup(dom.text, "html.parser")
	titles = soup.find_all('title')
	if "<title>Weltplus Artikel</title>" in str(titles):
		return None
	return link


def get_welt_articles(limit=None):
	links = Utils.fetch_article_links(RSS.welt_rss)
	articles = Utils.process_german_articles(
		"Welt",
		"de",
		links,
		scrape_welt_article,
		paywall_detecter_function=None
	)
	return articles
