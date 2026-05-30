import os
import re
from flask import Flask, request, send_file, jsonify
import yt_dlp

app = Flask(__name__)

DOWNLOAD_FOLDER = '/tmp/downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def home():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Error: index.html file not found.", 404

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    file_format = request.form.get('format')
    
    # Initialize dictionary flatly to avoid nesting typos
    ydl_opts = {}
    ydl_opts['outtmpl'] = os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')
    ydl_opts['restrictfilenames'] = True
    ydl_opts['quiet'] = True
    ydl_opts['no_warnings'] = True
    
    # Add spoofing headers step-by-step
    headers = {}
    headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    headers['Accept-Language'] = 'en-us,en;q=0.5'
    ydl_opts['http_headers'] = headers

    if file_format == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}]
    else:
        ydl_opts['format'] = 'best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if file_format == 'mp3':
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            if not os.path.exists(filename):
                return jsonify({"error": "Output file missing."}), 500
                
            safe_basename = re.sub(r'[^\x00-\x7F]+', '', os.path.basename(filename))
            
            return send_file(
                filename, 
                as_attachment=True, 
                download_name=safe_basename
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
