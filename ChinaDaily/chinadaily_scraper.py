from constants import RSS, Article_object, Categories
import feedparser
import requests
from newspaper import Article
import json
from datetime import datetime

def get_chinadaily_articles(limit=None):
	# creating a list of URLs fetched from RSS using feedparser
	RSS_URL = RSS.chinadaily_rss
	feed = feedparser.parse(RSS_URL)
	urls = [e.link for e in feed.entries]
	urls = urls[:limit]

	# fetching the HTML using response
	raw_html = []
	for url in urls:
		response = requests.get(url)
		html_content = response.text
		raw_html.append(html_content)

	# parsing the articles using newspaper
	parsed_articles = []
	SOURCE_NAME = "China Daily"
	LANGUAGE = "en"
	retrieved_at = datetime.utcnow().isoformat() + "Z"



	for i, url in enumerate(urls, start=1):
		try:
			article = Article(url)
			article.download()
			article.parse()

			title = article.title
			body = article.text
			published_at = article.publish_date.isoformat() + "Z" if article.publish_date else None
			word_count = len(body.split())

			# find category from url
			category = Categories.get_category(url)
			print(url, category)

			article_json = {
				"id": url,
				"title": title,
				"body": body,
				"language": LANGUAGE,
				"source:": SOURCE_NAME,
				"published_at": published_at,
				"category": category		# placeholder, ill implement the logic later xd
			}
			
			parsed_articles.append(article_json)

		except Exception as e:
			print("Error in Web-Scraper in ChinaDaily in chinadaily_scraper.py:", e)
			continue

	return parsed_articles