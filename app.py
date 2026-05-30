import os
import re
from flask import Flask, request, send_file, render_template_string
import yt_dlp

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'

# Ensure the downloads directory exists locally
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Unified Frontend: HTML, CSS, and JavaScript in one block
HTML_INTERFACE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Local Media Converter</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #121212;
            color: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .converter-container {
            background-color: #1e1e1e;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            text-align: center;
            width: 400px;
        }
        h1 {
            margin-bottom: 8px;
            color: #ff0000;
        }
        p {
            color: #aaaaaa;
            font-size: 14px;
            margin-bottom: 24px;
        }
        input[type="url"] {
            width: 100%;
            padding: 12px;
            box-sizing: border-box;
            border: 2px solid #333;
            border-radius: 6px;
            background-color: #2a2a2a;
            color: white;
            font-size: 14px;
            margin-bottom: 16px;
        }
        .options {
            margin-bottom: 20px;
            text-align: left;
        }
        select {
            padding: 8px;
            background-color: #2a2a2a;
            color: white;
            border: 1px solid #333;
            border-radius: 4px;
            margin-left: 10px;
        }
        button {
            width: 100%;
            padding: 14px;
            background-color: #ff0000;
            color: white;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover {
            background-color: #cc0000;
        }
        button:disabled {
            background-color: #555555;
            cursor: not-allowed;
        }
        .hidden {
            display: none;
        }
        #statusMessage {
            margin-top: 20px;
        }
        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.1);
            width: 36px;
            height: 36px;
            border-radius: 50%;
            border-left-color: #ff0000;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="converter-container">
        <h1>Media Converter</h1>
        <p>Enter a video URL to convert and download locally</p>
        
        <form id="downloadForm">
            <input type="url" id="videoUrl" placeholder="https://www.youtube.com/watch?v=..." required>
            
            <div class="options">
                <label for="formatSelect">Format:</label>
                <select id="formatSelect">
                    <option value="mp4">MP4 (Video)</option>
                    <option value="mp3">MP3 (Audio)</option>
                </select>
            </div>
            
            <button type="submit" id="submitBtn">Convert & Download</button>
        </form>

        <div id="statusMessage" class="hidden">
            <div class="spinner"></div>
            <p id="statusText">Processing your file, please wait...</p>
        </div>
    </div>

    <script>
        document.getElementById('downloadForm').addEventListener('submit', async function(e) {
            e.preventDefault();

            const url = document.getElementById('videoUrl').value;
            const format = document.getElementById('formatSelect').value;
            const submitBtn = document.getElementById('submitBtn');
            const statusMessage = document.getElementById('statusMessage');
            const statusText = document.getElementById('statusText');

            submitBtn.disabled = true;
            statusMessage.classList.remove('hidden');
            statusText.innerText = "Processing media request on server...";

            try {
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `url=${encodeURIComponent(url)}&format=${format}`
                });

                if (!response.ok) {
                    throw new Error('Server failed to process the video download.');
                }

                statusText.innerText = "Downloading processed file to your system...";

                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                
                const a = document.createElement('a');
                a.href = downloadUrl;
                
                // Get filename from header if provided, otherwise fallback to generic naming
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = format === 'mp3' ? 'audio.mp3' : 'video.mp4';
                if (contentDisposition) {
                    const match = contentDisposition.match(/filename="(.+)"/);
                    if (match && match[1]) filename = match[1];
                }

                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                
                statusText.innerText = "Download complete!";
            } catch (error) {
                statusText.innerText = `Error: ${error.message}`;
            } finally {
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_INTERFACE)

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    file_format = request.form.get('format')
    
    # Configuration rules for yt-dlp processing logic
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'restrictfilenames': True,  # Ensures clean filenames without weird symbols
    }
    
    if file_format == 'mp3':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        # Downloads highest quality MP4 container video or merges streams
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Postprocessor adjustments for audio extensions
            if file_format == 'mp3':
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            # Clean up safe ASCII-only presentation string for download header
            safe_basename = re.sub(r'[^\x00-\x7F]+', '', os.path.basename(filename))
            
            return send_file(
                filename, 
                as_attachment=True, 
                download_name=safe_basename
            )
    except Exception as e:
        return f"Processing Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

if __name__ == "__main__":
    app.run(host="0.0.0.0")
