from flask import Flask, request, jsonify, Response
import requests
import re
import json
from urllib.parse import urlparse
from flask_cors import CORS
import time
import os

app = Flask(__name__)
CORS(app)

# Configuration
BASE_URL = "https://allmovieland.ac"

class AllMovieLandM3U8:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def get_cookies(self):
        """Get initial cookies from the main site"""
        try:
            response = self.session.get(BASE_URL, timeout=10)
            print(f"Cookies established: PHPSESSID = {self.session.cookies.get('PHPSESSID')}")
            return True
        except Exception as e:
            print(f"Error getting cookies: {e}")
            return False

    def extract_video_data(self, content_url):
        """Extract video data from content page"""
        try:
            print(f"Extracting video data from: {content_url}")
            
            response = self.session.get(content_url, timeout=10)
            
            if response.status_code != 200:
                print(f"Failed to fetch page: Status {response.status_code}")
                return None

            html_content = response.text
            
            # Method 1: Extract player domain
            domain_match = re.search(r"const AwsIndStreamDomain\s*=\s*['\"]([^'\"]+)['\"]", html_content)
            player_domain = domain_match.group(1) if domain_match else None
            print(f"Player Domain: {player_domain}")

            # Method 2: Extract video ID from scripts
            video_sources = []
            
            # Look for various script patterns
            script_patterns = [
                r'src\s*:\s*[\'"]([^\'"]+)[\'"]',
                r'video-id[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]',
                r'file\s*:\s*[\'"]([^\'"]+)[\'"]',
            ]
            
            for pattern in script_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    video_sources.extend(matches)
                    print(f"Found video sources: {matches}")

            # Method 3: Look for iframe embeds
            iframe_matches = re.findall(r'<iframe[^>]*src=[\'"]([^\'"]+)[\'"]', html_content)
            for iframe_src in iframe_matches:
                if 'player' in iframe_src or 'embed' in iframe_src:
                    video_sources.append(iframe_src)
                    print(f"Found iframe source: {iframe_src}")

            print(f"Total video sources found: {len(video_sources)}")
            
            if player_domain and video_sources:
                return {
                    'player_domain': player_domain,
                    'video_sources': video_sources
                }
            else:
                print("No video sources found")
                return None

        except Exception as e:
            print(f"Error extracting video data: {e}")
            return None

    def get_embed_data(self, player_domain, video_source, referer_url):
        """Get data from embed/player page"""
        try:
            # Construct embed URL
            if video_source.startswith('http'):
                embed_url = video_source
            else:
                embed_url = f"https://{player_domain}/play/{video_source}"
            
            print(f"Accessing embed URL: {embed_url}")
            
            response = self.session.get(embed_url, headers={'Referer': referer_url}, timeout=10)
            
            if response.status_code != 200:
                print(f"Failed to fetch embed: Status {response.status_code}")
                return None

            # Look for JSON data in script
            json_match = re.search(r'(\{.*?\})', response.text)
            if json_match:
                try:
                    json_data = json.loads(json_match.group(1))
                    print(f"Found JSON data: {list(json_data.keys())}")
                    return json_data
                except json.JSONDecodeError:
                    print("Failed to parse JSON data")
            
            return None
            
        except Exception as e:
            print(f"Error getting embed data: {e}")
            return None

    def get_m3u8_content(self, player_domain, file_path, token):
        """Get M3U8 content"""
        try:
            m3u8_url = f"https://{player_domain}/playlist/{file_path}.txt"
            print(f"Fetching M3U8 from: {m3u8_url}")
            
            headers = {
                'Referer': BASE_URL + '/'
            }
            
            if token:
                headers['X-CSRF-TOKEN'] = token
            
            response = self.session.post(m3u8_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print("Successfully fetched M3U8 content")
                return response.text
            else:
                print(f"Failed to fetch M3U8: Status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error getting M3U8 content: {e}")
            return None

# Initialize the M3U8 handler
m3u8_handler = AllMovieLandM3U8()

@app.route('/')
def home():
    return jsonify({
        "message": "AllMovieLand M3U8 Proxy Server - FIXED",
        "status": "active",
        "endpoints": {
            "test_avengers": "/m3u8?url=https://allmovieland.ac/3101-the-avengers.html",
            "debug": "/debug?url=content_url",
            "health": "/health"
        }
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy", 
        "timestamp": time.time(),
        "base_url": BASE_URL
    })

@app.route('/debug')
def debug_url():
    """Debug endpoint to see what data we can extract"""
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    print(f"Debugging URL: {content_url}")
    m3u8_handler.get_cookies()
    
    video_data = m3u8_handler.extract_video_data(content_url)
    if video_data:
        return jsonify({
            "success": True,
            "debug_info": video_data
        })
    else:
        return jsonify({
            "error": "No video data found",
            "suggestions": [
                "Check if the URL is accessible",
                "Verify the movie exists",
                "Try a different content URL"
            ]
        })

@app.route('/m3u8')
def get_m3u8_links():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    print(f"Processing M3U8 request for: {content_url}")
    
    # Ensure we have cookies
    m3u8_handler.get_cookies()
    
    # Extract video data
    video_data = m3u8_handler.extract_video_data(content_url)
    if not video_data:
        return jsonify({
            "error": "Failed to extract video data from the URL",
            "debug_suggestion": "Use /debug endpoint to see what data is available"
        }), 500
    
    player_domain = video_data['player_domain']
    video_sources = video_data['video_sources']
    
    m3u8_results = []
    
    # Try each video source
    for source in video_sources[:3]:
        print(f"Trying source: {source}")
        
        embed_data = m3u8_handler.get_embed_data(player_domain, source, content_url)
        if embed_data and embed_data.get('file'):
            file_path = embed_data['file']
            token = embed_data.get('key', '')
            
            m3u8_content = m3u8_handler.get_m3u8_content(player_domain, file_path, token)
            if m3u8_content:
                m3u8_results.append({
                    'title': f"Source - {source[:20]}...",
                    'file': file_path,
                    'player_domain': player_domain,
                    'token': token,
                    'm3u8_content_preview': m3u8_content[:100] + "..." if len(m3u8_content) > 100 else m3u8_content
                })
    
    if m3u8_results:
        return jsonify({
            "success": True,
            "content_url": content_url,
            "player_domain": player_domain,
            "sources_found": len(video_sources),
            "m3u8_streams": m3u8_results
        })
    else:
        return jsonify({
            "error": "No M3U8 streams found",
            "debug_info": {
                "player_domain": player_domain,
                "video_sources_found": video_sources
            }
        })

@app.route('/direct')
def direct_m3u8():
    """Direct M3U8 access"""
    file_path = request.args.get('file')
    player_domain = request.args.get('domain')
    token = request.args.get('token')
    
    if not all([file_path, player_domain]):
        return jsonify({"error": "File and domain parameters are required"}), 400
    
    m3u8_content = m3u8_handler.get_m3u8_content(player_domain, file_path, token or '')
    if m3u8_content:
        return Response(m3u8_content, mimetype='application/vnd.apple.mpegurl')
    else:
        return jsonify({"error": "Failed to get M3U8 content"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    def extract_video_data(self, content_url):
        """Extract video data from content page with multiple fallback methods"""
        try:
            print(f"🔍 Extracting video data from: {content_url}")
            
            response = self.session.get(content_url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch page: Status {response.status_code}")
                return None

            html_content = response.text
            
            # Method 1: Extract player domain
            domain_match = re.search(r"const AwsIndStreamDomain\s*=\s*['\"]([^'\"]+)['\"]", html_content)
            player_domain = domain_match.group(1) if domain_match else None
            print(f"🌐 Player Domain: {player_domain}")

            # Method 2: Extract from script tags (multiple patterns)
            video_sources = []
            
            # Pattern 1: Look for script with video data
            script_patterns = [
                r'script[^>]*>.*?src\s*:\s*[\'"]([^\'"]+)[\'"]',
                r'video-id[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]',
                r'file\s*:\s*[\'"]([^\'"]+)[\'"]',
                r'const\s+[\w]+\s*=\s*[\'"]([^\'"]+)[\'"]'
            ]
            
            for pattern in script_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if matches:
                    video_sources.extend(matches)
                    print(f"🎯 Found video sources with pattern {pattern}: {matches}")

            # Method 3: Look for iframe embeds
            iframe_matches = re.findall(r'<iframe[^>]*src=[\'"]([^\'"]+)[\'"]', html_content)
            for iframe_src in iframe_matches:
                if 'player' in iframe_src or 'embed' in iframe_src:
                    video_sources.append(iframe_src)
                    print(f"🎥 Found iframe source: {iframe_src}")

            # Method 4: Look for JSON-LD structured data
            json_ld_matches = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html_content, re.DOTALL)
            for json_ld in json_ld_matches:
                try:
                    data = json.loads(json_ld)
                    if 'contentUrl' in data:
                        video_sources.append(data['contentUrl'])
                        print(f"📊 Found JSON-LD contentUrl: {data['contentUrl']}")
                except:
                    pass

            print(f"📦 Total video sources found: {len(video_sources)}")
            
            if player_domain and video_sources:
                return {
                    'player_domain': player_domain,
                    'video_sources': video_sources,
                    'html_content_sample': html_content[:500] + "..." if len(html_content) > 500 else html_content
                }
            else:
                print("❌ No video sources found")
                return None

        except Exception as e:
            print(f"❌ Error extracting video data: {e}")
            return None

    def get_embed_data(self, player_domain, video_source, referer_url):
        """Get data from embed/player page"""
        try:
            # Construct embed URL
            if video_source.startswith('http'):
                embed_url = video_source
            else:
                embed_url = f"https://{player_domain}/play/{video_source}"
            
            print(f"🔗 Accessing embed URL: {embed_url}")
            
            response = self.session.get(embed_url, headers={'Referer': referer_url}, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch embed: Status {response.status_code}")
                return None

            # Look for JSON data in script
            json_match = re.search(r'(\{.*?\})', response.text)
            if json_match:
                json_data = json.loads(json_match.group(1))
                print(f"📄 Found JSON data: {list(json_data.keys())}")
                return json_data
            
            # Look for direct file links
            file_match = re.search(r'file\s*:\s*[\'"]([^\'"]+\.(m3u8|mp4))[\'"]', response.text, re.IGNORECASE)
            if file_match:
                return {'file': file_match.group(1)}
                
            return None
            
        except Exception as e:
            print(f"❌ Error getting embed data: {e}")
            return None

    def get_m3u8_content(self, player_domain, file_path, token):
        """Get M3U8 content"""
        try:
            m3u8_url = f"https://{player_domain}/playlist/{file_path}.txt"
            print(f"🎯 Fetching M3U8 from: {m3u8_url}")
            
            response = self.session.post(
                m3u8_url,
                headers={
                    'X-CSRF-TOKEN': token,
                    'Referer': BASE_URL + '/'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ Successfully fetched M3U8 content")
                return response.text
            else:
                print(f"❌ Failed to fetch M3U8: Status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting M3U8 content: {e}")
            return None

# Initialize the M3U8 handler
m3u8_handler = AllMovieLandM3U8()

@app.route('/')
def home():
    return jsonify({
        "message": "AllMovieLand M3U8 Proxy Server - FIXED VERSION",
        "status": "active",
        "test_url": "https://workss-epyp.onrender.com/m3u8?url=https://allmovieland.ac/3101-the-avengers.html",
        "endpoints": {
            "m3u8": "/m3u8?url=content_url",
            "health": "/health",
            "debug": "/debug?url=content_url"
        }
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy", 
        "timestamp": time.time(),
        "base_url": BASE_URL
    })

@app.route('/debug')
def debug_url():
    """Debug endpoint to see what data we can extract"""
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    print(f"🔧 Debugging URL: {content_url}")
    m3u8_handler.get_cookies()
    
    video_data = m3u8_handler.extract_video_data(content_url)
    if video_data:
        return jsonify({
            "success": True,
            "debug_info": video_data
        })
    else:
        return jsonify({
            "error": "No video data found",
            "suggestions": [
                "Check if the URL is accessible",
                "Verify the movie/TV show exists",
                "Try a different content URL"
            ]
        })

@app.route('/m3u8')
def get_m3u8_links():
    content_url = request.args.get('url')
    if not content_url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    print(f"🎬 Processing M3U8 request for: {content_url}")
    
    # Ensure we have cookies
    m3u8_handler.get_cookies()
    
    # Extract video data
    video_data = m3u8_handler.extract_video_data(content_url)
    if not video_data:
        return jsonify({
            "error": "Failed to extract video data",
            "debug_suggestion": "Try the /debug endpoint to see what data is available"
        }), 500
    
    player_domain = video_data['player_domain']
    video_sources = video_data['video_sources']
    
    m3u8_results = []
    
    # Try each video source
    for source in video_sources[:3]:  # Limit to first 3 sources
        print(f"🔄 Trying source: {source}")
        
        embed_data = m3u8_handler.get_embed_data(player_domain, source, content_url)
        if embed_data and embed_data.get('file'):
            file_path = embed_data['file']
            token = embed_data.get('key', '')
            
            m3u8_content = m3u8_handler.get_m3u8_content(player_domain, file_path, token)
            if m3u8_content:
                m3u8_results.append({
                    'title': f"Source - {source[:20]}...",
                    'file': file_path,
                    'player_domain': player_domain,
                    'token': token,
                    'm3u8_content_preview': m3u8_content[:100] + "..." if len(m3u8_content) > 100 else m3u8_content
                })
    
    if m3u8_results:
        return jsonify({
            "success": True,
            "content_url": content_url,
            "player_domain": player_domain,
            "sources_found": len(video_sources),
            "m3u8_streams": m3u8_results
        })
    else:
        return jsonify({
            "error": "No M3U8 streams found",
            "debug_info": {
                "player_domain": player_domain,
                "video_sources_found": video_sources,
                "suggestions": [
                    "The content might be restricted",
                    "Try a different movie URL",
                    "Check if the site structure changed"
                ]
            }
        })

@app.route('/direct')
def direct_m3u8():
    """Direct M3U8 access"""
    file_path = request.args.get('file')
    player_domain = request.args.get('domain')
    token = request.args.get('token')
    
    if not all([file_path, player_domain]):
        return jsonify({"error": "File and domain parameters are required"}), 400
    
    m3u8_content = m3u8_handler.get_m3u8_content(player_domain, file_path, token or '')
    if m3u8_content:
        return Response(m3u8_content, mimetype='application/vnd.apple.mpegurl')
    else:
        return jsonify({"error": "Failed to get M3U8 content"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)        """Search for movies/TV shows"""
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
