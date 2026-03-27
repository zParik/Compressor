# SquishIt — Squish Videos for Discord

Compress videos to fit Discord's upload limits using two-pass H.264 encoding.
No limits, no sign-ups, no BS.

## Discord Size Targets

| Tier         | Limit  |
|-------------|--------|
| Free         | 10 MB  |
| Classic      | 25 MB  |
| Nitro Basic  | 50 MB  |
| Nitro        | 500 MB |

## What It Does

- **Two-pass encoding** — analyzes motion in pass 1, encodes perfectly in pass 2
- **Precise targeting** — hits your size target within ~2% accuracy
- **Smart scaling** — auto-reduces resolution when bitrate gets too low
- **4 quality modes** — from "best quality" to "extreme squish"
- **Real-time progress** — watch both encoding passes with live percentage
- **Auto-cleanup** — files delete after 1 hour

## Quick Start

```bash
# Install deps (Ubuntu/Debian)
sudo apt install ffmpeg python3 python3-pip
pip install flask pillow

# Run it
cd squishit
python3 app.py
```

Open **http://localhost:8080** and start squishing!

## Share With Friends

Your friends can use it over your local network:

```bash
python3 app.py
# Share: http://YOUR_LOCAL_IP:8080
# Find your IP: hostname -I
```

## Docker

```dockerfile
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y ffmpeg python3 python3-pip
RUN pip install flask --break-system-packages
COPY . /app
WORKDIR /app
EXPOSE 8080
CMD ["python3", "app.py"]
```

```bash
docker build -t squishit .
docker run -p 8080:8080 squishit
```

## How It Works

1. You upload a video and pick a target size (e.g. 10 MB for Discord free)
2. FFmpeg analyzes the video in **pass 1** to understand motion complexity
3. FFmpeg encodes the final video in **pass 2** using the optimal bitrate
4. If needed, resolution is reduced to keep quality acceptable at low bitrates
5. Output is H.264 MP4 with AAC audio — plays everywhere, Discord-compatible
