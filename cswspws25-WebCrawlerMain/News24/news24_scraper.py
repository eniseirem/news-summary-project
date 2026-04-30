import feedparser
import requests
import json
from newspaper import Article
from datetime import datetime, timezone
from constants import RSS, Article_object, Categories

def get_news24_articles(limit=None):
	# creating a list of URLs fetched from RSS using feedparser
	RSS_URL = RSS.news24_rss
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
	for i, url in enumerate(urls, start=1):
		try:
			article = Article(url)
			article.download()
			article.parse()

			title = article.title
			body = article.text

			# use proper iso 8601 date and time in UTC instead of iso 8601 date and time with offset
			if article.publish_date:
				published_at = article.publish_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
			else:
				published_at = None

			# find category from url
			category = Categories.get_category(url)
			article_json = {
				"id": url,
				"title": title,
				"body": body,
				"language": "en",
				"source": "News24",
				"published_at": published_at,
				"category": category
			}
			parsed_articles.append(article_json)

		except Exception as e:
			print("Error in Web-Scraper in News24 in news24_scraper.py:", e)
			continue

	return parsed_articles