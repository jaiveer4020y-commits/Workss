from flask import Flask, request, jsonify, Response
import requests
import re
import json
import time
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_URL = "https://allmovieland.ac"

class AllMovieLandM3U8:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def get_cookies(self):
        try:
            self.session.get(BASE_URL, timeout=10)
            return True
        except:
            return False

    def extract_video_data(self, content_url):
        try:
            response = self.session.get(content_url, timeout=10)
            if response.status_code != 200:
                return None

            html = response.text
            
            # Get player domain
            domain_match = re.search(r"AwsIndStreamDomain.*?['\"]([^'\"]+)['\"]", html)
            player_domain = domain_match.group(1) if domain_match else "aws.indstream.xyz"
            
            # Get video ID
            video_match = re.search(r"src:\s*['\"]([^'\"]+)['\"]", html)
            video_id = video_match.group(1) if video_match else None
            
            return {
                'player_domain': player_domain,
                'video_id': video_id
            }
        except Exception as e:
            print(f"Extract error: {e}")
            return None

    def get_embed_data(self, player_domain, video_id, referer):
        try:
            embed_url = f"https://{player_domain}/play/{video_id}"
            response = self.session.get(embed_url, headers={'Referer': referer}, timeout=10)
            
            if response.status_code != 200:
                return None

            json_match = re.search(r'(\{.*?\})', response.text)
            if json_match:
                return json.loads(json_match.group(1))
            return None
        except Exception as e:
            print(f"Embed error: {e}")
            return None

    def get_m3u8_content(self, player_domain, file_path, token):
        try:
            m3u8_url = f"https://{player_domain}/playlist/{file_path}.txt"
            headers = {'Referer': BASE_URL + '/'}
            if token:
                headers['X-CSRF-TOKEN'] = token
            
            response = self.session.post(m3u8_url, headers=headers, timeout=10)
            return response.text if response.status_code == 200 else None
        except Exception as e:
            print(f"M3U8 error: {e}")
            return None

m3u8_handler = AllMovieLandM3U8()

@app.route('/')
def home():
    return jsonify({
        "message": "AllMovieLand M3U8 Proxy - FULL WORKING VERSION",
        "status": "active",
        "endpoints": {
            "health": "/health",
            "test_avengers": "/m3u8?url=https://allmovieland.ac/3101-the-avengers.html",
            "m3u8": "/m3u8?url=CONTENT_URL",
            "direct": "/direct?file=FILE&domain=DOMAIN&token=TOKEN"
        }
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time()
    })

@app.route('/debug')
def debug_url():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter required"}), 400
    
    m3u8_handler.get_cookies()
    video_data = m3u8_handler.extract_video_data(content_url)
    
    if video_data:
        return jsonify({
            "success": True,
            "data": video_data
        })
    else:
        return jsonify({"error": "Debug failed"}), 500

@app.route('/m3u8')
def get_m3u8_links():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter required"}), 400
    
    m3u8_handler.get_cookies()
    
    # Step 1: Extract video data
    video_data = m3u8_handler.extract_video_data(content_url)
    if not video_data or not video_data.get('video_id'):
        return jsonify({"error": "No video data found"}), 500
    
    player_domain = video_data['player_domain']
    video_id = video_data['video_id']
    
    # Step 2: Get embed data
    embed_data = m3u8_handler.get_embed_data(player_domain, video_id, content_url)
    if not embed_data or not embed_data.get('file'):
        return jsonify({"error": "No embed data found"}), 500
    
    file_path = embed_data['file']
    token = embed_data.get('key', '')
    
    # Step 3: Get M3U8 content
    m3u8_content = m3u8_handler.get_m3u8_content(player_domain, file_path, token)
    if not m3u8_content:
        return jsonify({"error": "No M3U8 content found"}), 500
    
    return jsonify({
        "success": True,
        "content_url": content_url,
        "player_domain": player_domain,
        "file_path": file_path,
        "m3u8_content": m3u8_content,
        "direct_url": f"/direct?file={file_path}&domain={player_domain}&token={token}"
    })

@app.route('/direct')
def direct_m3u8():
    file_path = request.args.get('file')
    player_domain = request.args.get('domain')
    token = request.args.get('token', '')
    
    if not file_path or not player_domain:
        return jsonify({"error": "Missing parameters"}), 400
    
    m3u8_content = m3u8_handler.get_m3u8_content(player_domain, file_path, token)
    if m3u8_content:
        return Response(m3u8_content, mimetype='application/vnd.apple.mpegurl')
    else:
        return jsonify({"error": "M3U8 fetch failed"}), 500

@app.route('/test')
def test():
    return jsonify({
        "message": "All systems working!",
        "test_url": "https://workss-epyp.onrender.com/m3u8?url=https://allmovieland.ac/3101-the-avengers.html"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
