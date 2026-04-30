# Web Crawler

# For N8N

Working endpoints:

English:
- /cnn
- /espn
- /foxnews
- /goal
- /guardian
- /guardiansport
- /japantimes
- /nbc
- /sbs
- /southchinamorningpost/economics
- /southchinamorningpost/politics
- /tass
- /telesur
- /thenews
- /timesofindia
- /yahoofinance
- /yahoonews

German:
- /bild
- /faz
- /focus
- /ntv
- /spiegel
- /stern
- /welt

## Status of (english) Scrapers
- [ ] ABC
- [ ] China Daily
- [x] CNN
- [x] ESPN
- [x] Fox News
- [x] Goal
- [x] Guardian
- [x] Guradian (Sport)
- [ ] The Jakarta Post
- [x] The Japan Times
- [x] NBC
- [ ] News24
- [x] SBS
- [x] South China Morning Post (economics)
- [x] South China Morning Post (politics)
- [x] Tass
- [x] TeleSur
- [x] The News International
- [x] The Times of India
- [x] Yahoo Finance
- [x] Yahoo News

## Status of German Scrapers
- [x] Bild
- [x] FAZ
- [x] FOCUS
- [x] N-TV
- [x] Spiegel
- [x] Stern
- [ ] Tagesspiegel
- [x] Welt

## Current Format

| Field			| Type										| Required		| Description			|
|---------------|-------------------------------------------|---------------|-----------------------|
| `id`			| `string`									| yes			| URL					|
| `title`		| `string`									| yes			| Headline				|
| `body`		| `string`									| yes			| Full article text		|
| `language`	| `string`									| yes			| `en` or `de`			|
| `source`		| `string`									| yes			| Publisher				|
| `published_at`| `string` (ISO8601 date and time in UTC)	| yes			| 2026-01-06T12:23:33Z	|
| `category`	| `string`									| optional		| Category				|

## JSON Example

```json
{
	"id":"https://www.cnn.com/business/live-news/fox-news-dominion-trial-04-18-23/index.html",
	"title":"Settlement reached in Fox vs Dominion lawsuit",
	"body":"Justin Nelson, Dominion's lead counsel, appears on CNN. (CNN)\n\nDominion Voting Systems had two goals in its [...]",
	"language":"en",
	"source":"CNN",
	"published_at":"2023-04-18T15:02:55Z",
	"category":"business"
}
```

## Dependencies
- requests
- bs4
- feedparser
- newspaper3k
- json
- fastapi

## Dependencies for heatmap and testing (not N8N)
- plotly			(only for local heatmap)
- plotly kaleido	(only for local heatmap)
- numpy				(only for local heatmap)
- pandas			(only for local heatmap)
- uvicorn[standard]	(only for testing)

## Amount of scrapers

Working: 24

Total: 30

Per country (working):
| Country	| Amount	|
|-----------|-----------|
| USA		| 7			|
| Germany	| 7			|
| UK		| 2			|
| Japan		| 1			|
| Australia	| 1			|
| China		| 2			|
| Venezuela	| 1			|
| Russia	| 1			|
| India		| 1			|