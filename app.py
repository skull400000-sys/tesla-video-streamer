# app.py
import os
from flask import Flask, render_template_string, request, jsonify, abort, Response
import psycopg
from database import init_db
import requests
from urllib.parse import unquote

app = Flask(__name__)

# Initialize database on app startup
init_db()

# --- NEW CANVAS PLAYER TEMPLATE ---
VIDEO_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Tesla Videos</title>
    <style>
        :root {
            --brand-color: #E50914;
            --background-color: #141414;
            --text-color: #e5e5e5;
            --container-bg: #000;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            background-color: var(--background-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
        }
        .video-wrapper {
            background-color: var(--container-bg);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            text-align: center;
        }
        .video-title {
            font-size: 1.8rem;
            margin-bottom: 15px;
            word-wrap: break-word;
        }
        #player_canvas {
            width: 100%;
            height: auto;
            border-radius: 5px;
            cursor: pointer;
            background-color: #000;
        }
        .play-button-overlay {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 80px;
            height: 80px;
            background-color: rgba(229, 9, 20, 0.7);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            pointer-events: none; /* Allows clicks to go through to the canvas */
            transition: opacity 0.2s ease;
        }
        .play-button-overlay svg {
            width: 40px;
            height: 40px;
            fill: #fff;
        }
        .canvas-container {
            position: relative; /* Needed for the overlay */
            width: 100%;
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
        <div id="video-content"></div>
    </div>

    <script>
        const userId = '{{user_id}}';
        if (!userId) {
            document.getElementById('video-content').innerHTML = '<p class="info-text error">No user ID provided. Please use the link from the Telegram bot.</p>';
        } else {
            const videoUrl = '/videos?user_id=' + encodeURIComponent(userId);
            fetch(videoUrl)
                .then(r => r.json())
                .then(videos => {
                    const content = document.getElementById('video-content');
                    if (videos.length === 0) {
                        content.innerHTML = '<p class="info-text">No videos added yet. Send a video URL to the Telegram bot.</p>';
                    } else {
                        const v = videos[0];
                        const cleanTitle = decodeURIComponent(v.title.replace(/\\+/g, ' '));

                        content.innerHTML = `
                            <div class="video-wrapper">
                                <h2 class="video-title">${cleanTitle}</h2>
                                <div class="canvas-container">
                                    <canvas id="player_canvas"></canvas>
                                    <div class="play-button-overlay" id="play_overlay">
                                        <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                                    </div>
                                </div>
                                <video id="video_source" src="/proxy/video/${v.id}" style="display:none;"></video>
                            </div>`;
                        
                        setupCanvasPlayer();
                    }
                })
                .catch(err => {
                    document.getElementById('video-content').innerHTML = '<p class="info-text error">Error loading video: ' + err.message + '. Please try again.</p>';
                });
        }

        function setupCanvasPlayer() {
            const video = document.getElementById('video_source');
            const canvas = document.getElementById('player_canvas');
            const context = canvas.getContext('2d');
            const playOverlay = document.getElementById('play_overlay');

            video.addEventListener('loadedmetadata', () => {
                // Set canvas dimensions based on video's aspect ratio
                const aspectRatio = video.videoWidth / video.videoHeight;
                const canvasWidth = canvas.offsetWidth;
                canvas.width = canvasWidth;
                canvas.height = canvasWidth / aspectRatio;
                // Draw the first frame on the canvas
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
            });

            const drawFrame = () => {
                if (!video.paused && !video.ended) {
                    context.drawImage(video, 0, 0, canvas.width, canvas.height);
                    requestAnimationFrame(drawFrame);
                }
            };
            
            video.addEventListener('play', () => {
                playOverlay.style.opacity = '0';
                drawFrame();
            });

            video.addEventListener('pause', () => {
                playOverlay.style.opacity = '1';
            });

            canvas.addEventListener('click', () => {
                if (video.paused) {
                    video.play();
                } else {
                    video.pause();
                }
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
                videos = [{'id': row[0], 'title': unquote(row[1]), 'url': row[2]} for row in c.fetchall()]
        return jsonify(videos)
    except Exception as e:
        print(f"Error fetching videos for user_id {user_id}: {e}")
        return jsonify([]), 500

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

        proxy_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        range_header = request.headers.get('Range', None)
        if range_header:
            proxy_headers['Range'] = range_header
        
        source_response = requests.get(video_url, headers=proxy_headers, stream=True, timeout=20)
        source_response.raise_for_status()

        response_headers = {}
        for key, value in source_response.headers.items():
            if key.lower() in ['content-type', 'content-length', 'accept-ranges', 'content-range']:
                response_headers[key] = value

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