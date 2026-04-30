import json
from collections import Counter
import plotly.express as px
import kaleido
kaleido.get_chrome_sync()

json_file = "articles.json"
with open(json_file, "r") as f:
	articles = json.load(f)

source_to_country = {
	# US
	"CNN": "USA",
	"ESPN": "USA",
	"Fox News": "USA",
	"Goal": "USA",
	"YahooFinance": "USA",
	"YahooNews": "USA",
	"The News": "USA",

	# UK
	"Guardian": "UK",
	"Guardian Sport": "UK",
	"The Times of India": "India",

	# Japan
	"The Japan Times": "Japan",

	# Australia
	"NBC": "Australia",
	"SBS": "Australia",

	# China
	"South China Morning Post Economics": "China",
	"South China Morning Post Politics": "China",

	# Russia
	"Tass": "Russia",

	# Venezuela
	"Telesur": "Venezuela",

	# Germany
	"Bild": "Germany",
	"n-tv": "Germany",
	"Spiegel": "Germany",
	"Stern": "Germany",
	"Welt": "Germany"
}

countries = []
for article in articles:
	source = article.get("source")
	country = source_to_country.get(source)
	if country:
		countries.append(country)

country_counts = Counter(countries)

data = {
	"country": list(country_counts.keys()),
	"count": list(country_counts.values())
}

fig = px.scatter_geo(
	data,
	locations="country",
	locationmode="country names",
	size="count",
	projection="natural earth",
	title="Article Counts by Country",
	size_max=50,
	text="count"
)

fig.update_traces(
	mode="markers+text",
	texttemplate="%{text}",
	textposition="middle center",
	textfont=dict(
		size=16,           # larger font
		color="black",     # text color
		family="Arial Black"  # heavy/bold font
	),
	hovertemplate=(
		"<b>%{location}</b><br>"
		
		"Articles: %{text}<extra></extra>"
	)
)

# ===== CHOOSE EITHER BROWSER OR PDF =====

# ==== BROWSER ====
# fig.show()

# ==== PDF ====
fig.write_image("articles_heatmap.pdf", format="pdf")
print("PDF saved as articles_heatmap.pdf")
