from flask import Flask, request, jsonify, Response
import requests
import re
import json
from urllib.parse import urlparse
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)

# Configuration
BASE_URL = "https://allmovieland.ac"
PLAYER_DOMAIN = None
TOKEN_KEY = None

class AllMovieLandM3U8:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': BASE_URL + '/'
        })

    def get_cookies(self):
        """Get initial cookies from the main site"""
        try:
            response = self.session.get(BASE_URL)
            return True
        except Exception as e:
            print(f"Error getting cookies: {e}")
            return False

    def search_content(self, query):
        """Search for movies/TV shows"""
        try:
            form_data = {
                'do': 'search',
                'subaction': 'search',
                'search_start': '0',
                'full_search': '0',
                'result_from': '1',
                'story': query
            }
            
            response = self.session.post(
                f"{BASE_URL}/index.php?do=opensearch",
                data=form_data,
                headers={'Referer': BASE_URL + '/'}
            )
            
            return response.text
        except Exception as e:
            print(f"Search error: {e}")
            return None

    def get_video_data(self, content_url):
        """Get video data from content page"""
        try:
            response = self.session.get(content_url)
            html_content = response.text
            
            # Extract player domain
            domain_match = re.search(r"const AwsIndStreamDomain.*?'(.*?)';", html_content)
            global PLAYER_DOMAIN
            if domain_match:
                PLAYER_DOMAIN = domain_match.group(1)
                print(f"Found player domain: {PLAYER_DOMAIN}")
            
            # Extract script data containing video ID
            script_section = re.search(r'script[^>]*>(.*?)</script>', html_content, re.DOTALL)
            if script_section:
                script_content = script_section.group(1)
                video_id_match = re.search(r"src:\s*['\"]([^'\"]+)['\"]", script_content)
                if video_id_match:
                    video_id = video_id_match.group(1)
                    return self.get_download_json(video_id, content_url)
            
            return None
        except Exception as e:
            print(f"Error getting video data: {e}")
            return None

    def get_download_json(self, video_id, referer_url):
        """Get download JSON data"""
        try:
            embed_url = f"https://{PLAYER_DOMAIN}/play/{video_id}"
            
            response = self.session.get(embed_url, headers={'Referer': referer_url})
            html_content = response.text
            
            # Extract JSON from script
            json_match = re.search(r'(\{.*\})', html_content)
            if json_match:
                json_str = json_match.group(1)
                json_data = json.loads(json_str)
                
                # Get the file URL
                file_url = json_data.get('file', '')
                if file_url and not file_url.startswith('http'):
                    base_domain = self.get_base_url(embed_url)
                    file_url = base_domain + file_url
                
                # Get token key
                global TOKEN_KEY
                TOKEN_KEY = json_data.get('key', '')
                
                if file_url:
                    # Get M3U8 data
                    response = self.session.post(
                        file_url,
                        headers={
                            'X-CSRF-TOKEN': TOKEN_KEY,
                            'Referer': embed_url
                        }
                    )
                    
                    cleaned_data = response.text.replace(', []', '')
                    return cleaned_data
                
            return None
        except Exception as e:
            print(f"Error getting download JSON: {e}")
            return None

    def get_m3u8_content(self, file_path):
        """Get M3U8 content"""
        try:
            if not PLAYER_DOMAIN or not TOKEN_KEY:
                return None
                
            m3u8_url = f"https://{PLAYER_DOMAIN}/playlist/{file_path}.txt"
            
            response = self.session.post(
                m3u8_url,
                headers={
                    'X-CSRF-TOKEN': TOKEN_KEY,
                    'Referer': BASE_URL + '/'
                }
            )
            
            return response.text
        except Exception as e:
            print(f"Error getting M3U8: {e}")
            return None

    def get_base_url(self, url):
        """Extract base URL from full URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

# Initialize the M3U8 handler
m3u8_handler = AllMovieLandM3U8()

@app.route('/')
def home():
    return jsonify({
        "message": "AllMovieLand M3U8 Proxy Server",
        "status": "active",
        "endpoints": {
            "search": "/search?query=movie_name",
            "get_m3u8": "/m3u8?url=content_url",
            "health": "/health"
        },
        "usage": "Use /search to find content, then /m3u8 with the content URL to get M3U8 links"
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy", 
        "timestamp": time.time(),
        "base_url": BASE_URL
    })

@app.route('/search')
def search_content():
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    
    # Ensure we have cookies
    m3u8_handler.get_cookies()
    
    result = m3u8_handler.search_content(query)
    if result:
        return Response(result, mimetype='text/html')
    else:
        return jsonify({"error": "Search failed"}), 500

@app.route('/m3u8')
def get_m3u8_links():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    # Ensure we have cookies
    m3u8_handler.get_cookies()
    
    video_data = m3u8_handler.get_video_data(content_url)
    if video_data:
        try:
            # Parse the video data to extract M3U8 files
            videos = json.loads(video_data)
            m3u8_results = []
            
            if isinstance(videos, list):
                # Handle movie format
                for video in videos:
                    if video.get('file'):
                        m3u8_content = m3u8_handler.get_m3u8_content(video['file'])
                        if m3u8_content:
                            m3u8_results.append({
                                'title': video.get('title', 'Unknown'),
                                'file': video.get('file'),
                                'm3u8_url': f"/proxy_m3u8?file={video['file']}",
                                'quality': 'Unknown'
                            })
            
            return jsonify({
                "success": True,
                "content_url": content_url,
                "player_domain": PLAYER_DOMAIN,
                "m3u8_links": m3u8_results
            })
            
        except json.JSONDecodeError as e:
            return jsonify({
                "error": f"Failed to parse video data: {str(e)}",
                "raw_data": video_data[:500] + "..." if len(video_data) > 500 else video_data
            }), 500
        except Exception as e:
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
    else:
        return jsonify({"error": "Failed to get video data from the provided URL"}), 500

@app.route('/proxy_m3u8')
def proxy_m3u8_file():
    """Proxy individual M3U8 files"""
    file_path = request.args.get('file')
    if not file_path:
        return jsonify({"error": "File parameter is required"}), 400
    
    m3u8_content = m3u8_handler.get_m3u8_content(file_path)
    if m3u8_content:
        return Response(m3u8_content, mimetype='application/vnd.apple.mpegurl')
    else:
        return jsonify({"error": "Failed to get M3U8 content"}), 500

@app.route('/direct')
def direct_m3u8():
    """Direct M3U8 access with file path"""
    file_path = request.args.get('file')
    player_domain = request.args.get('domain')
    token = request.args.get('token')
    
    if not all([file_path, player_domain, token]):
        return jsonify({"error": "File, domain, and token parameters are required"}), 400
    
    try:
        m3u8_url = f"https://{player_domain}/playlist/{file_path}.txt"
        
        response = m3u8_handler.session.post(
            m3u8_url,
            headers={
                'X-CSRF-TOKEN': token,
                'Referer': BASE_URL + '/'
            }
        )
        
        if response.status_code == 200:
            return Response(response.content, mimetype='application/vnd.apple.mpegurl')
        else:
            return jsonify({"error": f"Failed to fetch M3U8: {response.status_code}"}), response.status_code
            
    except Exception as e:
        return jsonify({"error": f"Proxy error: {str(e)}"}), 500

if __name__ == '__main__':
    # Initialize cookies on startup
    m3u8_handler.get_cookies()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
