import feedparser
import requests
import json
from newspaper import Article
from datetime import datetime, timezone
from constants import RSS, Article_object, Categories, Utils


def get_yahoonews_articles(limit=None):
	# creating a list of URLs fetched from RSS using feedparser
	RSS_URL = RSS.yahoonews_rss
	feed = feedparser.parse(RSS_URL)
	urls = [e.link for e in feed.entries if "finance" not in e.link and "video" not in e.link] # we already have finance.yahoo, this rss feed also sometimes includes that
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
	n_unsuccesfull = 0
	for i, url in enumerate(urls, start=1):
		try:
			article = Article(url)
			article.download()
			article.parse()

			title = article.title
			body = article.text
			published_at = article.publish_date.isoformat() + "Z" if article.publish_date else None
			clean_str = published_at.rstrip('Z')
			dt = datetime.fromisoformat(clean_str)
			published_date = str(dt.astimezone(timezone.utc))
			published_date = (published_date.split(' ')[0]+'T'+published_date.split(' ')[1]).replace('+00:00','Z')
			# find category from url
			category = Categories.get_category(url)
			article_json = {
				"id": url,
				"title": title,
				"body": body,
				"language": "en",
				"source": "YahooNews",
				"published_at": published_at,
				"category": category
			}
			missing_fields = [key for key, value in article_json.items() if value is None]
			if missing_fields:
				n_unsuccesfull += 1
				failed_articles.append(f"{missing_fields} missing in {url} \n")
			else:
				parsed_articles.append(article_json)
				
		except Exception as e:
			print(f"Exception: {e} in:{url}")
			n_unsuccesfull+=1
			failed_articles.append(f"{url} \n")
	Utils.failure_report(len(urls), n_unsuccesfull, "YahooNews",failed_articles)
	return parsed_articles