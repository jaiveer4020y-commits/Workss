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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
                self.session.cookies.update(self.cookies)
                print("✅ Cookies set successfully")
                return True
            return False
        except Exception as e:
            print(f"❌ Cookie error: {e}")
            return False

    def get_base_url(self, url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def get_dl_json(self, link, referer_url):
        try:
            print(f"🔗 Getting DL JSON from: {link}")
            baseurl = self.get_base_url(link)
            response = self.session.get(link, headers={'Referer': referer_url})
            
            # Extract JSON from script - EXACT Kotlin logic
            script_elements = re.findall(r'<script[^>]*>(.*?)</script>', response.text, re.DOTALL)
            json_string = None
            
            for script in script_elements:
                if 'src' in script and 'file' in script:
                    json_match = re.search(r'(\{.*\})', script)
                    if json_match:
                        json_string = json_match.group(1)
                        break
            
            if not json_string:
                print("❌ No JSON found in scripts")
                return None
                
            print(f"📄 Raw JSON found: {json_string[:100]}...")
            json_data = json.loads(json_string)
            self.token_key = json_data.get('key', '')
            
            # Build file URL like Kotlin
            file_url = json_data['file']
            if not file_url.startswith('http'):
                file_url = baseurl + file_url
                
            print(f"📁 File URL: {file_url}")
            print(f"🔑 Token Key: {self.token_key}")
            
            # Get M3U8 languages data
            m3u8_response = self.session.post(
                file_url,
                headers={
                    'X-CSRF-TOKEN': self.token_key,
                    'Referer': link
                }
            )
            
            result = m3u8_response.text.replace(', []', '')
            print(f"✅ DL JSON success, length: {len(result)}")
            return result
            
        except Exception as e:
            print(f"❌ DL JSON error: {e}")
            return None

    def extract_video_data(self, content_url):
        try:
            print(f"🎬 Extracting from: {content_url}")
            response = self.session.get(content_url)
            
            if response.status_code != 200:
                print(f"❌ HTTP Error: {response.status_code}")
                return None

            html = response.text
            
            # Extract player domain EXACTLY like Kotlin
            domain_match = re.search(r"const AwsIndStreamDomain\s*=\s*['\"]([^'\"]+)['\"]", html)
            if domain_match:
                self.player_domain = domain_match.group(1)
                print(f"🌐 Player Domain: {self.player_domain}")
            else:
                print("❌ No player domain found")
                # Try fallback domain
                self.player_domain = "aws.indstream.xyz"
                print(f"🌐 Using fallback domain: {self.player_domain}")

            # Extract video ID like Kotlin - from script tags
            script_sections = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
            video_id = None
            
            for script in script_sections:
                # Look for pattern: src: 'SOME_ID'
                id_match = re.search(r"src:\s*['\"]([^'\"]+)['\"]", script)
                if id_match:
                    video_id = id_match.group(1)
                    print(f"🎥 Video ID found: {video_id}")
                    break
            
            if not video_id:
                print("❌ No video ID found in scripts")
                # Try alternative patterns
                alt_match = re.search(r"video-id\s*:\s*['\"]([^'\"]+)['\"]", html)
                if alt_match:
                    video_id = alt_match.group(1)
                    print(f"🎥 Alternative Video ID: {video_id}")
                else:
                    return None
            
            # Build embed link and get JSON data
            embed_link = f"https://{self.player_domain}/play/{video_id}"
            print(f"🔗 Embed Link: {embed_link}")
            
            json_data = self.get_dl_json(embed_link, content_url)
            
            return {
                'video_id': video_id,
                'embed_link': embed_link,
                'json_data': json_data,
                'player_domain': self.player_domain,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ Extraction error: {e}")
            return None

    def get_m3u8_content(self, file_path):
        try:
            if not self.player_domain:
                print("❌ No player domain set")
                return None
                
            m3u8_url = f"https://{self.player_domain}/playlist/{file_path}.txt"
            print(f"📺 Fetching M3U8 from: {m3u8_url}")
            
            headers = {
                'Referer': BASE_URL + "/"
            }
            if self.token_key:
                headers['X-CSRF-TOKEN'] = self.token_key
            
            response = self.session.post(m3u8_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ M3U8 fetched successfully, length: {len(response.text)}")
                return response.text
            else:
                print(f"❌ M3U8 fetch failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ M3U8 error: {e}")
            return None

m3u8_handler = AllMovieLandM3U8()

@app.route('/')
def home():
    return jsonify({
        "message": "AllMovieLand M3U8 - EXACT KOTLIN LOGIC",
        "status": "active", 
        "endpoints": {
            "health": "/health",
            "m3u8": "/m3u8?url=CONTENT_URL",
            "debug": "/debug?url=CONTENT_URL",
            "test_avengers": "/m3u8?url=https://allmovieland.ac/3101-the-avengers.html"
        }
    })

@app.route('/health')
def health_check():
    m3u8_handler.get_cookies()
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "cookies_set": bool(m3u8_handler.cookies),
        "player_domain": m3u8_handler.player_domain
    })

@app.route('/debug')
def debug():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter required"}), 400
    
    print(f"🔧 DEBUG: Processing {content_url}")
    m3u8_handler.get_cookies()
    
    video_data = m3u8_handler.extract_video_data(content_url)
    
    if video_data:
        return jsonify({
            "success": True,
            "player_domain": m3u8_handler.player_domain,
            "token_key": m3u8_handler.token_key,
            "video_id": video_data.get('video_id'),
            "embed_link": video_data.get('embed_link'),
            "json_data_available": bool(video_data.get('json_data')),
            "json_data_length": len(video_data.get('json_data', '')),
            "json_data_preview": video_data.get('json_data', '')[:500] + "..." if video_data.get('json_data') else None
        })
    else:
        return jsonify({
            "error": "Extraction failed",
            "suggestions": [
                "Check if the URL is accessible",
                "Verify the movie exists on AllMovieLand",
                "The site structure might have changed"
            ]
        })

@app.route('/m3u8')
def get_m3u8():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter required"}), 400
    
    print(f"🎯 M3U8 REQUEST: {content_url}")
    m3u8_handler.get_cookies()
    
    video_data = m3u8_handler.extract_video_data(content_url)
    if not video_data:
        return jsonify({"error": "Failed to extract video data - check debug endpoint"}), 500
    
    json_data = video_data['json_data']
    if not json_data:
        return jsonify({"error": "No JSON data received from embed"}), 500
    
    try:
        # Parse the JSON data
        parsed_data = json.loads(json_data)
        m3u8_links = []
        
        # Check if it's a movie or series
        if isinstance(parsed_data, list):
            # Movie format - list of files
            for item in parsed_data:
                if item.get('file'):
                    m3u8_content = m3u8_handler.get_m3u8_content(item['file'])
                    if m3u8_content:
                        m3u8_links.append({
                            'title': item.get('title', 'Movie'),
                            'file': item['file'],
                            'quality': 'Unknown',
                            'm3u8_url': f"/direct?file={item['file']}",
                            'm3u8_content_preview': m3u8_content[:100] + "..." if len(m3u8_content) > 100 else m3u8_content
                        })
        else:
            # TV Series format with seasons
            if 'folder' in parsed_data:
                for season in parsed_data['folder']:
                    season_num = season.get('id', '1')
                    for episode in season.get('folder', []):
                        episode_num = episode.get('episode', '1')
                        for file_obj in episode.get('folder', []):
                            if file_obj.get('file'):
                                m3u8_content = m3u8_handler.get_m3u8_content(file_obj['file'])
                                if m3u8_content:
                                    m3u8_links.append({
                                        'title': f"S{season_num}E{episode_num} - {file_obj.get('title', 'Episode')}",
                                        'file': file_obj['file'],
                                        'season': season_num,
                                        'episode': episode_num,
                                        'm3u8_url': f"/direct?file={file_obj['file']}",
                                        'm3u8_content_preview': m3u8_content[:100] + "..." if len(m3u8_content) > 100 else m3u8_content
                                    })
        
        if m3u8_links:
            return jsonify({
                "success": True,
                "content_url": content_url,
                "player_domain": m3u8_handler.player_domain,
                "token_key": m3u8_handler.token_key,
                "m3u8_streams_found": len(m3u8_links),
                "m3u8_streams": m3u8_links
            })
        else:
            return jsonify({"error": "No M3U8 streams found in JSON data"}), 500
            
    except Exception as e:
        return jsonify({"error": f"JSON parsing error: {str(e)}", "raw_json": json_data[:500]}), 500

@app.route('/direct')
def direct_m3u8():
    file_path = request.args.get('file')
    if not file_path:
        return jsonify({"error": "File parameter required"}), 400
    
    m3u8_content = m3u8_handler.get_m3u8_content(file_path)
    if m3u8_content:
        return Response(m3u8_content, mimetype='application/vnd.apple.mpegurl')
    else:
        return jsonify({"error": "Failed to get M3U8 content"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
