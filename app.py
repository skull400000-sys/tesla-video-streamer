import os
from flask import Flask, render_template_string, request, jsonify, abort, Response
import psycopg
from database import init_db
import requests
from urllib.parse import unquote

app = Flask(__name__)

# Initialize database on app startup
init_db()

# --- NEW NETFLIX-STYLE TEMPLATE ---
VIDEO_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Tesla Videos</title>
    <link href="https://vjs.zencdn.net/8.6.1/video-js.css" rel="stylesheet">
    <script src="https://vjs.zencdn.net/8.6.1/video.min.js"></script>
    <style>
        :root {
            --brand-color: #E50914; /* Netflix Red */
            --background-color: #141414; /* Netflix Dark */
            --text-color: #e5e5e5;
            --container-bg: #1f1f1f;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            background-color: var(--background-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            font-size: 2.5rem;
            color: var(--brand-color);
            margin-bottom: 30px;
        }
        .video-wrapper {
            background-color: var(--container-bg);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        .video-title {
            font-size: 1.8rem;
            margin-bottom: 15px;
            word-wrap: break-word;
        }
        .video-js {
            width: 100%;
            height: auto;
            border-radius: 5px;
        }
        .vjs-control-bar {
            background-color: rgba(0,0,0,0.7) !important;
        }
        .vjs-big-play-button {
            border-color: var(--brand-color) !important;
            background-color: rgba(229, 9, 20, 0.7) !important;
        }
        .vjs-play-progress, .vjs-volume-level {
            background-color: var(--brand-color) !important;
        }
        .info-text {
            text-align: center;
            margin-top: 40px;
            font-size: 1.2rem;
        }
        .error {
            color: var(--brand-color);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>My Tesla Videos</h1>
        <div id="video-content"></div>
    </div>

    <script>
        const userId = '{{user_id}}';
        if (!userId) {
            document.getElementById('video-content').innerHTML = '<p class="info-text error">No user ID provided. Please scan the QR code from the bot.</p>';
        } else {
            const videoUrl = '/videos?user_id=' + encodeURIComponent(userId);
            fetch(videoUrl)
                .then(r => {
                    if (!r.ok) throw new Error('Fetch failed: ' + r.status + ' ' + r.statusText);
                    return r.json();
                })
                .then(videos => {
                    const content = document.getElementById('video-content');
                    if (videos.length === 0) {
                        content.innerHTML = '<p class="info-text">No videos added yet. Send a video URL to the Telegram bot.</p>';
                    } else {
                        // Since we only have one video now, just display the first one
                        const v = videos[0];
                        const mimeType = v.url.toLowerCase().endsWith('.mkv') ? 'video/x-matroska' : 'video/mp4';
                        
                        // Decode URL-encoded characters (like %20) for a cleaner title
                        const cleanTitle = decodeURIComponent(v.title.replace(/\\+/g, ' '));

                        content.innerHTML = `
                            <div class="video-wrapper">
                                <h2 class="video-title">${cleanTitle}</h2>
                                <video-js id="video-${v.id}" class="vjs-default-skin" controls preload="auto" width="16" height="9">
                                    <source src="/proxy/video/${v.id}" type="${mimeType}">
                                    <p class="vjs-no-js">
                                        To view this video please enable JavaScript, and consider upgrading to a web browser that
                                        <a href="https://videojs.com/html5-video-support/" target="_blank">supports HTML5 video</a>
                                    </p>
                                </video-js>
                            </div>`;
                        
                        const player = videojs('video-' + v.id, {
                            fluid: true // This makes the player responsive
                        });
                    }
                })
                .catch(err => {
                    console.error('Fetch error:', err);
                    document.getElementById('video-content').innerHTML = '<p class="info-text error">Error loading video: ' + err.message + '. Please try again.</p>';
                });
        }
    </script>
</body>
</html>
'''

@app.route('/')
@app.route('/login')
def index():
    user_id = request.args.get('user_id')
    if not user_id:
        return "Scan QR from bot to log in.", 400
    return render_template_string(VIDEO_TEMPLATE, user_id=user_id)

@app.route('/videos')
def get_videos():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify([]), 400
    
    try:
        conn_str = os.environ['DATABASE_URL']
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as c:
                c.execute("SELECT id, title, url FROM videos WHERE user_id = %s ORDER BY added_at DESC", (user_id,))
                # Use unquote to clean up URL-encoded titles
                videos = [{'id': row[0], 'title': unquote(row[1]), 'url': row[2]} for row in c.fetchall()]
        return jsonify(videos)
    except Exception as e:
        print(f"Error fetching videos for user_id {user_id}: {e}")
        return jsonify([]), 500

# --- UPGRADED PROXY FUNCTION WITH SEEKING SUPPORT ---
@app.route('/proxy/video/<int:video_id>')
def proxy_video(video_id):
    try:
        conn_str = os.environ['DATABASE_URL']
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as c:
                c.execute("SELECT url FROM videos WHERE id = %s", (video_id,))
                result = c.fetchone()
                if not result:
                    abort(404)
                video_url = result[0]

        # Prepare headers for the request to the source
        proxy_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Check for a Range header from the browser and pass it on
        range_header = request.headers.get('Range', None)
        if range_header:
            proxy_headers['Range'] = range_header
        
        # Make the request to the video source
        source_response = requests.get(video_url, headers=proxy_headers, stream=True, timeout=20)
        source_response.raise_for_status()

        # Build our response to the browser, copying headers from the source
        response_headers = {}
        for key, value in source_response.headers.items():
            # These headers are important for streaming and seeking
            if key.lower() in ['content-type', 'content-length', 'accept-ranges', 'content-range']:
                response_headers[key] = value

        # Create a Flask response that streams the content
        return Response(
            source_response.iter_content(chunk_size=8192),
            status=source_response.status_code,
            headers=response_headers,
            mimetype=source_response.headers.get('Content-Type')
        )
        
    except requests.RequestException as e:
        print(f"Error proxying video {video_id}: {e}")
        abort(500)
    except Exception as e:
        print(f"Unexpected error proxying video {video_id}: {e}")
        abort(500)