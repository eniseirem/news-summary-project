import feedparser
from newspaper import Article
from constants import RSS, Kategorien
import re

def get_focus_articles(limit=150):
	RSS_URL = RSS.focus_rss
	feed = feedparser.parse(RSS_URL)
	
	urls = [e.link for e in feed.entries][:limit]
	articles_list = []

	print(urls)

	for url in urls:
		article = Article(url, language="de")
		article.download()
		article.parse()

		title = article.title
		body = article.text

		# Brute-force Suche nach pagePublishDateTimeUtc im HTML
		match = re.search(r'"pagePublishDateTimeUtc"\s*:\s*"([^"]+)"', article.html)
		if match:
			published_at = match.group(1)
		else:
			published_at = None

		# Kategorie via bestehendem Modul
		category = Kategorien.get_category(url)

		article_json = {
			"id": url,
			"title": title,
			"body": body,
			"language": "de",
			"source": "FOCUS",
			"published_at": published_at,
			"category": category
		}

		print(article_json)

		articles_list.append(article_json)

	return articles_list
