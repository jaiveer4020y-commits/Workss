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

BASE_URL = "https://allmovieland.ac"

class AllMovieLandM3U8:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.cookies = {}
        self.player_domain = ""
        self.token_key = ""

    def get_cookies(self):
        try:
            response = self.session.get(BASE_URL)
            if 'PHPSESSID' in response.cookies:
                self.cookies = {'PHPSESSID': response.cookies['PHPSESSID']}
                return True
            return False
        except Exception as e:
            print(f"Cookie error: {e}")
            return False

    def get_base_url(self, url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def get_dl_json(self, link, referer_url):
        try:
            baseurl = self.get_base_url(link)
            response = self.session.get(link, headers={'Referer': referer_url})
            
            # Extract JSON from script like in Kotlin code
            script_text = response.text
            json_match = re.search(r'(\{.*\})', script_text)
            if not json_match:
                return None
                
            json_data = json.loads(json_match.group(1))
            self.token_key = json_data.get('key', '')
            
            json_file = json_data['file'] if json_data['file'].startswith('http') else baseurl + json_data['file']
            
            # Get M3U8 languages data
            m3u8_response = self.session.post(
                json_file,
                headers={
                    'X-CSRF-TOKEN': self.token_key,
                    'Referer': link
                }
            )
            
            return m3u8_response.text.replace(', []', '')
            
        except Exception as e:
            print(f"DL JSON error: {e}")
            return None

    def get_m3u8_content(self, file_path):
        try:
            if not self.player_domain or not self.token_key:
                return None
                
            m3u8_url = f"{self.player_domain}/playlist/{file_path}.txt"
            response = self.session.post(
                m3u8_url,
                headers={
                    'X-CSRF-TOKEN': self.token_key,
                    'Referer': BASE_URL + "/"
                }
            )
            return response.text if response.status_code == 200 else None
        except Exception as e:
            print(f"M3U8 error: {e}")
            return None

    def extract_video_data(self, content_url):
        try:
            response = self.session.get(content_url)
            if response.status_code != 200:
                return None

            html = response.text
            
            # Extract player domain exactly like in Kotlin
            domain_match = re.search(r"const AwsIndStreamDomain.*?'(.*?)';", html)
            if domain_match:
                self.player_domain = domain_match.group(1)
            else:
                return None

            # Extract video ID like in Kotlin
            script_section = re.search(r'script[^>]*>(.*?)</script>', html, re.DOTALL)
            if script_section:
                script_content = script_section.group(1)
                id_match = re.search(r"src:.?'([^']+)", script_content)
                video_id = id_match.group(1) if id_match else None
                
                if video_id:
                    embed_link = f"{self.player_domain}/play/{video_id}"
                    json_data = self.get_dl_json(embed_link, content_url)
                    return {
                        'video_id': video_id,
                        'embed_link': embed_link,
                        'json_data': json_data,
                        'player_domain': self.player_domain
                    }
            
            return None
            
        except Exception as e:
            print(f"Extract error: {e}")
            return None

m3u8_handler = AllMovieLandM3U8()

# Data classes matching your Kotlin code
class Extract:
    def __init__(self, title=None, id=None, file=None):
        self.title = title
        self.id = id
        self.file = file

class Seasons:
    def __init__(self, title=None, id=None, folder=None):
        self.title = title
        self.id = id
        self.folder = folder or []

class Episodes:
    def __init__(self, episode=None, title=None, id=None, folder=None):
        self.episode = episode
        self.title = title
        self.id = id
        self.folder = folder or []

class Files:
    def __init__(self, file=None, end_tag=None, title=None, id=None):
        self.file = file
        self.end_tag = end_tag
        self.title = title
        self.id = id

@app.route('/')
def home():
    return jsonify({
        "message": "AllMovieLand M3U8 - EXACT KOTLIN LOGIC",
        "status": "active",
        "endpoints": {
            "health": "/health",
            "m3u8": "/m3u8?url=CONTENT_URL",
            "test_avengers": "/m3u8?url=https://allmovieland.ac/3101-the-avengers.html",
            "direct": "/direct?file=FILE_PATH"
        }
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "cookies_set": bool(m3u8_handler.cookies)
    })

@app.route('/m3u8')
def get_m3u8():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter required"}), 400
    
    # Get cookies first
    m3u8_handler.get_cookies()
    
    # Extract video data using exact Kotlin logic
    video_data = m3u8_handler.extract_video_data(content_url)
    if not video_data:
        return jsonify({"error": "Failed to extract video data"}), 500
    
    json_data = video_data['json_data']
    player_domain = video_data['player_domain']
    
    if not json_data:
        return jsonify({"error": "No JSON data received"}), 500
    
    try:
        # Parse JSON data like in Kotlin
        m3u8_links = []
        
        if "folder" in json_data.lower():
            # TV Series with seasons
            seasons_data = json.loads(json_data)
            for season in seasons_data:
                season_num = int(season['id']) if season['id'].isdigit() else 1
                for episode in season['folder']:
                    episode_num = int(episode['episode']) if episode['episode'].isdigit() else 1
                    for file_obj in episode['folder']:
                        if file_obj['file']:
                            m3u8_content = m3u8_handler.get_m3u8_content(file_obj['file'])
                            if m3u8_content:
                                m3u8_links.append({
                                    'title': f"S{season_num}E{episode_num} - {file_obj.get('title', 'Episode')}",
                                    'file': file_obj['file'],
                                    'season': season_num,
                                    'episode': episode_num,
                                    'm3u8_content': m3u8_content
                                })
        else:
            # Movie format
            movies_data = json.loads(json_data)
            for movie in movies_data:
                if movie.get('file'):
                    m3u8_content = m3u8_handler.get_m3u8_content(movie['file'])
                    if m3u8_content:
                        m3u8_links.append({
                            'title': movie.get('title', 'Movie'),
                            'file': movie['file'],
                            'm3u8_content': m3u8_content
                        })
        
        if m3u8_links:
            return jsonify({
                "success": True,
                "content_url": content_url,
                "player_domain": player_domain,
                "token_key": m3u8_handler.token_key,
                "m3u8_streams": m3u8_links
            })
        else:
            return jsonify({"error": "No M3U8 streams found"}), 500
            
    except Exception as e:
        return jsonify({"error": f"JSON parsing error: {str(e)}"}), 500

@app.route('/direct')
def direct_m3u8():
    file_path = request.args.get('file')
    if not file_path:
        return jsonify({"error": "File parameter required"}), 400
    
    m3u8_content = m3u8_handler.get_m3u8_content(file_path)
    if m3u8_content:
        return Response(m3u8_content, mimetype='application/vnd.apple.mpegurl')
    else:
        return jsonify({"error": "Failed to get M3U8"}), 500

@app.route('/debug')
def debug():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter required"}), 400
    
    m3u8_handler.get_cookies()
    video_data = m3u8_handler.extract_video_data(content_url)
    
    if video_data:
        return jsonify({
            "success": True,
            "player_domain": m3u8_handler.player_domain,
            "token_key": m3u8_handler.token_key,
            "video_id": video_data.get('video_id'),
            "embed_link": video_data.get('embed_link'),
            "json_data_preview": video_data.get('json_data', '')[:200] + "..." if video_data.get('json_data') else None
        })
    else:
        return jsonify({"error": "Debug failed"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
