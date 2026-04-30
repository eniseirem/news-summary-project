import feedparser
from newspaper import Article
from constants import Article_object
from datetime import datetime,timezone
import calendar


def fetch_rss_articles(rss_feeds, limit = None):
	articles = []
	for outlet, rss_link in rss_feeds:
		feed = feedparser.parse(rss_link)
		counter = 1
		for entry in feed.entries:
			try:
				if limit and counter>limit:
					break
				url = entry.link
				article = Article(url)
				article.download()
				article.parse()
				content = article.text
				title = article.title
				url = article.url
				now_utc = datetime.now(timezone.utc)
				iso_format = now_utc.isoformat(timespec='seconds')
				retrieved_at = iso_format.replace('+00:00', 'Z')
				if outlet=='BBC':
					publish_data = entry.published_parsed
					timestamp = calendar.timegm(publish_data)
					utc_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
					published_at = utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
					category = "international news"
				else:
					continue
				article_object = Article_object(url, outlet,title,content,'en',published_at,retrieved_at, category)
				article_object = article_object.create_json_item()
				counter+=1
				articles.append(article_object)
			except Exception as e:
				print(e)

	return articles
