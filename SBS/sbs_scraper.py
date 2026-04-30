import feedparser
import requests
from newspaper import Article
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from constants import RSS, Categories, Utils

def get_sbs_articles(limit=None):
    RSS_URL = RSS.sbs_rss
    feed = feedparser.parse(RSS_URL)
    urls = [e.link for e in feed.entries][:limit]

    parsed_articles = []
    failed_articles = []
    n_unsuccesfull = 0
    for url in urls:
        try:
            # fetch html
            response = requests.get(url)
            html_content = response.text

            # parse article with newspaper
            article = Article(url)
            article.download()
            article.parse()

            title = article.title
            body = article.text

            # parse published date from <p data-testid="publishedDate">
            soup = BeautifulSoup(html_content, "html.parser")
            published_at = None
            date_p_tag = soup.find("p", {"data-testid": "publishedDate"})
            if date_p_tag:
                time_tags = date_p_tag.find_all("time")
                if time_tags:
                    date_str = time_tags[0].get("datetime")  # "2026-01-05"
                    if len(time_tags) > 1:
                        time_str = time_tags[1].get("datetime")  # "05:34"
                        dt = datetime.fromisoformat(f"{date_str}T{time_str}")
                    else:
                        dt = datetime.fromisoformat(f"{date_str}T00:00:00")
                    published_at = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            # find category from url
            category = Categories.get_category(url)
            article_json = {
                "id": url,
                "title": title,
                "body": body,
                "language": "en",
                "source": "SBS",
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
            failed_articles.append(f"Exception: {e} in:{url} \n")
            continue
    Utils.failure_report(len(urls), n_unsuccesfull, "SBS",failed_articles)
    return parsed_articles
