import feedparser
import requests
import json
from newspaper import Article
from datetime import datetime
from constants import RSS, Article_object, Categories
import re  # To extract the final URL from Google News

def extract_jakarta_post_url(google_news_url):
	# Extract the Jakarta Post article URL from Google News link
	match = re.search(r"articles/([A-Za-z0-9\-]+)\?oc=[0-9]+", google_news_url)
	if match:
		# Construct the Jakarta Post article URL
		article_id = match.group(1)
		return f"https://thejakartapost.com/article/{article_id}"
	return None  # Return None if URL cannot be extracted

def get_jakartapost_articles(limit=2):
	# Create a list of URLs fetched from RSS using feedparser
	RSS_URL = RSS.jakartapost_rss
	feed = feedparser.parse(RSS_URL)
	urls = [e.link for e in feed.entries]
	urls = urls[:limit]

	print(RSS_URL)
	print("Original Google URLs:")
	print(urls)

	# Convert Google URLs to Jakarta Post URLs
	jakarta_urls = [extract_jakarta_post_url(url) for url in urls if extract_jakarta_post_url(url)]
	
	print("Converted Jakarta Post URLs:")
	print(jakarta_urls)

	# Fetching the HTML using requests and following redirects (you can do this later)
	final_urls = []
	for url in jakarta_urls:
		try:
			# Add logic for fetching article content here if needed
			final_urls.append(url)
		except Exception as e:
			print(f"Error fetching URL: {url}, Error: {e}")
			continue

	# Parsing the articles using newspaper (you can do this later)
	parsed_articles = []
	for i, url in enumerate(final_urls, start=1):
		try:
			article = Article(url)
			article.download()
			article.parse()

			title = article.title
			body = article.text
			published_at = article.publish_date.isoformat() + "Z" if article.publish_date else None

			# Find category from URL
			category = Categories.get_category(url)
			article_json = {
				"id": url,
				"title": title,
				"body": body,
				"language": "en",
				"source": "The Jakarta Post",
				"published_at": published_at,
				"category": category
			}
			parsed_articles.append(article_json)

		except Exception as e:
			print(f"Error parsing article from {url}: {e}")
			continue

	return parsed_articles
