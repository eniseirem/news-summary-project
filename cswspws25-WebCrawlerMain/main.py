import json, time, datetime
from fastapi import FastAPI

# from Tagesspiegel.tagesspiegel_scraping import get_all_articles_content
# from Bild.bild_scraping import get_bild_articles 
from FoxNews.foxnews_scraper import get_foxnews_articles
from Bild.bild_scraping import get_bild_articles
from YahooFinance.yahoofincance_scraper import get_yahoofinance_articles
from ESPN.espn_scraper import get_espn_articles
from GuardianSport.guardian_sport_scraper import get_guardiansport_articles
from Goal.goal_scraper import get_goal_articles
from RSS.rss_fetching import fetch_rss_articles
from Guardian.guardian_scraper import get_guardian_articles
from NBC.nbc_scraper import get_nbc_articles
from YahooNews.yahoonews_scraper import get_yahoonews_articles
from CNN.cnn_scraper import get_cnn_articles
from ChinaDaily.chinadaily_scraper import get_chinadaily_articles
from SouthChinaMorningPost.scmp_china_politics_scraper import get_scmp_pol_articles
from SouthChinaMorningPost.scmp_china_economics_scraper import get_scmp_econ_articles
from TeleSur.telesur_scraper import get_telesur_articles
from ABC.abc_scraper import get_abc_articles
from News24.news24_scraper import get_news24_articles
from JapanTimes.japantimes_scraper import get_japantimes_articles
from TimesOfIndia.timesofindia_scraper import get_timesofindia_articles
from JakartaPost.jakartapost_scraper import get_jakartapost_articles
from TheNews.thenews_scraper import get_thenews_articles
from Tagesspiegel.tagesspiegel_scraping import get_all_articles_content
from Tass.tass_scraper import get_tass_articles
from YahooNews.yahoonews_scraper import get_yahoonews_articles
from TimesOfIndia.timesofindia_scraper import get_timesofindia_articles
from TheNews.thenews_scraper import get_thenews_articles
from SBS.sbs_scraper import get_sbs_articles
from Spiegel.spiegel_scraper import get_spiegel_articles
from Welt.welt_scraper import get_welt_articles
from NTV.ntv_scraper import get_ntv_articles
from Stern.stern_scraper import get_stern_articles
from FAZ.faz_scraper import get_faz_articles
from FOCUS.focus_scraper import get_focus_articles
from constants import RSS, Static_values



################################ API ################################
#
#	for testing
#
#	terminal:	uvicorn main:app --reload
#	browser:	127.0.0.1:8000/news_outlet_name
#


"""
not working scrapers are commented, we will un-comment them once they're running
"""

app = FastAPI()

@app.get("/")
def up():
	return "up"

@app.get("/health")
def health():
	return "up"

# has no published at
# @app.get("/abc")
# def abc():
# 	articles = get_abc_articles()
# 	return articles

# not functional
# @app.get("/chinadaily")
# def chinadaily():
# 	articles = get_chinadaily_articles(Static_values.chinadaily_url)
# 	return articles

@app.get("/bild")
def bild():
	articles = get_bild_articles()
	return articles

@app.get("/cnn")
def cnn():
	articles = get_cnn_articles()
	return articles

@app.get("/espn")
def espn():
	articles = get_espn_articles()
	return articles

@app.get("/faz")
def faz():
	articles = get_faz_articles()
	return articles

@app.get("/focus")
def focus():
	articles = get_focus_articles()
	return articles

@app.get("/foxnews")
def foxnews():
	articles = get_foxnews_articles()
	return articles

@app.get("/goal")
def goal():
	articles = get_goal_articles()
	return articles

@app.get("/guardian")
def guardian():
	articles = get_guardian_articles()
	return articles

@app.get("/guardiansport")
def guardiansport():
	articles = get_guardiansport_articles()
	return articles

# not functional
# @app.get("/jakartapost")
# def jakartapost():
# 	articles = get_jakartapost_articles()
# 	return articles

@app.get("/japantimes")
def japantimes():
	articles = get_japantimes_articles()
	return articles

@app.get("/nbc")
def nbc():
	articles = get_nbc_articles()
	return articles

# error 403 -> bot detection
# @app.get("/news24")
# def news24():
# 	articles = get_news24_articles()
# 	return articles

@app.get("/sbs")
def sbs():
	articles = get_sbs_articles()
	return articles

@app.get("/spiegel")
def spiegel():
	articles = get_spiegel_articles()
	return articles

@app.get("/southchinamorningpost/economics")
def scmp_politics():
	articles = get_scmp_econ_articles()
	return articles

@app.get("/southchinamorningpost/politics")
def scmp_politics():
	articles = get_scmp_pol_articles()
	return articles

@app.get("/stern")
def stern():
	articles = get_stern_articles()
	return articles

@app.get("/ntv")
def ntv():
	articles = get_ntv_articles()
	return articles

@app.get("/tagesspiegel")
def tagesspiegel():
	articles = get_all_articles_content()
	return articles

@app.get("/tass")
def tass():
	articles = get_tass_articles()
	return articles

@app.get("/telesur")
def telesur():
	articles = get_telesur_articles()
	return articles

@app.get("/thenews")
def rss():
	articles = get_thenews_articles()
	return articles

@app.get("/timesofindia")
def timesofindia():
	articles = get_timesofindia_articles()
	return articles

@app.get("/welt")
def faz():
	articles = get_welt_articles()
	return articles

@app.get("/yahoofinance")
def yahoofinance():
	articles = get_yahoofinance_articles()
	return articles

@app.get("/yahoonews")
def yahoonews():
	articles = get_yahoonews_articles()
	return articles

@app.get("/rss")
def rss():
	articles = fetch_rss_articles(RSS.rss_feeds)
	return articles


# helper in case we want to limit body
def limit_chars(articles):
	for article in articles:
		article['body']= article['body'][:3000]
	return articles

# this function is only for testing purposes, it is not used in n8n
def generate_json():
	articles = []
	limit_amount = 50

	# print("ABC")
	# abc_articles = get_abc_articles()
	# articles += abc_articles

	# print("China Daily")
	# chinadaily_articles = get_chinadaily_articles()
	# articles += chinadaily_articles

	print("CNN")
	cnn_articles = get_cnn_articles(limit = limit_amount)
	articles += cnn_articles

	print("ESPN")
	espn_articles = get_espn_articles(limit = limit_amount)
	articles += espn_articles

	print("Fox News")
	foxnews_articles = get_foxnews_articles(limit = limit_amount)
	articles += foxnews_articles

	print("Goal")
	goal_articles = get_goal_articles()
	articles += goal_articles

	print("Guardian")
	guardian_articles = get_guardian_articles(limit = limit_amount)
	articles += guardian_articles

	print("Guardian Sport")
	guardiansport_articles = get_guardiansport_articles(limit = limit_amount)
	articles += guardiansport_articles

	# print("The Jakarta Post")
	# jakartapost_articles = get_jakartapost_articles()
	# articles += jakartapost_articles

	print("The Japan Times")
	japantimes_articles = get_japantimes_articles(limit = limit_amount)
	articles += japantimes_articles

	print("NBC")
	nbc_articles = get_nbc_articles(limit = limit_amount)
	articles += nbc_articles

	# print("News24")
	# news24_articles = get_news24_articles()
	# articles += news24_articles

	print("SBS")
	sbs_articles = get_sbs_articles(limit = limit_amount)
	articles += sbs_articles

	print("SCMP Economics")
	scmp_econ_articles = get_scmp_econ_articles(limit = limit_amount)
	articles += scmp_econ_articles

	# merge conflict not resolved
	print("SCMP Politics")
	scmp_pol_articles = get_scmp_pol_articles(limit = limit_amount)
	articles += scmp_pol_articles

	print("Tass")
	tass_articles = get_tass_articles(limit = limit_amount)
	articles += tass_articles

	print("TeleSur")
	telesur_articles = get_telesur_articles(limit = limit_amount)
	articles += telesur_articles
	
	print("The News")
	thenews_articles = get_thenews_articles()
	articles += thenews_articles

	print("Times of India")
	timesofindia_articles = get_timesofindia_articles(limit = limit_amount)
	articles += timesofindia_articles

	print("Yahoo Finance")
	yahoofinance_articles = get_yahoofinance_articles(limit = limit_amount)
	articles += yahoofinance_articles

	print("Yahoo News")
	yahoonews_articles = get_yahoonews_articles(limit = limit_amount)
	articles += yahoonews_articles



	print("Bild")
	bild_articles = get_bild_articles(limit = limit_amount)
	articles += bild_articles

	print("N-TV")
	ntv_articles = get_ntv_articles(limit = limit_amount)
	articles += ntv_articles

	print("Spiegel")
	spiegel_articles = get_spiegel_articles(limit = limit_amount)
	articles += spiegel_articles

	print("Stern")
	stern_articles = get_stern_articles(limit = limit_amount)
	articles += stern_articles

	print("Welt")
	welt_articles = get_welt_articles(limit = limit_amount)
	articles += welt_articles

	with open('articles.json','w') as f:
		json.dump(articles, f, ensure_ascii=False, indent=4)
		print("written to articles.json")


# uncomment this line to generate a json
# generate_json()