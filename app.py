from flask import Flask, request, jsonify, Response
import requests
import re
import json
import time
import os
from flask_cors import CORS
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

class AllMovieLandM3U8:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.token_key = ""

    def get_dl_json(self, player_url):
        """Extract JSON data from player page and get M3U8 data"""
        try:
            print(f"🎬 Processing player URL: {player_url}")
            
            # Get the player page
            response = self.session.get(player_url)
            if response.status_code != 200:
                return None

            # Extract JSON from script
            json_match = re.search(r'(\{.*?\})', response.text)
            if not json_match:
                return None
                
            json_data = json.loads(json_match.group(1))
            self.token_key = json_data.get('key', '')
            
            # Get base URL for relative paths
            base_url = self.get_base_url(player_url)
            
            # Build file URL
            file_url = json_data['file']
            if not file_url.startswith('http'):
                file_url = base_url + file_url
                
            print(f"📁 File URL: {file_url}")
            print(f"🔑 Token: {self.token_key}")
            
            # Get M3U8 data
            m3u8_response = self.session.post(
                file_url,
                headers={
                    'X-CSRF-TOKEN': self.token_key,
                    'Referer': player_url
                }
            )
            
            result = m3u8_response.text.replace(', []', '')
            print(f"✅ Got M3U8 data, length: {len(result)}")
            return result
            
        except Exception as e:
            print(f"❌ DL JSON error: {e}")
            return None

    def get_base_url(self, url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def get_m3u8_content(self, player_domain, file_path):
        """Get actual M3U8 content"""
        try:
            m3u8_url = f"https://{player_domain}/playlist/{file_path}.txt"
            print(f"📺 Fetching M3U8 from: {m3u8_url}")
            
            headers = {
                'Referer': player_domain + "/"
            }
            if self.token_key:
                headers['X-CSRF-TOKEN'] = self.token_key
            
            response = self.session.post(m3u8_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ M3U8 fetched successfully")
                return response.text
            else:
                print(f"❌ M3U8 fetch failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ M3U8 error: {e}")
            return None

    def extract_player_domain(self, player_url):
        """Extract player domain from URL"""
        parsed = urlparse(player_url)
        return parsed.netloc

m3u8_handler = AllMovieLandM3U8()

@app.route('/')
def home():
    return jsonify({
        "message": "AllMovieLand Player M3U8 Extractor",
        "status": "active", 
        "usage": "Use /m3u8?url=PLAYER_URL (like https://hurry379dec.com/play/tt31307640)",
        "example": "/m3u8?url=https://hurry379dec.com/play/tt31307640"
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time()
    })

@app.route('/m3u8')
def get_m3u8():
    player_url = request.args.get('url', '').strip()
    if not player_url:
        return jsonify({"error": "URL parameter required"}), 400
    
    # Fix double slash in URL if present
    player_url = player_url.replace('//play/', '/play/')
    
    print(f"🎯 Processing: {player_url}")
    
    # Get JSON data from player
    json_data = m3u8_handler.get_dl_json(player_url)
    if not json_data:
        return jsonify({"error": "Failed to extract data from player URL"}), 500
    
    try:
        # Parse JSON data
        parsed_data = json.loads(json_data)
        m3u8_links = []
        player_domain = m3u8_handler.extract_player_domain(player_url)
        
        # Handle different JSON structures
        if isinstance(parsed_data, list):
            # List of video files
            for item in parsed_data:
                if item.get('file'):
                    m3u8_content = m3u8_handler.get_m3u8_content(player_domain, item['file'])
                    if m3u8_content:
                        m3u8_links.append({
                            'title': item.get('title', 'Video'),
                            'file': item['file'],
                            'quality': item.get('quality', 'Unknown'),
                            'm3u8_url': f"/direct?file={item['file']}&domain={player_domain}",
                            'm3u8_content': m3u8_content
                        })
        elif isinstance(parsed_data, dict):
            # Single video object
            if parsed_data.get('file'):
                m3u8_content = m3u8_handler.get_m3u8_content(player_domain, parsed_data['file'])
                if m3u8_content:
                    m3u8_links.append({
                        'title': parsed_data.get('title', 'Video'),
                        'file': parsed_data['file'],
                        'quality': 'Unknown',
                        'm3u8_url': f"/direct?file={parsed_data['file']}&domain={player_domain}",
                        'm3u8_content': m3u8_content
                    })
        
        if m3u8_links:
            return jsonify({
                "success": True,
                "player_url": player_url,
                "player_domain": player_domain,
                "token_key": m3u8_handler.token_key,
                "m3u8_streams_found": len(m3u8_links),
                "m3u8_streams": m3u8_links
            })
        else:
            return jsonify({"error": "No M3U8 streams found in the data"}), 500
            
    except Exception as e:
        return jsonify({"error": f"JSON parsing error: {str(e)}"}), 500

@app.route('/direct')
def direct_m3u8():
    file_path = request.args.get('file')
    player_domain = request.args.get('domain')
    
    if not file_path or not player_domain:
        return jsonify({"error": "File and domain parameters required"}), 400
    
    m3u8_content = m3u8_handler.get_m3u8_content(player_domain, file_path)
    if m3u8_content:
        return Response(m3u8_content, mimetype='application/vnd.apple.mpegurl', headers={
            'Content-Type': 'application/vnd.apple.mpegurl',
            'Access-Control-Allow-Origin': '*'
        })
    else:
        return jsonify({"error": "Failed to get M3U8 content"}), 500

@app.route('/debug')
def debug():
    player_url = request.args.get('url', '').strip()
    if not player_url:
        return jsonify({"error": "URL parameter required"}), 400
    
    player_url = player_url.replace('//play/', '/play/')
    
    json_data = m3u8_handler.get_dl_json(player_url)
    
    if json_data:
        return jsonify({
            "success": True,
            "player_url": player_url,
            "player_domain": m3u8_handler.extract_player_domain(player_url),
            "token_key": m3u8_handler.token_key,
            "json_data_available": True,
            "json_data_length": len(json_data),
            "json_data_preview": json_data[:500] + "..." if len(json_data) > 500 else json_data
        })
    else:
        return jsonify({"error": "Failed to extract data from player URL"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
