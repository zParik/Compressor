#!/usr/bin/env python3
"""
SquishIt — Video compressor for Discord uploads.
Targets 10MB (free), 25MB (Classic), 50MB (Nitro Basic), 500MB (Nitro) limits.
Uses two-pass encoding for precise file size targeting.
"""

import os, sys, uuid, subprocess, json, time, threading, math, shutil, tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file, after_this_request

# Support PyInstaller frozen exe and normal Python
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
    STATIC_DIR = Path(sys._MEIPASS) / "static"
    FFMPEG_DIR = Path(sys._MEIPASS) / "ffmpeg"  # extracted from inside the exe
else:
    BASE_DIR = Path(__file__).parent
    STATIC_DIR = BASE_DIR / "static"
    FFMPEG_DIR = BASE_DIR / "ffmpeg"

app = Flask(__name__, static_folder=str(STATIC_DIR))

DATA_DIR = BASE_DIR / "squishit_data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Add bundled ffmpeg to PATH so ffmpeg/ffprobe are found
if FFMPEG_DIR.exists():
    os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

# Track job progress
jobs = {}  # job_id -> {status, progress, error, output_path, ...}

def cleanup_old_files():
    while True:
        time.sleep(60)
        now = time.time()
        # Delete output files for completed downloads
        for job in list(jobs.values()):
            if job.get("status") == "downloaded":
                path = job.get("output_path")
                if path:
                    path.unlink(missing_ok=True)
        # Delete any leftover files older than 1 hour
        for d in [UPLOAD_DIR, OUTPUT_DIR]:
            for f in d.iterdir():
                if f.is_file() and now - f.stat().st_mtime > 3600:
                    f.unlink(missing_ok=True)

threading.Thread(target=cleanup_old_files, daemon=True).start()


def get_video_info(path):
    """Get video metadata via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:300]}")
    data = json.loads(result.stdout)

    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0))
    file_size = int(fmt.get("size", 0))
    bitrate = int(fmt.get("bit_rate", 0))

    # Find video and audio streams
    video_stream = None
    audio_stream = None
    for s in data.get("streams", []):
        if s["codec_type"] == "video" and not video_stream:
            video_stream = s
        elif s["codec_type"] == "audio" and not audio_stream:
            audio_stream = s

    width = int(video_stream.get("width", 0)) if video_stream else 0
    height = int(video_stream.get("height", 0)) if video_stream else 0
    fps_str = video_stream.get("r_frame_rate", "30/1") if video_stream else "30/1"
    try:
        num, den = fps_str.split("/")
        fps = round(float(num) / float(den), 2)
    except:
        fps = 30.0

    has_audio = audio_stream is not None

    return {
        "duration": duration,
        "file_size": file_size,
        "bitrate": bitrate,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": has_audio,
        "codec": video_stream.get("codec_name", "unknown") if video_stream else "unknown",
    }


def compute_encoding_params(info, target_mb, quality_preset):
    """Calculate encoding params to hit target file size."""
    target_bytes = target_mb * 1024 * 1024
    duration = info["duration"]

    if duration <= 0:
        raise RuntimeError("Cannot determine video duration")

    # Reserve bits for audio (128kbps for good quality, 96k for aggressive, 64k for extreme)
    audio_kbps = {"quality": 128, "balanced": 96, "aggressive": 64, "extreme": 48}[quality_preset]

    # Overhead margin (container, muxing, 2-pass variance) — ~5%
    usable_bytes = target_bytes * 0.95
    audio_bytes = (audio_kbps * 1000 / 8) * duration
    video_bytes = usable_bytes - audio_bytes

    if video_bytes <= 0:
        # Audio alone exceeds target, reduce audio
        audio_kbps = 32
        audio_bytes = (audio_kbps * 1000 / 8) * duration
        video_bytes = usable_bytes - audio_bytes

    video_bitrate_kbps = max(50, int((video_bytes * 8) / (duration * 1000)))

    # Decide resolution scaling
    w, h = info["width"], info["height"]
    target_h = h

    if quality_preset == "extreme":
        if h > 480: target_h = 480
    elif quality_preset == "aggressive":
        if h > 720: target_h = 720
    elif quality_preset == "balanced":
        if h > 1080: target_h = 1080
    # quality: no downscale

    # If bitrate is very low, force lower resolution
    if video_bitrate_kbps < 300 and target_h > 480:
        target_h = 480
    elif video_bitrate_kbps < 600 and target_h > 720:
        target_h = 720

    scale_factor = target_h / h if target_h < h else 1.0
    out_w = int(w * scale_factor)
    out_h = int(h * scale_factor)
    # Ensure even dimensions
    out_w = out_w + (out_w % 2)
    out_h = out_h + (out_h % 2)

    # FPS reduction for extreme compression
    target_fps = info["fps"]
    if quality_preset == "extreme" and target_fps > 30:
        target_fps = 24
    elif quality_preset == "aggressive" and target_fps > 60:
        target_fps = 30

    return {
        "video_bitrate_kbps": video_bitrate_kbps,
        "audio_bitrate_kbps": audio_kbps,
        "width": out_w,
        "height": out_h,
        "fps": target_fps,
        "duration": duration,
        "target_bytes": target_bytes,
        "estimated_size_mb": round((video_bitrate_kbps + audio_kbps) * duration / 8 / 1024, 2),
    }


def compress_video(job_id, input_path, target_mb, quality_preset):
    """Run two-pass H.264 compression targeting a specific file size."""
    try:
        jobs[job_id]["status"] = "analyzing"
        info = get_video_info(input_path)
        jobs[job_id]["input_info"] = info

        # Already small enough?
        if info["file_size"] <= target_mb * 1024 * 1024:
            output_path = OUTPUT_DIR / f"{input_path.stem}_{job_id}.mp4"
            shutil.copy2(str(input_path), str(output_path))
            jobs[job_id]["status"] = "done"
            jobs[job_id]["output_path"] = output_path
            jobs[job_id]["output_size"] = info["file_size"]
            jobs[job_id]["already_small"] = True
            return

        params = compute_encoding_params(info, target_mb, quality_preset)
        jobs[job_id]["params"] = params
        jobs[job_id]["status"] = "compressing"
        jobs[job_id]["progress"] = 0

        output_path = OUTPUT_DIR / f"{input_path.stem}_{job_id}.mp4"
        passlog = UPLOAD_DIR / f"passlog_{job_id}"

        vf_filters = []
        if params["width"] != info["width"] or params["height"] != info["height"]:
            vf_filters.append(f"scale={params['width']}:{params['height']}")
        if params["fps"] != info["fps"]:
            vf_filters.append(f"fps={params['fps']}")

        vf = ",".join(vf_filters) if vf_filters else None
        preset = "slow" if quality_preset == "quality" else "medium"

        # ── Pass 1 ──
        jobs[job_id]["pass"] = 1
        cmd1 = ["ffmpeg", "-y", "-i", str(input_path)]
        if vf:
            cmd1 += ["-vf", vf]
        cmd1 += [
            "-c:v", "libx264", "-preset", preset,
            "-b:v", f"{params['video_bitrate_kbps']}k",
            "-pass", "1", "-passlogfile", str(passlog),
            "-an", "-f", "null", os.devnull
        ]

        proc1 = subprocess.Popen(cmd1, stderr=subprocess.PIPE, text=True)
        monitor_progress(proc1, job_id, info["duration"], 1)
        if proc1.wait() != 0:
            raise RuntimeError("Pass 1 failed")

        # ── Pass 2 ──
        jobs[job_id]["pass"] = 2
        jobs[job_id]["progress"] = 50

        cmd2 = ["ffmpeg", "-y", "-i", str(input_path)]
        if vf:
            cmd2 += ["-vf", vf]
        cmd2 += [
            "-c:v", "libx264", "-preset", preset,
            "-b:v", f"{params['video_bitrate_kbps']}k",
            "-pass", "2", "-passlogfile", str(passlog),
            "-c:a", "aac", "-b:a", f"{params['audio_bitrate_kbps']}k",
            "-movflags", "+faststart",
            str(output_path)
        ]

        proc2 = subprocess.Popen(cmd2, stderr=subprocess.PIPE, text=True)
        monitor_progress(proc2, job_id, info["duration"], 2)
        if proc2.wait() != 0:
            raise RuntimeError("Pass 2 failed")

        # Verify output
        if not output_path.exists():
            raise RuntimeError("Output file not created")

        output_size = output_path.stat().st_size

        # If still too big (rare with 2-pass), do a quick trim attempt
        if output_size > target_mb * 1024 * 1024 * 1.05:
            jobs[job_id]["note"] = f"Slightly over target ({round(output_size/1024/1024, 1)}MB)"

        # Clean up passlog files
        for f in UPLOAD_DIR.glob(f"passlog_{job_id}*"):
            f.unlink(missing_ok=True)

        jobs[job_id]["status"] = "done"
        jobs[job_id]["output_path"] = output_path
        jobs[job_id]["output_size"] = output_size
        jobs[job_id]["progress"] = 100

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
    finally:
        input_path.unlink(missing_ok=True)


def monitor_progress(proc, job_id, duration, pass_num):
    """Parse ffmpeg stderr for progress updates."""
    offset = 0 if pass_num == 1 else 50
    for line in proc.stderr:
        if "time=" in line:
            try:
                time_str = line.split("time=")[1].split()[0]
                parts = time_str.split(":")
                secs = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                pass_progress = min(secs / duration * 50, 50)
                jobs[job_id]["progress"] = int(offset + pass_progress)
            except:
                pass


# ── Routes ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]
    target_mb = float(request.form.get("target_mb", 10))
    quality = request.form.get("quality", "balanced")

    if quality not in ("quality", "balanced", "aggressive", "extreme"):
        quality = "balanced"
    if target_mb not in (10, 25, 50, 100, 500):
        target_mb = 10

    job_id = uuid.uuid4().hex[:10]
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in ".-_ ").strip()
    input_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
    file.save(str(input_path))

    # Get info first to return immediately
    try:
        info = get_video_info(input_path)
    except Exception as e:
        input_path.unlink(missing_ok=True)
        return jsonify({"error": f"Not a valid video: {e}"}), 400

    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "input_info": info,
        "target_mb": target_mb,
        "quality": quality,
    }

    # Start compression in background thread
    t = threading.Thread(target=compress_video, args=(job_id, input_path, target_mb, quality))
    t.daemon = True
    t.start()

    return jsonify({
        "job_id": job_id,
        "input_info": info,
    })

@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    result = {
        "status": job["status"],
        "progress": job.get("progress", 0),
        "pass": job.get("pass"),
    }

    if job["status"] == "done":
        result["output_size"] = job.get("output_size", 0)
        result["input_size"] = job.get("input_info", {}).get("file_size", 0)
        result["already_small"] = job.get("already_small", False)
        result["note"] = job.get("note")
        result["download_url"] = f"/api/download/{job_id}"
        result["params"] = job.get("params")
    elif job["status"] == "error":
        result["error"] = job.get("error", "Unknown error")

    return jsonify(result)

@app.route("/api/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "Not ready"}), 404
    output_path = job["output_path"]
    job["status"] = "downloaded"
    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    import webbrowser
    port = 8080
    # Open browser after a short delay so Flask is ready
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"SquishIt running at http://localhost:{port}")
    print("Close this window to stop the app.")
    app.run(host="127.0.0.1", port=port, debug=False)
