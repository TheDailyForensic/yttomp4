import os
import re
import requests
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Error: index.html file not found in the repository.", 404

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    file_format = request.form.get('format')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        # Requesting data processing from Cobalt's public API endpoint
        api_url = "https://api.cobalt.tools/api/json"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        payload = {
            "url": url,
            "filenamePattern": "basic"
        }
        
        # Adjust API parameters depending on what the user wants
        if file_format == 'mp3':
            payload["isAudioOnly"] = True
            payload["audioFormat"] = "mp3"
        else:
            payload["videoCodec"] = "h264"  # Forces clean, universally readable MP4 files
            
        api_response = requests.post(api_url, json=payload, headers=headers)
        
        if api_response.status_code != 200:
            return jsonify({"error": "The stream processing infrastructure rejected the request layout."}), 500
            
        data = api_response.json()
        if data.get("status") == "error":
            return jsonify({"error": data.get("text", "Unknown engine error")}), 500
            
        stream_url = data.get("url")
        if not stream_url:
            return jsonify({"error": "Failed to resolve downstream data transport links."}), 500
            
        # Establish a live chunked data pipeline from the resolved link back to the browser
        file_stream = requests.get(stream_url, stream=True)
        
        def generate():
            for chunk in file_stream.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        safe_name = f"download.{file_format}"
        response_headers = {
            'Content-Disposition': f'attachment; filename="{safe_name}"',
            'Content-Type': 'audio/mpeg' if file_format == 'mp3' else 'video/mp4'
        }
        
        return Response(generate(), headers=response_headers)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
            info = ydl.extract_info(url, download=False)
            stream_url = info.get('url')
            title = info.get('title', 'download')
            
            if not stream_url:
                return jsonify({"error": "Could not extract stream URL."}), 500

            # Clean up the filename
            safe_title = re.sub(r'[^\x00-\x7F]+', '', title).replace(' ', '_')
            ext = 'm4a' if file_format == 'mp3' else 'mp4'  # Use m4a for audio to avoid heavy server-side mp3 conversion
            filename = f"{safe_title}.{ext}"

            # Open a live connection to the stream URL and pipe it directly to the user
            import requests
            req = requests.get(stream_url, stream=True)
            
            def generate():
                for chunk in req.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk

            # Return a streaming response directly to the browser
            headers = {
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'audio/mp4' if file_format == 'mp3' else 'video/mp4'
            }
            
            return Response(generate(), headers=headers)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
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
