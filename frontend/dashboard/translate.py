# DICTIONARY FOR UI TRANSLATIONS
TRANSLATIONS = {
    # General UI
    "title": {"EN": "News Clustering Dashboard", "DE": "Nachrichten-Cluster Dashboard"},
    "loading_cats": {"EN": "Loading categories...", "DE": "Lade Kategorien..."},
    "header_settings": {"EN": "Search Settings", "DE": "Such-Einstellungen"},
    "lbl_language": {"EN": "Language / Sprache", "DE": "Sprache / Language"},
    "lbl_category": {"EN": "Select Category", "DE": "Kategorie wählen"},
    "lbl_subcategory": {"EN": "Select Subcategory (Optional)", "DE": "Unterkategorie wählen (Optional)"},
    "lbl_keywords": {"EN": "Keywords", "DE": "Schlüsselwörter"},
    "lbl_timewindow": {"EN": "Time Window", "DE": "Zeitfenster"},
    "btn_generate": {"EN": "Generate Summary", "DE": "Zusammenfassung erstellen"},
    "lbl_global_overview":{"EN": "Global overview of all clusters in this category:", "DE":"Globale Übersicht aller Cluster in dieser Kategorie:"},
    "header_browse": {"EN": "Browse Clusters", "DE": "Cluster durchsuchen"},
    "info_clusters_found": {"EN": "Found {} clusters in this category", "DE": "{} Cluster in dieser Kategorie gefunden"},
    "msg_based_on_clusters": {"EN": "Based on {} clusters", "DE": "Basierend auf {} Clustern"},
    "msg_translation_not_available": {"EN": "Translated summary not available yet for this language.", "DE": "Übersetzte Zusammenfassung für diese Sprache noch nicht verfügbar."},
    "info_change_filters_or_browse": {"EN": "💡 Change filters and click 'Generate Summary' to create a new summary, or change categories to browse existing summaries.", "DE": "💡 Filter anpassen und auf 'Zusammenfassung erstellen' klicken für eine neue Zusammenfassung, oder Kategorie wechseln um bestehende Zusammenfassungen zu durchsuchen."},
    "msg_articles_count": {"EN": " ({} articles)", "DE": " ({} Artikel)"},
    "msg_clusters_in_request": {"EN": "{} clusters in this request", "DE": "{} Cluster in dieser Anfrage"},
    "lbl_mega_summary": {"EN": "📰 Overall Summary (Mega Summary)", "DE": "📰 Gesamtzusammenfassung (Mega Summary)"},
    "lbl_topic_summary": {"EN": "Topic Summary:", "DE": "Themen-Zusammenfassung:"},
    "lbl_articles": {"EN": "Articles in this cluster:", "DE": "Artikel in diesem Cluster:"},
    "warn_no_clusters": {"EN": "No clusters found for this category. Try a different category or generate a new summary.", "DE": "Keine Cluster für diese Kategorie gefunden. Versuchen Sie eine andere Kategorie."},
    "msg_processing": {"EN": "Processing... This may take up to 15 minutes", "DE": "Verarbeite... Dies kann bis zu 15 Minuten dauern"},
    "msg_generating_category": {"EN": "Generating summary for category: '{}'...", "DE": "Zusammenfassung wird erstellt für Kategorie: '{}'..."},
    "msg_success": {"EN": "Analysis Complete!", "DE": "Analyse abgeschlossen!"},
    "metric_batches": {"EN": "Batches Processed", "DE": "Verarbeitete Batches"},
    "metric_clusters": {"EN": "Source Clusters", "DE": "Quell-Cluster"},
    "metric_category": {"EN": "Category", "DE": "Kategorie"},
    "header_summary": {"EN": "### Cluster Summary", "DE": "### Cluster Zusammenfassung"},
    "expander_source": {"EN": "View Source Articles", "DE": "Quell-Artikel anzeigen"},
    "lbl_writing_style": {"EN": "Writing Style", "DE": "Schreibstil"},
    "lbl_output_format": {"EN": "Output Format", "DE": "Ausgabeformat"},
    "lbl_editorial_tone": {"EN": "Editorial Tone", "DE": "Editorialer Ton"},
    "caption_style_options": {"EN": "**Style option** — Default: original style preserved.", "DE": "**Stil-Option** — Standard: ursprünglicher Stil bleibt erhalten."},
    "btn_apply": {"EN": "Run", "DE": "Anwenden"},
    "msg_apply_sent": {"EN": "Preferences sent", "DE": "Einstellungen gesendet"},
    "err_apply": {"EN": "Error sending preferences", "DE": "Fehler beim Senden der Einstellungen"},
    "err_style_not_json": {"EN": "Invalid or empty response from style service.", "DE": "Ungültige oder leere Antwort vom Stil-Service."},
    "err_timeout": {"EN": "Request timed out after 15 minutes", "DE": "Zeitüberschreitung der Anfrage nach 15 Minuten"},
    "err_connect": {"EN": "Could not connect to n8n", "DE": "Verbindung zu n8n fehlgeschlagen"},
    "err_unexpected": {"EN": "An unexpected error occurred: {}", "DE": "Ein unerwarteter Fehler ist aufgetreten: {}"},

    # Categories
    "Technology": {"EN": "Technology", "DE": "Technologie"},
    "Global Politics": {"EN": "Global Politics", "DE": "Globale Politik"},
    "Economy": {"EN": "Economy", "DE": "Wirtschaft"},
    "Sports": {"EN": "Sports", "DE": "Sport"},
    "Health": {"EN": "Health", "DE": "Gesundheit"},
    "All": {"EN": "All", "DE": "Alle"},

    # Time Windows
    "last_6_hours":  {"EN": "Last 6 hours",  "DE": "Letzte 6 Stunden"},
    "last_12_hours": {"EN": "Last 12 hours", "DE": "Letzte 12 Stunden"},
    "last_24_hours": {"EN": "Last 24 hours", "DE": "Letzte 24 Stunden"},
    "last_3_days":   {"EN": "Last 3 days",   "DE": "Letzte 3 Tage"},
    "last_7_days":   {"EN": "Last 7 days",   "DE": "Letzte 7 Tage"},

    # Writing Styles
    "Default":     {"EN": "Default",     "DE": "Standard"},
    "Journalistic": {"EN": "Journalistic", "DE": "Journalistisch"},
    "Academic":    {"EN": "Academic",    "DE": "Akademisch"},
    "Executive":   {"EN": "Executive",   "DE": "Für Führungskräfte"},
    "LinkedIn":    {"EN": "LinkedIn",    "DE": "LinkedIn"},

    # Output Formats
    "Paragraph":    {"EN": "Paragraph",    "DE": "Fließtext"},
    "Bullet Point": {"EN": "Bullet Point", "DE": "Stichpunkte"},
    "TL;DR":        {"EN": "TL;DR",        "DE": "Kurzfassung"},
    "Sections":     {"EN": "Sections",     "DE": "Abschnitte"},

    # Editorial Tones
    "Neutral":       {"EN": "Neutral",       "DE": "Neutral"},
    "Institutional": {"EN": "Institutional", "DE": "Institutionell"},
}


def translate(tag: str, lang: str, fallback: str = None) -> str:
    """
    Returns the translation for a given tag in the specified language.
    If the tag or language is not found, it returns the fallback or the tag itself.
    """
    if not tag:
        return ""

    translation = TRANSLATIONS.get(tag)
    if translation:
        return translation.get(lang, fallback or tag)

    return fallback or tag
