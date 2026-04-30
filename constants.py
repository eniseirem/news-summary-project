from datetime import datetime
from zoneinfo import ZoneInfo
import feedparser

class Article_object:
	def __init__(self, url, source, title, body, language, published_at, category):
		self.url = url
		self.source = source
		self.title = title
		self.body = body
		self.language = language
		self.published_at = published_at
		self.category = category
	
	def create_json_item(self):
		return {
			'id':self.url,
			'title':self.title,
			'body':self.body,
			'language':self.language,
			'source':self.source,
			'published_at':self.published_at, 
			'category':self.category
		}

class RSS():
	bbc_rss = "https://feeds.bbci.co.uk/news/rss.xml"
	ny_rss = "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml"
	bild_rss = "https://www.bild.de/feed/alles.xml"
	foxnews_rss = "https://moxie.foxnews.com/google-publisher/world.xml"
	yahoofinance_rss = "https://finance.yahoo.com/news/rssindex" 
	espn_rss = "https://www.espn.com/espn/rss/news"
	guardiansport_rss = "https://www.theguardian.com/uk/sport/rss"
	guardian_rss = "https://www.theguardian.com/international/rss"
	nbc_rss = "https://feeds.nbcnews.com/nbcnews/public/news"
	yahoonews_rss = "http://rss.news.yahoo.com/rss/topstories"
	thenews_rss = "https://feeds.feedburner.com/com/Yeor"
	cnn_rss = "http://rss.cnn.com/rss/cnn_topstories.rss"
	chinadaily_rss = "http://www.chinadaily.com.cn/rss/world_rss.xml"
	japantimes_rss = "https://www.japantimes.co.jp/feed/topstories/"
	sbs_rss = "https://www.sbs.com.au/news/feed"
	spiegel_rss = "https://www.spiegel.de/schlagzeilen/index.rss"
	welt_rss = "https://www.welt.de/feeds/topnews.rss"
	ntv_rss = "https://www.n-tv.de/politik/rss"
	stern_rss = "http://www.stern.de/feed/standard/all/"
	faz_rss = "https://www.faz.net/rss/aktuell/"
	focus_rss = "https://www.focus.de/politik/rss"
	rss_feeds = [("BBC", bbc_rss)]

class Categories():
	categories = [
		"politics",
		"economics",
		"sports",
		"culture",
		"health",
		"us-news",
		"business",
		"arts",
		"innovation",
		"earth",
		"science",
		"lifestyle",
		"media",
		"world"
	]

	def get_category(url):
		url = url.lower()

		for cat in Categories.categories:
			if f"/{cat}/" in url:
				return cat
		
		# ""edgecases""
		if "sport" in url:
			return "sports"
		if "international" in url:
			return "world"	
		
		return "none"

class Kategorien():
	# deutsche URL-Stichworte into englische JSON-Kategorie
	mapping = {
		"politik": "politics",
		"wirtschaft": "economics",
		"sport": "sports",
		"kultur": "culture",
		"gesundheit": "health",
		"gesellschaft": "lifestyle",
		"medien": "media",
		"wissen": "science",
		"technik": "innovation",
		"umwelt": "earth",
		"klima": "earth",
		"welt": "world",
		"international": "world",
		"reise": "lifestyle",
		"leben": "lifestyle",
		"karriere": "business",
		"finanzen": "business"
	}

	def get_category(url):
		url = url.lower()

		for de, en in Kategorien.mapping.items():
			if f"/{de}/" in url or de in url:
				return en

		return "none"

class Static_values():
	tagesspiegel_data_privacy ="Empfohlener redaktioneller InhaltAn dieser Stelle finden Sie einen von unseren Redakteuren ausgew\u00e4hlten, externen Inhalt, der den Artikel f\u00fcr Sie mit zus\u00e4tzlichen Informationen anreichert. Sie k\u00f6nnen sich hier den externen Inhalt mit einem Klick anzeigen lassen oder wieder ausblenden.Ich bin damit einverstanden, dass mir der externe Inhalt angezeigt wird. Damit k\u00f6nnen personenbezogene Daten an Drittplattformen \u00fcbermittelt werden.  Mehr Informationen dazu erhalten Sie in den Datenschutz-Einstellungen. Diese finden Sie ganz unten auf unserer Seite im Footer, sodass Sie Ihre Einstellungen jederzeit verwalten oder widerrufen k\u00f6nnen."
	spiegel_paywall = "Diesen Artikel weiterlesen mit SPIEGEL+Sie haben bereits ein Digital-Abo?Zum LoginSPIEGEL plusNur für Neukunden€ 1,– für 4 Wochendanach € 5,99 pro WocheFreier Zugriff auf alle S+-Artikel auf SPIEGEL.de und in der AppWöchentlich die digitale Ausgabe des SPIEGEL inkl. E-Paper (PDF), Digital-Archiv und S+-NewsletterJederzeit kündigenJetzt abonnierenSPIEGEL plus52 Wochen 25 % sparen€ 4,49 pro Woche für 52 Wochendanach € 5,99 pro WocheFreier Zugriff auf alle S+-Artikel auf SPIEGEL.de und in der AppWöchentlich die digitale Ausgabe des SPIEGEL inkl. E-Paper (PDF), Digital-Archiv und S+-Newsletter52 Wochen rabattierte LaufzeitJetzt abonnierenSie haben bereits ein Print-Abo?Hier rabattiert Digital-Zugang bestellenJetzt Artikel freischalten:Sie haben bereits ein Digital-Abo?Zum LoginSPIEGEL plusMonatsabo Preis wird geladen...Zugang zu allen Artikeln in der App und auf SPIEGEL.deWöchentliche Ausgabe des SPIEGEL als E-PaperJederzeit kündbarJetzt abonnierenSPIEGEL plus20 % sparenJahresabo Preis wird geladenZugang zu allen Artikeln in der App und auf SPIEGEL.deWöchentliche Ausgabe des SPIEGEL als E-PaperJederzeit kündbarJetzt abonniereniTunes-Abo wiederherstellenSPIEGEL+ wird über Ihren iTunes-Account abgewickelt und mit Kaufbestätigung bezahlt. 24 Stunden vor Ablauf verlängert sich das Abo automatisch umeinen Monat zum Preis von zurzeit¤ein Jahr zum Preis von zurzeit¤. In den Einstellungen Ihres iTunes-Accounts können Sie das Abo jederzeit kündigen. Um SPIEGEL+ außerhalb\ndieser App zu nutzen, müssen Sie das Abo direkt nach dem Kauf mit einem SPIEGEL-ID-Konto verknüpfen. Mit dem Kauf akzeptieren Sie unsereAllgemeinen GeschäftsbedingungenundDatenschutzerklärung."
	foxnews_unrelevant_content = ["CLICK HERE TO DOWNLOAD THE FOX NEWS APP",]
	encoding_artifacts = {
		'â€s':"'",
		"â€™":"'",
		"â€”":"-",
	}
	headers = {
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
		"Accept-Language": "en-US,en;q=0.9",
		"Referer": "https://www.google.com/"
	}
	months = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
	goal_url = "https://www.goal.com/en"
	journalism_tz_map = {
	"ET": -5,
	"EST": -5,
	"EDT": -4,
	"CT": -6,
	"PT": -8,
	"GMT": 0,
	"BST": 1,
	"CET": 1,
	"CEST": 2,
	"JST": 9,
	"HKT": 8,
}


class Utils():
	def iso_now():
		"""Return current time in ISO 8601 UTC format"""
		return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

	def make_article_id(source: str, url: str, index: int) -> str:
		"""Create deterministic ID based on source + date + index."""
		date_str = datetime.utcnow().strftime("%Y%m%d")
		return f"{source}-{date_str}-{index+1:03d}"

	def clean_text(text: str) -> str:
		return text.strip().replace("\n", " ").replace("  ", " ")
	
	def clean_body(content, artifacts, unrelevants):
		for key,value in artifacts.items():
			content = content.replace(key, value)
		for elem in unrelevants:
			content = content.replace(elem, '')
		return content
	
	def failure_report(n_links,n_succesfull_links, outlet_name, failed_articles):
		time_of_run = datetime.now()
		info = [f"###### Scrape Report for {outlet_name} at {time_of_run} #####\n"]
		info.append(f"Incomplete article crawls: {n_links-(n_links-n_succesfull_links)} \n")
		if n_links-(n_links-n_succesfull_links)!=0:
			info.append("Failed articles: \n")
			for elem in failed_articles:
				info.append(elem)
		with open('scraping_report.txt', 'a') as report:
			report.writelines(info)

	def to_iso8601(year, month, day, hour, minute, tz_str):
		"""
		Converts date/time components and a timezone string into ISO 8601 UTC format.
		"""
		# Map common journalism abbreviations to IANA timezone names
		# This ensures Daylight Saving Time is handled automatically
		tz_map = {
			"ET": "America/New_York",
			"CT": "America/Chicago",
			"MT": "America/Denver",
			"PT": "America/Los_Angeles",
			"GMT": "UTC",
			"BST": "Europe/London",
			"CET": "Europe/Paris",
			"JST": "Asia/Tokyo",
			"HKT": "Asia/Hong_Kong"
		}

		# 1. Resolve the timezone name
		iana_tz = tz_map.get(tz_str.strip().upper(), tz_str.strip())

		try:
			# 2. Create the datetime object in the local timezone
			local_dt = datetime(
				int(year), int(month), int(day), 
				int(hour), int(minute), 
				tzinfo=ZoneInfo(iana_tz)
			)

			# 3. Convert to UTC
			utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

			# 4. Return formatted string (Z indicates UTC)
			return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

		except Exception as e:
			return None
			
	def fetch_article_links(rss_link):
		feed = feedparser.parse(rss_link)
		links = []
		for entry in feed.entries:
			links.append(entry.link)
		return links
	
	def process_articles(outlet_name, language, links, scraper_function, paywall_detecter_function=None, forced_category=None):
		articles = []
		failed_articles = []
		n_unsuccesfull = 0
		counter = 1

		for link in links:
			try:
				if paywall_detecter_function is None or not paywall_detecter_function(link):
					content, published_at, title = scraper_function(link)
					id = link

					# IF CATEGORY PASSED AS STRING: SET AS CATEGORY
					# ELSE: RUN FIND CATEGORY ROUTINE
					if forced_category and isinstance(forced_category, str) and forced_category.strip():
						category = forced_category.strip()
					else:
						category = Categories.get_category(link)

					article = Article_object(id, outlet_name, title, content, language, published_at, category)
					article_json = article.create_json_item()

					missing_fields = [key for key, value in article_json.items() if value is None]
					if missing_fields:
						n_unsuccesfull += 1
						failed_articles.append(f"{missing_fields} missing in {link} \n")
					else:
						articles.append(article_json)

					counter += 1

			except Exception as e:
				n_unsuccesfull += 1
				failed_articles.append(f"Exception: {e} in:{link} \n")

		Utils.failure_report(len(links), n_unsuccesfull, outlet_name, failed_articles)
		return articles


	def process_german_articles(outlet_name,language,links, scraper_function, paywall_detecter_function=None):
		articles = []
		failed_articles = []
		n_unsuccesfull = 0
		counter = 1
		for link in links:
			try:
				if paywall_detecter_function is None or not paywall_detecter_function(link):						
					content,published_at,title = scraper_function(link)
					id=link
					category=Kategorien.get_category(link)
					article = Article_object(id, outlet_name, title, content, language, published_at, category)
					article_json = article.create_json_item()
					missing_fields = [key for key, value in article_json.items() if value is None]
					if missing_fields:
						n_unsuccesfull += 1
						failed_articles.append(f"{missing_fields} missing in {link} \n")
					else:
						articles.append(article_json)
					counter += 1
			except Exception as e:
				n_unsuccesfull+=1
				failed_articles.append(f"Exception: {e} in:{link} \n")
		Utils.failure_report(len(links), n_unsuccesfull, outlet_name,failed_articles)
		return articles
