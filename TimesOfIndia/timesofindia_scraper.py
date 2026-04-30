import feedparser
import requests
import json
from newspaper import Article
from constants import RSS, Article_object, Categories, Static_values, Utils
from bs4 import BeautifulSoup
from datetime import datetime, timezone


def get_rss_feed():
	homepage = "https://timesofindia.indiatimes.com/rss.cms"
	dom = requests.get(homepage, headers=Static_values.headers)
	soup = BeautifulSoup(dom.text, "html.parser")
	trs = soup.find_all("tr")
	for tr in trs:
		link = tr.find("a", string="India")
		if link and 'rssfeeds' in link['href']:
			return link['href']


# fallback date extractor for Times of India
def extract_date_from_html(html):
	soup = BeautifulSoup(html, "html.parser")
	scripts = soup.find_all("script", type="application/ld+json")

	for script in scripts:
		try:
			data = json.loads(script.string)
		except Exception:
			continue

		if isinstance(data, list):
			for item in data:
				date = item.get("datePublished") or item.get("dateCreated")
				if date:
					return normalize_date(date)

		elif isinstance(data, dict):
			date = data.get("datePublished") or data.get("dateCreated")
			if date:
				return normalize_date(date)

	return None


def normalize_date(date_str):
	dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
	return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def get_timesofindia_articles(limit=None):
	RSS_URL = get_rss_feed()
	feed = feedparser.parse(RSS_URL)
	urls = [e.link for e in feed.entries]
	urls = urls[:limit]

	raw_html = []
	for url in urls:
		response = requests.get(url, headers=Static_values.headers)
		raw_html.append(response.text)

	parsed_articles = []
	failed_articles = []
	n_unsuccesfull = 0

	for i, url in enumerate(urls):
		try:
			article = Article(url)
			article.download()
			article.parse()

			title = article.title
			body = article.text

			# hacky fix because sometimes body == title, so if body == title: skip article
			# TODO: logging for that case (anh bitte mach du)
			# also: if body == "tired of too many ads?" skip article
			if not body or body.strip() == "" or body.strip() == title.strip() \
			   or body.strip().lower() == "tired of too many ads?":
				continue

			# primary: newspaper
			if article.publish_date:
				published_date = article.publish_date.astimezone(timezone.utc) \
					.isoformat().replace("+00:00", "Z")
			else:
				# fallback: JSON-LD
				published_date = extract_date_from_html(raw_html[i])

			category = Categories.get_category(url)

			article_json = {
				"id": url,
				"title": title,
				"body": body,
				"language": "en",
				"source": "The Times of India",
				"published_at": published_date,
				"category": "world"
			}

			missing_fields = [key for key, value in article_json.items() if value is None]
			if missing_fields:
				n_unsuccesfull += 1
				failed_articles.append(f"{missing_fields} missing in {url} \n")
			else:
				parsed_articles.append(article_json)
				
		except Exception as e:
			print(f"Exception: {e} in:{url}")
			n_unsuccesfull += 1
			failed_articles.append(f"{url}\n")

	Utils.failure_report(len(urls), n_unsuccesfull, "Times of India", failed_articles)
	return parsed_articles