import os
from flask import Flask, render_template_string, request, jsonify
import sqlite3
from database import init_db

app = Flask(__name__)

# Initialize database on app startup
init_db()

# HTML template for video player (using Video.js)
VIDEO_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <link href="https://vjs.zencdn.net/8.6.1/video-js.css" rel="stylesheet">
    <script src="https://vjs.zencdn.net/8.6.1/video.min.js"></script>
</head>
<body>
    <h1>My Tesla Videos</h1>
    <div id="video-list"></div>
    <script>
        fetch('/videos?user_id={{user_id}}')
            .then(r => r.json())
            .then(videos => {
                const list = document.getElementById('video-list');
                videos.forEach(v => {
                    const div = document.createElement('div');
                    div.innerHTML = `<h3>${v.title}</h3>
                        <video-js id="video-${v.id}" class="vjs-default-skin" controls preload="auto" width="800" height="450">
                            <source src="${v.url}" type="video/mp4">
                        </video-js>
                        <script>videojs('video-${v.id}');</script>`;
                    list.appendChild(div);
                });
            })
            .catch(err => {
                document.getElementById('video-list').innerHTML = '<p>Error loading videos. Please try again.</p>';
            });
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
        conn = sqlite3.connect('videos.db')
        c = conn.cursor()
        c.execute("SELECT id, title, url FROM videos WHERE user_id = ? ORDER BY added_at DESC", (user_id,))
        videos = [{'id': row[0], 'title': row[1], 'url': row[2]} for row in c.fetchall()]
        conn.close()
        return jsonify(videos)
    except Exception as e:
        print(f"Error fetching videos: {e}")
        return jsonify([]), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))