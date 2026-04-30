import feedparser
import requests
import json
from newspaper import Article
from datetime import datetime, timezone
from constants import RSS, Article_object, Categories, Utils

def get_cnn_articles(limit=None):
	# creating a list of URLs fetched from RSS using feedparser
	RSS_URL = RSS.cnn_rss
	feed = feedparser.parse(RSS_URL)
	urls = [e.link for e in feed.entries if "/video" not in e.link]
	urls = urls[:limit]

	# fetching the HTML using response
	raw_html = []
	for url in urls:
		response = requests.get(url)
		html_content = response.text
		raw_html.append(html_content)

	# parsing the articles using newspaper
	parsed_articles = []
	failed_articles = []
	n_unsuccesfull= 0
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
				"source": "CNN",
				"published_at": published_at,
				"category": category
			}
			missing_fields = [key for key, value in article_json.items() if value is None]
			if missing_fields:
				n_unsuccesfull += 1
				failed_articles.append(f"{missing_fields} missing in {link} \n")
			else:
				parsed_articles.append(article_json)
			counter += 1

		except Exception as e:
			failed_articles.append(f"Exception: {e} in:{url} \n")
			continue
	Utils.failure_report(len(urls), n_unsuccesfull, "CNN",failed_articles)
	return parsed_articles