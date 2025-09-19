import os
from flask import Flask, render_template_string, request, jsonify, send_file, abort
import psycopg
from database import init_db
import requests

app = Flask(__name__)

# Initialize database on app startup
init_db()

# HTML template for video player (using Video.js)
VIDEO_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>My Tesla Videos</title>
    <link href="https://vjs.zencdn.net/8.6.1/video-js.css" rel="stylesheet">
    <script src="https://vjs.zencdn.net/8.6.1/video.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { text-align: center; }
        .error { color: red; text-align: center; }
        .video-container { margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>My Tesla Videos</h1>
    <div id="video-list"></div>
    <script>
        const userId = '{{user_id}}';
        console.log('User ID:', userId);
        if (!userId) {
            document.getElementById('video-list').innerHTML = '<p class="error">No user ID provided. Please scan the QR code from the bot.</p>';
        } else {
            const videoUrl = '/videos?user_id=' + encodeURIComponent(userId);
            console.log('Fetching:', videoUrl);
            fetch(videoUrl)
                .then(r => {
                    if (!r.ok) throw new Error('Fetch failed: ' + r.status + ' ' + r.statusText);
                    return r.json();
                })
                .then(videos => {
                    console.log('Fetched videos:', videos);
                    const list = document.getElementById('video-list');
                    if (videos.length === 0) {
                        list.innerHTML = '<p>No videos added yet. Send a video URL to the Telegram bot.</p>';
                    } else {
                        videos.forEach(v => {
                            const mimeType = v.url.toLowerCase().endsWith('.mkv') ? 'video/x-matroska' : 'video/mp4';
                            const div = document.createElement('div');
                            div.className = 'video-container';
                            div.innerHTML = `<h3>${v.title}</h3>
                                <video-js id="video-${v.id}" class="vjs-default-skin" controls preload="auto" width="800" height="450">
                                    <source src="/proxy/video/${v.id}" type="${mimeType}">
                                </video-js>`;
                            list.appendChild(div);
                            videojs(`video-${v.id}`);
                        });
                    }
                })
                .catch(err => {
                    console.error('Fetch error:', err);
                    document.getElementById('video-list').innerHTML = '<p class="error'>Error loading videos: ' + err.message + '. Please try again.</p>';
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
        print("Error: No user_id provided in / or /login request")
        return "Scan QR from bot to log in.", 400
    print(f"Rendering page for user_id {user_id}")
    return render_template_string(VIDEO_TEMPLATE, user_id=user_id)

@app.route('/videos')
def get_videos():
    user_id = request.args.get('user_id')
    if not user_id:
        print("Error: No user_id provided in /videos request")
        return jsonify([]), 400
    
    try:
        conn_str = os.environ['DATABASE_URL']
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as c:
                c.execute("SELECT id, title, url FROM videos WHERE user_id = %s ORDER BY added_at DESC", (user_id,))
                videos = [{'id': row[0], 'title': row[1], 'url': row[2]} for row in c.fetchall()]
        print(f"Fetched {len(videos)} videos for user_id {user_id}: {videos}")
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
        
        print(f"Proxying video {video_id} from {video_url}")
        response = requests.get(video_url, stream=True, timeout=10)
        response.raise_for_status()
        
        # Explicitly set MIME type based on file extension
        mime_type = 'video/mp4' if video_url.lower().endswith('.mp4') else 'video/x-matroska'
        print(f"Proxying with MIME type: {mime_type}")
        
        return send_file(
            response.raw,
            mimetype=mime_type,
            as_attachment=False,
            attachment_filename='video.mp4'  # Force .mp4 filename for better compatibility
        )
    except requests.RequestException as e:
        print(f"Error proxying video {video_id}: {e}")
        abort(500)
    except Exception as e:
        print(f"Unexpected error proxying video {video_id}: {e}")
        abort(500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))