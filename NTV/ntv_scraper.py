import feedparser
import requests
import re
from newspaper import Article
from datetime import datetime, timezone
from constants import RSS, Kategorien, Utils

def get_ntv_articles(limit=None):
	RSS_URL = RSS.ntv_rss
	feed = feedparser.parse(RSS_URL)
	urls = [e.link for e in feed.entries if "/video" not in e.link][:limit]

	articles = []

	for url in urls:
		try:
			response = requests.get(url, timeout=10)
			response.raise_for_status()
			html = response.text

			article = Article(url)
			article.set_html(html)
			article.parse()

			title = article.title
			body = article.text

			# --- brute force datePublished → UTC ISO ---
			published_at = None
			match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)

			if match:
				raw_date = match.group(1)               # 2026-01-29T13:13:24+01:00
				dt = datetime.fromisoformat(raw_date)   # aware datetime
				dt = dt.astimezone(timezone.utc)        # convert to UTC
				published_at = dt.isoformat().replace("+00:00", "Z")

			# find category from url
			category = Kategorien.get_category(url)
			article_json = {
				"id": url,
				"title": title,
				"body": body,
				"language": "de",
				"source": "N-TV",
				"published_at": published_at,
				"category": category
			}

			articles.append(article_json)

		except Exception as e:
			print(f"FAILED: {url} ({e})")

	return articles
