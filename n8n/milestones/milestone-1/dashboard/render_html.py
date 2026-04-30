#!/usr/bin/env python3
import os
import json
from html import escape

ERROR_DIR = "/llm/data/errors"
SUCCESS_DIR = "/llm/data/successes"


def iter_files_safe(directory):
    if not os.path.isdir(directory):
        return []
    files = []
    for name in sorted(os.listdir(directory)):
        full = os.path.join(directory, name)
        if os.path.isfile(full):
            files.append(full)
    return files


def read_maybe_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        try:
            return json.loads(text), True
        except json.JSONDecodeError:
            return text, False
    except Exception as e:
        return f"ERROR reading file: {e}", False


def render_value(val):
    if isinstance(val, (dict, list)):
        return escape(json.dumps(val, indent=2, ensure_ascii=False))
    return escape(str(val))


def render_article_card(obj):
    """Render individual article summary as a card"""
    card_html = "<div class='article-card'>"

    # Title
    if 'title' in obj:
        card_html += f"<h3 class='article-title'>{escape(obj['title'])}</h3>"

    # Metadata row
    meta_items = []
    if 'source' in obj:
        meta_items.append(f"<span class='badge badge-source'>{escape(obj['source'])}</span>")
    if 'article_id' in obj:
        meta_items.append(f"<span class='badge badge-id'>{escape(obj['article_id'])}</span>")
    if 'model' in obj:
        meta_items.append(f"<span class='badge badge-model'>{escape(obj['model'])}</span>")

    if meta_items:
        card_html += f"<div class='meta-row'>{''.join(meta_items)}</div>"

    # Summary
    if 'summary' in obj:
        card_html += f"<div class='summary-text'>{escape(obj['summary'])}</div>"

    # Footer with URL and timestamp
    footer_items = []
    if 'url' in obj:
        footer_items.append(f"<a href='{escape(obj['url'])}' target='_blank' class='article-link'>🔗 Read original</a>")
    if 'processed_at' in obj:
        footer_items.append(f"<span class='timestamp'>⏱️ {escape(obj['processed_at'][:19].replace('T', ' '))}</span>")

    if footer_items:
        card_html += f"<div class='card-footer'>{' '.join(footer_items)}</div>"

    card_html += "</div>"
    return card_html


def render_mega_summary_card(obj):
    """Render mega summary with special styling"""
    card_html = "<div class='mega-summary-card'>"
    card_html += "<h2 class='mega-title'>📰 Mega Summary</h2>"

    # Stats
    stats = []
    if 'article_count' in obj:
        stats.append(
            f"<div class='stat'><span class='stat-label'>Articles</span><span class='stat-value'>{obj['article_count']}</span></div>")
    if 'summary_length' in obj:
        stats.append(
            f"<div class='stat'><span class='stat-label'>Length</span><span class='stat-value'>{obj['summary_length']} chars</span></div>")
    if 'sources' in obj and obj['sources']:
        sources_text = ', '.join(obj['sources'])
        stats.append(
            f"<div class='stat'><span class='stat-label'>Sources</span><span class='stat-value'>{escape(sources_text)}</span></div>")

    if stats:
        card_html += f"<div class='stats-row'>{''.join(stats)}</div>"

    # Summary
    if 'summary' in obj:
        card_html += f"<div class='mega-summary-text'>{escape(obj['summary'])}</div>"

    # Timestamp
    if 'generated_at' in obj:
        card_html += f"<div class='mega-footer'>Generated: {escape(obj['generated_at'][:19].replace('T', ' '))}</div>"

    card_html += "</div>"
    return card_html


def render_section(title, directory):
    files = iter_files_safe(directory)
    if not files:
        return f"<div class='section'><h2>{escape(title)}</h2><p class='empty-state'>No files found.</p></div>"

    # Separate mega summary from individual articles
    mega_files = [f for f in files if 'mega' in os.path.basename(f).lower()]
    article_files = [f for f in files if 'mega' not in os.path.basename(f).lower()]

    parts = [f"<div class='section'><h2>{escape(title)}</h2>"]

    # Render mega summaries first
    for path in mega_files:
        data, is_json = read_maybe_json(path)
        if is_json and isinstance(data, dict):
            parts.append(render_mega_summary_card(data))

    # Render individual articles
    if article_files:
        parts.append("<div class='articles-grid'>")
        for path in article_files:
            data, is_json = read_maybe_json(path)
            if is_json and isinstance(data, dict):
                parts.append(render_article_card(data))
            elif is_json and isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        parts.append(render_article_card(entry))
        parts.append("</div>")

    parts.append("</div>")
    return "".join(parts)


def main():
    html = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<meta charset='utf-8'/>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>News Summary Dashboard</title>",
        "<style>",
        """
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
        }

        .header p {
            opacity: 0.9;
            font-size: 1.1em;
        }

        .section {
            padding: 40px;
        }

        .section h2 {
            font-size: 1.8em;
            margin-bottom: 24px;
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }

        .mega-summary-card {
            background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 40px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        }

        .mega-title {
            font-size: 2em;
            color: #d35400;
            margin-bottom: 20px;
        }

        .stats-row {
            display: flex;
            gap: 20px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }

        .stat {
            background: white;
            padding: 16px 24px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            flex: 1;
            min-width: 150px;
        }

        .stat-label {
            display: block;
            font-size: 0.85em;
            color: #666;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-value {
            display: block;
            font-size: 1.5em;
            font-weight: bold;
            color: #d35400;
        }

        .mega-summary-text {
            background: white;
            padding: 20px;
            border-radius: 8px;
            line-height: 1.8;
            font-size: 1.05em;
            color: #2c3e50;
        }

        .mega-footer {
            margin-top: 16px;
            text-align: right;
            font-size: 0.9em;
            color: #d35400;
            opacity: 0.8;
        }

        .articles-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 24px;
        }

        .article-card {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            flex-direction: column;
        }

        .article-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.15);
        }

        .article-title {
            font-size: 1.2em;
            margin-bottom: 12px;
            color: #2c3e50;
            font-weight: 600;
            line-height: 1.4;
        }

        .meta-row {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 500;
        }

        .badge-source {
            background: #667eea;
            color: white;
        }

        .badge-id {
            background: #e9ecef;
            color: #495057;
        }

        .badge-model {
            background: #20c997;
            color: white;
        }

        .summary-text {
            flex: 1;
            margin-bottom: 16px;
            color: #495057;
            line-height: 1.7;
        }

        .card-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 16px;
            border-top: 1px solid #dee2e6;
            gap: 12px;
            flex-wrap: wrap;
        }

        .article-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s;
        }

        .article-link:hover {
            color: #764ba2;
            text-decoration: underline;
        }

        .timestamp {
            font-size: 0.85em;
            color: #6c757d;
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
            font-size: 1.1em;
        }

        @media (max-width: 768px) {
            .articles-grid {
                grid-template-columns: 1fr;
            }

            .header h1 {
                font-size: 1.8em;
            }

            .stats-row {
                flex-direction: column;
            }
        }
        """,
        "</style>",
        "</head>",
        "<body>",
        "<div class='container'>",
        "<div class='header'>",
        "<h1>📰 News Summary Dashboard</h1>",
        "<p>Automated news aggregation and summarization</p>",
        "</div>",
    ]

    html.append(render_section("📊 Results", SUCCESS_DIR))
    html.append(render_section("❌ Errors", ERROR_DIR))

    html.append("</div></body></html>")
    print("".join(html))


if __name__ == "__main__":
    main()
