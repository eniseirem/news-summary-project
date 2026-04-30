import streamlit as st
import requests
import json
import sys

# --- CONFIGURATION: PRODUCTION MODE ---
# Set to False for the VM (Production) so it connects to the real server
USE_MOCK_DATA = False 

# Import helper modules (wrapped to prevent crash if files are missing locally)
try:
    from config import N8N_WEBHOOK_URL, OPENSEARCH_URLS, OPENSEARCH_USER, OPENSEARCH_PASS
    from opensearch import (
        fetch_categories_from_opensearch,
        fetch_subcategories_from_opensearch,
        fetch_clusters_from_opensearch,
        fetch_keywords_from_opensearch,
    )
    from translate import TRANSLATIONS, translate
except ImportError:
    # Fallback dummies if helper files are missing
    N8N_WEBHOOK_URL = "http://localhost:5678/webhook/cluster-summary"
    # ORIGINAL VM CONNECTION VALUES (Fallback)
    OPENSEARCH_URLS = [
        "https://opensearch:9200",           # Main Internal Docker URL
        "https://host.docker.internal:9200", # Fallback
        "https://localhost:9200"             # Fallback
    ]
    OPENSEARCH_USER = "admin"
    OPENSEARCH_PASS = "admin"
    
    TRANSLATIONS = {"EN": {}, "DE": {}} 
    def translate(key, lang, fallback=None): return fallback or key
    def fetch_categories_from_opensearch(): return [], None, []
    def fetch_subcategories_from_opensearch(c, u): return []
    def fetch_clusters_from_opensearch(c, s, u, language="en"): return [], None

#Summary Translation
def _lang_matches(a, b):
    return (a or "").strip().lower() == (b or "").strip().lower()


def get_localized_field(original, translated, translated_language, selected_language):
    if translated and _lang_matches(translated_language, selected_language):
        return translated
    return original


# --- TASK 1: HELPER FOR NEW DATA MODEL ---
def get_localized_content(field_value, lang_code):
    """
    Handle fields that might be strings (old) or dicts (new).
    Returns the string for the selected language.
    """
    if isinstance(field_value, dict):
        # Try selected language, fallback to 'en', then empty string
        return field_value.get(lang_code, field_value.get("en", ""))
    # If it's just a string (old format), return it as is
    return str(field_value) if field_value else ""

# --- TASK 2: WARNING MESSAGES (Defined locally) ---
WARNING_TRANSLATIONS = {
    
    "warn_inst_bullets": {
        "EN": "Institutional tone in bullet points can sound overly rigid. Formality will be slightly reduced for clarity.",
        "DE": "Institutioneller Ton in Stichpunkten kann sehr starr wirken. Die Formalität wird zugunsten der Klarheit etwas reduziert."
    }
    
}

# --- TASK 2: VALIDATION LOGIC ---
def validate_styling_selection(tone, style, fmt, lang):
    """
    Validates combinations of Tone, Style, and Format based on LLM Safety Gate rules.
    """
    norm_tone = tone
    norm_style = style
    norm_fmt = fmt
    warning_key = None
    
    
    if tone == "Institutional" and fmt == "Bullet Point":
        warning_key = "warn_inst_bullets"
        
    warning_msg = None
    if warning_key:
        warning_msg = WARNING_TRANSLATIONS[warning_key].get(lang, "")
        
    return {
        "is_valid": warning_key is None,
        "normalized_selection": {
            "editorial_tone": norm_tone,
            "writing_style": norm_style,
            "output_format": norm_fmt
        },
        "warning": warning_msg
    }

# --- MOCK DATA WRAPPERS ---
def get_categories_wrapper():
    if USE_MOCK_DATA:
        return ["Technology", "Politics", "Economy", "Local Test"], "http://mock-local", None
    return fetch_categories_from_opensearch()

def get_subcategories_wrapper(category, url):
    if USE_MOCK_DATA:
        return ["AI", "Crypto", "Local Subcat"]
    return fetch_subcategories_from_opensearch(category, url)

def get_clusters_wrapper(category, subcategory, url, language="en"):
    if USE_MOCK_DATA:
        # Fake Data reflecting NEW Data Model (Dicts for translations)
        dummy_clusters = [{
            "cluster_id": 999,
            "request_id": "mock_req_1",
            "topic_label": f"Local Test Topic ({language})",
            # New Field Name: summary_translated
            "summary_translated": {
                "en": "This is the English summary of the cluster.",
                "de": "Dies ist die deutsche Zusammenfassung des Clusters."
            },
            # Fallback for old field name
            "topic_summary": "Legacy Summary String",
            "article_count": 5,
            "processed_at": "2025-10-10T10:00:00",
            "articles": [
                {"id": "1", "title": "Test Article A", "source": "CNN", "url": "http://google.com"},
                {"id": "2", "title": "Test Article B", "source": "BBC", "url": "http://google.com"}
            ],
            # New Field Name: category_translated
            "category_translated": {
                "en": "Technology",
                "de": "Technologie"
            }
        }]
        # New Field Name: mega_summary_translated
        mega_sum = {
            "en": "This is a Mega Summary in English.",
            "de": "Dies ist eine Mega-Zusammenfassung auf Deutsch."
        }
        return dummy_clusters, mega_sum
    
    return fetch_clusters_from_opensearch(category, subcategory, url, language=language)


# UI LAYOUT
st.set_page_config(page_title="News Cluster Dashboard", layout="wide")

# -- LANGUAGE SELECTION --
if "language" not in st.session_state:
    st.session_state.language = "EN"

if "lang_radio" not in st.session_state:
    st.session_state.lang_radio = "English" if st.session_state.language == "EN" else "Deutsch"

# Sidebar
with st.sidebar:
    st.header("Language / Sprache")

    def _on_lang_change():
        sel = st.session_state.get("lang_radio", "English")
        st.session_state.language = "EN" if sel == "English" else "DE"

    lang_choice = st.radio(
        "Select Language",
        options=["English", "Deutsch"],
        index=0 if st.session_state.lang_radio == "English" else 1,
        key="lang_radio",
        on_change=_on_lang_change,
        horizontal=True,
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.header(translate("header_settings", st.session_state.language))

    # Fetch categories
    with st.spinner(translate("loading_cats", st.session_state.language)):
        # USE WRAPPER
        categories, opensearch_url, errors = get_categories_wrapper()

    if opensearch_url:
        print(f"[INFO] Successfully connected to OpenSearch at {opensearch_url}", file=sys.stderr)
    else:
        print("[WARNING] Failed to load categories from OpenSearch", file=sys.stderr)
        if errors and not USE_MOCK_DATA:
            err_lines = []
            for e in errors:
                url = e.get("url", "?")
                status = e.get("status", "")
                err_msg = e.get("error") or e.get("exception", "")
                err_lines.append(f"{url} -> {status} {err_msg}".strip())
            st.error("OpenSearch categories could not be loaded. Details:\n\n" + "\n".join(err_lines))
            st.info("Categories come from the **clusters** index. If the index is missing or empty, run `opensearch/scripts/restore_indices.sh` and ensure OpenSearch data was restored from the bundle (or seed the clusters index).")
        elif not USE_MOCK_DATA:
            st.error("OpenSearch categories could not be loaded.")

    if not categories:
        categories = ["[OpenSearch error: see messages]"]

    # Category selection
    selected_category = st.selectbox(
        translate("lbl_category", st.session_state.language),
        options=categories,
        format_func=lambda x: translate(x, st.session_state.language, fallback=x)
    )

    # Subcategory selection
    # USE WRAPPER
    subcategories = get_subcategories_wrapper(selected_category, opensearch_url) if opensearch_url else []
    selected_subcategory = None
    if subcategories:
        selected_subcategory = st.selectbox(
            translate("lbl_subcategory", st.session_state.language),
            options=["All"] + subcategories,
            format_func=lambda x: translate(x, st.session_state.language, fallback=x) if x == "All" else x
        )
        if selected_subcategory == "All":
            selected_subcategory = None

    # Keywords are computed per cluster and shown in the results below.
    # We keep this empty list for payload compatibility.
    selected_keywords = []

    # Time window
    time_window_options = ["last_6_hours", "last_12_hours", "last_24_hours", "last_3_days", "last_7_days"]
    time_window = st.selectbox(
        translate("lbl_timewindow", st.session_state.language),
        options=time_window_options,
        index=2,
        format_func=lambda k: translate(k, st.session_state.language)
    )

    style_version = "Neutral"
    sentiment_target = "None"
    size = 15

    st.caption(f"Using defaults: Style={style_version}, Sentiment={sentiment_target}, Max Articles={size}")

    run_btn = st.button(translate("btn_generate", st.session_state.language), type="primary")

# -- MAIN PAGE --
st.title(translate("title", st.session_state.language))

# --- Right Column Dropdowns ---
main_col, right_col = st.columns([1, 2])  # Wider space for style options (right)

with right_col:
    st.caption(translate("caption_style_options", st.session_state.language))
    style_col1, style_col2, style_col3 = st.columns(3)
    with style_col1:
        writing_style_options = ["Default", "Journalistic", "Academic", "Executive"]
        writing_style = st.selectbox(
            translate("lbl_writing_style", st.session_state.language),
            options=writing_style_options,
            index=0,
            key="writing_style_select",
            format_func=lambda k: translate(k, st.session_state.language)
        )
    with style_col2:
        output_format_options = ["Default", "Paragraph", "Bullet Point", "TL;DR", "Sections"]
        output_format = st.selectbox(
            translate("lbl_output_format", st.session_state.language),
            options=output_format_options,
            index=0,
            key="output_format_select",
            format_func=lambda k: translate(k, st.session_state.language)
        )
    with style_col3:
        editorial_tone_options = ["Default", "Neutral", "Institutional"]
        editorial_tone = st.selectbox(
            translate("lbl_editorial_tone", st.session_state.language),
            options=editorial_tone_options,
            index=0,
            key="editorial_tone_select",
            format_func=lambda k: translate(k, st.session_state.language)
        )

    # --- LIVE VALIDATION ---
    validation_res = validate_styling_selection(
        editorial_tone, 
        writing_style, 
        output_format, 
        st.session_state.language
    )

    if validation_res["warning"]:
        st.warning(validation_res["warning"])

# Find the Apply button section (around line 268) and replace it with this updated version:

    # Apply button - works for both Browse and Generate modes
    apply_clicked = st.button(translate("btn_apply", st.session_state.language), key="apply_prefs")
    if apply_clicked:
        # Check if there's any summary available (either browsed or generated)
        current_summary = st.session_state.get('current_display_summary')
        
        if not current_summary:
            st.warning("Please browse a category or generate a summary first before applying styles.")
        else:
            lang_code = "en" if st.session_state.language == "EN" else "de"
            norm = validation_res["normalized_selection"]
            
            ws_payload = None if norm["writing_style"] == "Default" else norm["writing_style"]
            of_payload = None if norm["output_format"] == "Default" else norm["output_format"]
            et_payload = None if norm["editorial_tone"] == "Default" else norm["editorial_tone"]

            # Send the existing summary to be restyled
            payload = {
                "action": "apply_style",
                "summary": current_summary,
                "request_id": st.session_state.get('current_request_id'),
                "language": lang_code,
                "writing_style": ws_payload,
                "output_format": of_payload,
                "editorial_tone": et_payload,
                "original_filters": {
                    "category": selected_category,
                    "subcategory": selected_subcategory,
                    "time_window": time_window,
                    "keywords": selected_keywords
                }
            }

            print(f"[DEBUG] Apply style payload: {json.dumps(payload)}", file=sys.stderr)
            
            # Use style webhook endpoint
            STYLE_WEBHOOK_URL = N8N_WEBHOOK_URL.replace('/webhook/cluster-summary', '/webhook/style')
            print(f"[INFO] Sending to style webhook: {STYLE_WEBHOOK_URL}", file=sys.stderr)
            
            try:
                with st.spinner(translate("msg_processing", st.session_state.language)):
                    resp = requests.post(STYLE_WEBHOOK_URL, json=payload, timeout=900)

                if resp.status_code == 200:
                    styled_data = None
                    try:
                        text = (resp.text or "").strip()
                        if not text:
                            raise ValueError("Empty response from style service")
                        styled_data = resp.json()
                    except (ValueError, json.JSONDecodeError, requests.exceptions.JSONDecodeError):
                        st.error(translate("err_apply", st.session_state.language) + ": " + translate("err_style_not_json", st.session_state.language))
                        if resp.text:
                            st.code(resp.text[:500], language="text")

                    if styled_data is not None:
                        # Handle both array and single object responses
                        if isinstance(styled_data, list) and len(styled_data) > 0:
                            styled_result = styled_data[0]
                        else:
                            styled_result = styled_data if isinstance(styled_data, dict) else {}
                        
                        styled_summary = styled_result.get("styled_summary", "") if isinstance(styled_result, dict) else ""
                        
                        if styled_summary:
                            # Update the displayed summary with the styled version
                            st.session_state.current_display_summary = styled_summary
                            st.session_state.current_style_metadata = {
                                "writing_style": styled_result.get("writing_style"),
                                "output_format": styled_result.get("output_format"),
                                "institutional": styled_result.get("institutional"),
                                "processed_at": styled_result.get("processed_at")
                            }
                            st.success(translate("msg_apply_sent", st.session_state.language))
                            st.rerun()  # Refresh to show the styled summary
                        else:
                            st.error("No styled summary returned from server")
                else:
                    st.error(f"{translate('err_apply', st.session_state.language)}: {resp.status_code}")
                    st.code(resp.text)
            except requests.exceptions.Timeout:
                st.error(translate("err_timeout", st.session_state.language))
            except requests.exceptions.ConnectionError:
                st.error(translate("err_connect", st.session_state.language))
            except Exception as e:
                st.error(translate("err_unexpected", st.session_state.language).format(e))
                import traceback
                st.code(traceback.format_exc())
# Browse Mode (showing existing clusters and mega summary)
if opensearch_url and not run_btn:
    # If user changed category (or subcategory) while viewing a generated summary, switch to browse mode for the new selection
    if st.session_state.get('summary_source') == 'generated':
        if selected_category != st.session_state.get('generated_category') or selected_subcategory != st.session_state.get('generated_subcategory'):
            for key in ('summary_source', 'current_display_summary', 'current_request_id', 'current_style_metadata', 'generated_category', 'generated_subcategory'):
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    # Check if there's an active generated summary (same category as current selection)
    if st.session_state.get('summary_source') == 'generated':
        # Show the generated summary section (not browse mode)
        st.markdown("---")
        st.subheader(translate("header_summary", st.session_state.language))
        
        # Display the generated summary (original or styled)
        if st.session_state.get('current_display_summary'):
            st.markdown(st.session_state.current_display_summary)
            
            # Show styling info if available
            if st.session_state.get('current_style_metadata'):
                metadata = st.session_state.current_style_metadata
                style_info = []
                if metadata.get('writing_style'):
                    style_info.append(f"Style: {metadata['writing_style'].title()}")
                if metadata.get('output_format'):
                    style_info.append(f"Format: {metadata['output_format'].replace('_', ' ').title()}")
                if metadata.get('institutional'):
                    style_info.append("Tone: Institutional")
                if style_info:
                    st.caption("🎨 " + " | ".join(style_info))
            
            st.info(translate("info_change_filters_or_browse", st.session_state.language))
    
    else:
        # Show normal Browse Mode
        st.markdown("---")
        display_cat = translate(selected_category, st.session_state.language, fallback=selected_category)
        st.subheader(f"{translate('header_browse', st.session_state.language)}: {display_cat}")

        with st.spinner(translate("loading_cats", st.session_state.language)):
            lang_code = "en" if st.session_state.language == "EN" else "de"
            # Pass language to fetch function
            clusters, mega_summary_data = fetch_clusters_from_opensearch(selected_category, selected_subcategory, opensearch_url, language=lang_code)

        if clusters:
            st.info(
                translate("info_clusters_found", st.session_state.language)
                .format(len(clusters))
            )

            # --- Mega Summary (category-level overview) ---
            if mega_summary_data:
                # Get the current request ID and language from the database
                current_request = mega_summary_data.get("request_id", "browse_mode")
                stored_request = st.session_state.get('current_request_id')
                stored_language = st.session_state.get('current_language')
                
                # Check if the category/request OR language has changed
                category_changed = (stored_request != current_request)
                language_changed = (stored_language != lang_code)
                
                # If category or language changed, clear the old styled version and use fresh translation
                show_translation_unavailable = False  # only for browse API content when DE (or selected lang) not available
                if category_changed or language_changed:
                    mega_text = get_localized_field(
                        original=mega_summary_data.get("original"),
                        translated=mega_summary_data.get("translated"),
                        translated_language=mega_summary_data.get("translated_language"),
                        selected_language=lang_code
                    )
                    # Only show "not available" when we're actually showing the original (no translation used) and user selected a non-English language
                    has_translation = mega_summary_data.get("translated") and _lang_matches(mega_summary_data.get("translated_language"), lang_code)
                    show_translation_unavailable = (mega_text == mega_summary_data.get("original")) and (lang_code != "en") and not has_translation
                    # Clear old styling metadata when category/language changes
                    if 'current_style_metadata' in st.session_state:
                        del st.session_state.current_style_metadata
                # If we have a styled summary from the response, always show it (ignore language match)
                elif st.session_state.get('current_display_summary') and st.session_state.get('current_style_metadata'):
                    mega_text = st.session_state.current_display_summary
                # If same category AND language and we have a previous browse summary (no style applied), use it
                elif st.session_state.get('current_display_summary') and st.session_state.get('summary_source') == 'browse':
                    mega_text = st.session_state.current_display_summary
                # Otherwise, use fresh translation from API
                else:
                    mega_text = get_localized_field(
                        original=mega_summary_data.get("original"),
                        translated=mega_summary_data.get("translated"),
                        translated_language=mega_summary_data.get("translated_language"),
                        selected_language=lang_code
                    )
                    has_translation = mega_summary_data.get("translated") and _lang_matches(mega_summary_data.get("translated_language"), lang_code)
                    show_translation_unavailable = (mega_text == mega_summary_data.get("original")) and (lang_code != "en") and not has_translation

                if mega_text:
                    # Store mega summary for Apply button
                    st.session_state.current_display_summary = mega_text
                    st.session_state.current_request_id = current_request
                    st.session_state.current_language = lang_code  # STORE LANGUAGE TOO
                    st.session_state.summary_source = "browse"
                    
                    with st.expander(
                        translate("lbl_mega_summary", st.session_state.language),
                        expanded=True
                    ):
                        st.markdown(
                            f"**{translate('lbl_global_overview', st.session_state.language)}**"
                        )
                        # Display the current summary (either original or styled)
                        st.markdown(mega_text)
                        
                        # Show styling info if available
                        if st.session_state.get('current_style_metadata'):
                            metadata = st.session_state.current_style_metadata
                            style_info = []
                            if metadata.get('writing_style'):
                                style_info.append(f"Style: {metadata['writing_style'].title()}")
                            if metadata.get('output_format'):
                                style_info.append(f"Format: {metadata['output_format'].replace('_', ' ').title()}")
                            if metadata.get('institutional'):
                                style_info.append("Tone: Institutional")
                            if style_info:
                                st.caption("🎨 " + " | ".join(style_info))
                        
                        st.caption(translate("msg_based_on_clusters", st.session_state.language).format(len(clusters)))
                        if show_translation_unavailable and not st.session_state.get('current_style_metadata'):
                            st.info(translate("msg_translation_not_available", st.session_state.language))

            st.markdown("---")

            # --- Individual Clusters ---
            clusters_by_request = {}
            for cluster in clusters:
                request_id = cluster.get("request_id", "unknown")
                if request_id not in clusters_by_request:
                    clusters_by_request[request_id] = []
                clusters_by_request[request_id].append(cluster)

            for request_id, request_clusters in clusters_by_request.items():
                if len(clusters_by_request) > 1:
                    st.caption(translate("msg_clusters_in_request", st.session_state.language).format(len(request_clusters)))

                for cluster in request_clusters:
                    cluster_id = cluster.get("cluster_id", "N/A")
                    
                    # --- UPDATE: Handle New Data Model Fields ---
                    # Check 'summary_translated' first, then fallback
                    topic_summary = get_localized_field(
                        original=cluster.get("topic_summary"),
                        translated=cluster.get("summary_translated"),
                        translated_language=cluster.get("summary_translated_language"),
                        selected_language=lang_code
                    )

                    
                    # Topic Label (Title)
                    topic_label = cluster.get("topic_label", "")

                    article_count = cluster.get("article_count", 0)
                    processed_at = cluster.get("processed_at", "")[:19]

                    header_text = f"**Cluster {cluster_id}**"
                    if topic_label:
                        header_text += f" - {topic_label}"
                    header_text += translate("msg_articles_count", st.session_state.language).format(article_count)

                    with st.expander(header_text):
                        # --- Cluster-specific keywords (read-only) ---
                        keywords_label = translate("lbl_keywords", st.session_state.language, fallback="Keywords")
                        cluster_kw = cluster.get("keywords", [])
                        if cluster_kw:
                            st.markdown(f"**{keywords_label}**")
                            st.text(", ".join(cluster_kw))
                            st.markdown("---")

                        if topic_summary:
                            st.markdown(f"**{translate('lbl_topic_summary', st.session_state.language)}**")
                            st.markdown(topic_summary)
                            st.markdown("---")
                        
                        st.caption(f"Processed: {processed_at}")
                        articles = cluster.get("articles", [])
                        if articles:
                            st.markdown(f"**{translate('lbl_articles', st.session_state.language)}**")
                            for i, article in enumerate(articles, 1):
                                title = article.get("title", "No title")
                                source = article.get("source", "Unknown")
                                st.markdown(f"{i}. **{title}**")
                                if article.get("url"):
                                    st.caption(f"[Link]({article.get('url')})")
                                st.markdown("")
                        else:
                            st.caption("No articles found in this cluster")

                if len(clusters_by_request) > 1:
                    st.markdown("---")
        else:
            st.warning(translate("warn_no_clusters", st.session_state.language))
            # Clear summary if no clusters
            st.session_state.current_display_summary = None
# Generate Mode (creating new summary via webhook)
if run_btn:
    display_cat = translate(selected_category, st.session_state.language, fallback=selected_category)
    print(f"[INFO] User requested summary for category: '{selected_category}'", file=sys.stderr)
    st.info(translate("msg_generating_category", st.session_state.language).format(display_cat))

    try:
        lang_code = "en" if st.session_state.language == "EN" else "de"

        # --- RE-VALIDATE ---
        val_res_main = validate_styling_selection(
            editorial_tone, 
            writing_style, 
            output_format, 
            st.session_state.language
        )
        norm_main = val_res_main["normalized_selection"]

        payload = {
            "time_window": time_window,
            "category": selected_category,
            "subcategory": selected_subcategory,
            "keywords": selected_keywords,
            "size": size,
            "style_version": style_version,
            "sentiment_target": sentiment_target,
            "use_cluster_filter": True,
            "language": lang_code,
            "writing_style": None if norm_main["writing_style"] == "Default" else norm_main["writing_style"],
            "output_format": None if norm_main["output_format"] == "Default" else norm_main["output_format"],
            "editorial_tone": None if norm_main["editorial_tone"] == "Default" else norm_main["editorial_tone"]
        }

        print(f"[DEBUG] Request payload: {json.dumps(payload, indent=2)}", file=sys.stderr)
        print(f"[INFO] Sending request to n8n", file=sys.stderr)
        
        with st.spinner(translate("msg_processing", st.session_state.language)):
            response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=900)

        print(f"[DEBUG] n8n response status: {response.status_code}", file=sys.stderr)

        # --- SAFETY NET: CHECK FOR JSON ---
        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError:
                st.error("Backend Error: The server returned text instead of JSON.")
                st.markdown("**Raw Response from Server:**")
                st.code(response.text)
                st.stop()
            
            print(f"[INFO] Received successful response from n8n", file=sys.stderr)

            if data.get("batches_processed", 0) == 0 or data.get("source_clusters", 0) == 0:
                print(f"[WARNING] No results found: {data.get('message', 'N/A')}", file=sys.stderr)
                st.warning(f"{data.get('message', 'No articles found matching your filters')}")
            else:
                summary_text = data.get("final_summary", data.get("summary", ""))
                
                # STORE IN SESSION STATE for Apply button
                st.session_state.current_display_summary = summary_text
                st.session_state.current_request_id = data.get("request_id")
                st.session_state.summary_source = "generated"
                st.session_state.generated_category = selected_category
                st.session_state.generated_subcategory = selected_subcategory

                # When DE is selected: bypass style UI and apply standard style so styled summary is shown
                if lang_code == "de":
                    STYLE_WEBHOOK_URL = N8N_WEBHOOK_URL.replace('/webhook/cluster-summary', '/webhook/style')
                    style_payload = {
                        "action": "apply_style",
                        "summary": summary_text,
                        "request_id": data.get("request_id"),
                        "language": lang_code,
                        "writing_style": None,
                        "output_format": None,
                        "editorial_tone": None,
                        "original_filters": {
                            "category": selected_category,
                            "subcategory": selected_subcategory,
                            "time_window": time_window,
                            "keywords": selected_keywords
                        }
                    }
                    try:
                        with st.spinner(translate("msg_processing", st.session_state.language)):
                            style_resp = requests.post(STYLE_WEBHOOK_URL, json=style_payload, timeout=900)
                        if style_resp.status_code == 200 and style_resp.text and style_resp.text.strip():
                            styled_data = style_resp.json()
                            styled_result = styled_data[0] if isinstance(styled_data, list) and len(styled_data) > 0 else (styled_data if isinstance(styled_data, dict) else {})
                            styled_summary = styled_result.get("styled_summary", "") if isinstance(styled_result, dict) else ""
                            if styled_summary:
                                st.session_state.current_display_summary = styled_summary
                                st.session_state.current_style_metadata = {
                                    "writing_style": styled_result.get("writing_style"),
                                    "output_format": styled_result.get("output_format"),
                                    "institutional": styled_result.get("institutional"),
                                    "processed_at": styled_result.get("processed_at")
                                }
                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, ValueError):
                        pass  # Keep showing unstyled summary on style failure
                
                st.success(translate("msg_success", st.session_state.language))

                col1, col2, col3 = st.columns(3)
                with col1: st.metric(translate("metric_batches", st.session_state.language), data.get("batches_processed", 0))
                with col2: st.metric(translate("metric_clusters", st.session_state.language), data.get("source_clusters", 0))
                with col3: st.metric(translate("metric_category", st.session_state.language), translate(selected_category, st.session_state.language, fallback=selected_category))

                st.markdown(translate("header_summary", st.session_state.language))
                # Display the current summary (either original or styled)
                st.markdown(st.session_state.current_display_summary)

                all_clusters = data.get("all_clusters", [])
                if all_clusters:
                    with st.expander(translate("expander_source", st.session_state.language)):
                        for i, cluster in enumerate(all_clusters, 1):
                            # --- UPDATE: Handle Category Translation + Label Fallback ---
                            # Priority: category_translated -> category_label -> category
                            cat_display = get_localized_field(
                                original=cluster.get("category_label") or cluster.get("category"),
                                translated=cluster.get("category_translated"),
                                translated_language=cluster.get("category_translated_language"),
                                selected_language=lang_code
                            )


                            st.markdown(f"**Cluster {i}** ({cat_display})")
                            articles = cluster.get("articles", [])
                            if articles:
                                for j, article in enumerate(articles, 1):
                                    title = article.get("title", "No title")
                                    source = article.get("source", "Unknown")
                                    st.markdown(f"**{j}. {title}**")
                                    st.caption(f"Source: {source}")
                                    st.markdown("---")
                            else:
                                st.caption("No articles in this cluster")

                if data.get("individual_summaries"):
                    with st.expander("Individual Batch Summaries"):
                        for i, summary in enumerate(data["individual_summaries"], 1):
                            st.markdown(f"**Batch {i}**")
                            st.write(summary.get("summary", ""))
                            st.markdown("---")
        else:
            print(f"[ERROR] n8n returned error status: {response.status_code}", file=sys.stderr)
            st.error(f"Error from n8n: {response.status_code}")
            st.code(response.text)

    except requests.exceptions.Timeout:
        st.error(translate("err_timeout", st.session_state.language))
    except requests.exceptions.ConnectionError:
        st.error(translate("err_connect", st.session_state.language))
    except Exception as e:
        st.error(translate("err_unexpected", st.session_state.language).format(e))
