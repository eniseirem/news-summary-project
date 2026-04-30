import feedparser
import requests
import re
from newspaper import Article
from datetime import datetime, timezone
from constants import RSS, Kategorien, Utils

def get_faz_articles(limit=None):
	RSS_URL = RSS.faz_rss
	feed = feedparser.parse(RSS_URL)
	urls = [e.link for e in feed.entries if "/video" not in e.link][:limit]
	articles_list = []

	for url in urls:
		try:
			article = Article(url)
			article.download()
			article.parse()

			title = article.title
			body = article.text

			published_at = None
			if article.publish_date:
				published_at = article.publish_date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
			else:
				# --- brute force: search for datePublished in raw HTML ---
				match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', article.html)
				if match:
					try:
						dt = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
						published_at = dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
					except Exception:
						published_at = None

			category = Kategorien.get_category(url)
			article_json = {
				"id": url,
				"title": title,
				"body": body,
				"language": "de",
				"source": "Frankfurter Allgemeine",
				"published_at": published_at,
				"category": category
			}
			articles_list.append(article_json)

		except Exception as e:
			print("Failed to parse:", url)
			print("Error:", e)

	return articles_list
