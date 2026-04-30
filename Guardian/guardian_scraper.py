from constants import RSS, Article_object, Utils, Categories
import feedparser
from newspaper import Article as NPArticle


def clean_text(text: str) -> str:
		return text.strip().replace("\n", " ").replace("  ", " ")


def get_guardian_articles(limit=None):     # ARTICLE AMOUNT LIMIT PER NEWSOUTLET
	results = []

	feed = feedparser.parse(RSS.guardian_rss)

	 # Filter URLs to include only /politics/ or /world/
	 # we can remove this filter once we dont need it anymore. then it will jsut fetch all types of articles
	filtered_entries = [entry for entry in feed.entries if "/politics/" in entry.link or "/world/" in entry.link]

	entries = filtered_entries[:limit]
	failed_articles = []
	n_unsuccesfull = 0
	for idx, entry in enumerate(entries):
		try:
			url = entry.link
			body = ""
			word_count = 0
			try:
				art = NPArticle(url)
				art.download()
				art.parse()
				body = clean_text(art.text)
				word_count = len(body.split())
			except Exception as e:
				print(f"Failed to parse {url}: {e}")

			published_at = ""
			if hasattr(entry, "published_parsed") and entry.published_parsed:
				t = entry.published_parsed
				published_at = f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}Z"
			
			# find category from url
			category = Categories.get_category(url)

			article_json = {
				"id": url,
				"title": clean_text(entry.title),
				"body": body,
				"language": "en",
				"source": "Guardian",
				"published_at": published_at,
				"category": category
			}
			missing_fields = [key for key, value in article_json.items() if value is None]
			if missing_fields:
				n_unsuccesfull += 1
				failed_articles.append(f"{missing_fields} missing in {url} \n")
			else:
				results.append(article_json)

		except Exception as e:
			failed_articles.append(f"Exception: {e} in:{url} \n")
			continue
	Utils.failure_report(len(entries), n_unsuccesfull, "Guardian",failed_articles)
	return results