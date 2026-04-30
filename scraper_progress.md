# Status of Scrapers

### ABC
Language: English  
Country: Australia
- [x] returns articles
- [x] uses current JSON-format
- [ ] uses ISO-time
- [x] has categories

### Bild
Language: German  
Country: Germany
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [] has categories

### China Daily
Language: English  
Country: China
- [ ] returns articles
- [ ] uses current JSON-format
- [ ] uses ISO-time
- [ ] has categories

### CNN
Language: English  
Country:USA
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### ESPN
Language: English  
Country: USA
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### Fox News
Language: English  
Country: USA
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### Goal
Language: English  
Country: United Kingdom
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### Guardian
Language: English  
Country: United Kingdom
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### Guardian (Sport)
Language: English  
Country: United Kingdom
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### The Jakarta Post
403 error -> bot detection  
Language: English  
Country: Indonesia
- [ ] returns articles
- [ ] uses current JSON-format
- [ ] uses ISO-time
- [ ] has categories

### The Japan Times
Language: English  
Country: Japan
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### NBC
Language: English  
Country: USA
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### News24
Language: English  
Country: South Africa
- [ ] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### SBS
Language: English  
Country: Australia
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [ ] has categories

### Spiegel
Language: Germman  
Country: Germany 
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### South China Morning Post (economics)
Language: English  
Country: China
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### South China Morning Post (politics)
Language: English  
Country: China
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### Tagesspiegel
Language: German  
Country: Germany
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [] has categories

### Tass
Language: English  
Country: Russia
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### TeleSur
Language: English  
Country: Venezuela
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### The News International
Language: English  
Country: Pakistan
- [ ] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### The Times of India
Language: English  
Country: India
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### Welt
Language: German  
Country: Germany
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### Yahoo Finance
Language: English  
Country: USA
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

### Yahoo News
Language: English  
Country: USA
- [x] returns articles
- [x] uses current JSON-format
- [x] uses ISO-time
- [x] has categories

## some internal stuff

### ```get_category(url)```

```get_category(url)``` is in the ```constants.py``` file and can be used like this: ```category = Categories.get_category(url)```  
Then we can just add the category to the json. This version only searches for the category in the URL, not in the meta data. Remember to import the file using ```from constants import Categories```