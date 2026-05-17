import os
import re
from flask import Flask, request, jsonify
import cloudscraper
from bs4 import BeautifulSoup

app = Flask(__name__)
API_KEY = os.environ.get('API_KEY', 'changeme123')

# ── Auth ─────────────────────────────────────────────────────────
def check_auth():
    key = request.headers.get('x-api-key') or request.args.get('key')
    return key == API_KEY

# ── Helpers ──────────────────────────────────────────────────────
FINAL_DOMAINS = ['mega.nz', 'drive.google.com', 'mediafire.com', 'gofile.io', '1fichier.com']
LOCKED_DOMAINS = ['link-hub.net', 'link-target.net', 'link-center.net', 'linkvertise.com',
                  'work.ink', 'lootlinks.co', 'loot-link.com', 'sub2unlock.com', 'sub2get.com',
                  'pastelink.net', 'direct-link.net']

def is_final(url):
    return any(d in url for d in FINAL_DOMAINS)

def is_locked(url):
    return any(d in url for d in LOCKED_DOMAINS)

def extract_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('http') and any(d in href for d in FINAL_DOMAINS):
            links.append(href)
    return links

def bypass_url(url, depth=0):
    if depth > 3:
        return {'status': 'failed', 'error': 'Too many redirects'}

    # Already a final link
    if is_final(url):
        return {'status': 'success', 'result': url}

    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )

        # Try bypass.city API style first
        bypass_url_encoded = requests.utils.quote(url, safe='')
        response = scraper.get(
            f'https://bypass.city/bypass?bypass={bypass_url_encoded}',
            timeout=30,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
        )

        html = response.text

        # Extract final links from page
        links = extract_links(html)
        if links:
            return {'status': 'success', 'result': links[0]}

        # Check if there's another locked link to follow
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if is_locked(href):
                return bypass_url(href, depth + 1)

        # Try regex extraction
        mega_match = re.search(r'https?://mega\.nz/[^\s"\'<>]+', html)
        if mega_match:
            return {'status': 'success', 'result': mega_match.group(0)}

        return {'status': 'failed', 'error': 'No final link found on page'}

    except Exception as e:
        return {'status': 'failed', 'error': str(e)}


# ── Routes ───────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'status': 'ok'})


@app.route('/bypass', methods=['POST'])
def bypass():
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    url = data.get('url') if data else None

    if not url:
        return jsonify({'error': 'url is required'}), 400

    result = bypass_url(url)
    result['original'] = url
    return jsonify(result)


@app.route('/bypass-bulk', methods=['POST'])
def bypass_bulk():
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    urls = data.get('urls', []) if data else []

    if not urls:
        return jsonify({'error': 'urls array is required'}), 400

    results = []
    for url in urls:
        result = bypass_url(url.get('url', ''))
        result['original'] = url.get('url', '')
        result['context'] = url.get('context', '')
        results.append(result)

    return jsonify({'status': 'success', 'results': results})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
