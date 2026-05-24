"""
Digen.ai Video Generation API client for OWL-BOT
Free tier: 300 credits, watermarked videos, up to 720p
Models: Sora2(1), VEO(2), Banana(3), Grok(6), Seedream(7), SoraMax(9)
"""

import urllib.request
import json
import uuid
import time
import os

DIGEN_API = "https://api.digen.ai"

MODEL_IDS = {
    "sora": "1",       # Sora 2 - text-to-video
    "sora2": "1",
    "veo": "2",        # VEO - text-to-video
    "banana": "3",     # Banana
    "grok": "6",       # Grok Video
    "seedream": "7",    # Seedream 5 lite
    "soramax": "9",    # Sora Max
}

MODEL_CREDITS = {
    "1": 30,   # Sora2: 30 credits
    "2": 20,   # VEO: 20 credits
    "6": 25,   # Grok: 25 credits (estimated)
    "7": 15,   # Seedream: 15 credits (estimated)
    "9": 50,   # SoraMax: 50 credits (estimated)
}

_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _load_credentials():
    """Load credentials from .env file. Returns (email, password) or (None, None)."""
    if not os.path.exists(_env_file):
        return None, None
    email, password = None, None
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("DIGEN_EMAIL="):
                email = line.split("=", 1)[1]
            elif line.startswith("DIGEN_PASSWORD="):
                password = line.split("=", 1)[1]
    return email, password


def _make_headers(token=None):
    session_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())  # persistent per session is better but random works
    h = {
        "Content-Type": "application/json",
        "Digen-SessionID": session_id,
        "Digen-Language": "en",
        "Digen-Platform": "web",
        "DIGEN-DeviceID": device_id,
        "DIGEN-SystemType": "Android",
        "DIGEN-SystemVersion": "16",
        "DIGEN-AppVersion": "0.0.47",
        "Origin": "https://digen.ai",
        "Referer": "https://digen.ai/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    if token:
        h["Digen-Token"] = token
    return h


def _post(url, data, headers):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())


def _get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())


def login(email=None, password=None):
    """Login to Digen.ai. Returns token and user info."""
    if not email or not password:
        email, password = _load_credentials()
    if not email or not password:
        raise ValueError("No credentials. Set DIGEN_EMAIL and DIGEN_PASSWORD in .env")

    headers = _make_headers()
    result = _post(f"{DIGEN_API}/v1/user/login",
                   {"email": email, "password": password, "rememberMe": True},
                   headers)

    if result.get("errCode") != 0:
        raise Exception(f"Login failed: {result.get('errMsg')}")

    data = result["data"]
    return {
        "token": data["token"],
        "user_id": data["id"],
        "name": data["name"],
        "email": data["email"],
    }


def get_credits(token):
    """Check remaining credits."""
    headers = _make_headers(token)
    result = _get(f"{DIGEN_API}/v1/credit/remain", headers)
    if result.get("errCode") == 0:
        return result["data"]["remained"]
    return None


def get_queue_status(token, model_id="1"):
    """Check queue status for a model."""
    headers = _make_headers(token)
    try:
        result = _get(f"{DIGEN_API}/v1/tools/queue", headers)
        if result.get("errCode") == 0:
            q = result["data"]["queue"]
            return {
                "total": q.get("total", 0),
                "estimated_time": q.get("customer_estimatedTime", 0),
                "ahead": q.get("customer_area", 0),
            }
    except Exception:
        pass
    return None


def submit_video(token, prompt, model="sora", duration=5, resolution="720p",
                 aspect_ratio="16:9", negative_prompt=""):
    """Submit a video generation job. Returns job info."""
    model_id = MODEL_IDS.get(model.lower(), "1")
    headers = _make_headers(token)

    payload = {
        "model": model_id,
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
        "aspectRatio": aspect_ratio,
    }
    if negative_prompt:
        payload["negativePrompt"] = negative_prompt

    result = _post(f"{DIGEN_API}/v3/video/job/submit", payload, headers)

    if result.get("errCode") != 0:
        raise Exception(f"Submit failed: {result.get('errMsg')}")

    data = result["data"]
    return {
        "job_id": data["jobId"],
        "status": data["status"],
        "thumbnail": data.get("thumbnail", ""),
        "video_url": data.get("videoUrl", ""),
        "created_at": data.get("createdAt", ""),
    }


def get_job_status(token, job_id):
    """Check job status. Returns job data."""
    headers = _make_headers(token)

    # Try video_list (most reliable - shows all user videos)
    try:
        result = _get(f"{DIGEN_API}/v1/community/video_list?page=1&pageSize=20", headers)
        if result.get("errCode") == 0:
            videos = result.get("data", {}).get("list", [])
            for v in videos:
                if v.get("jobID") == job_id:
                    video_url = v.get("videoURL", "")
                    return {
                        "status": "completed" if video_url else "processing",
                        "video_url": video_url,
                        "thumbnail": v.get("thumbnail", ""),
                        "source": "video_list",
                    }
    except Exception:
        pass

    # Try get_url
    try:
        result = _post(f"{DIGEN_API}/v1/tools/get_url",
                       {"jobID": job_id}, headers)
        if result.get("errCode") == 0 and result.get("data"):
            return {"status": "completed", "video_url": result["data"], "source": "get_url"}
    except Exception:
        pass

    # Try v3/video/get_task
    try:
        result = _get(f"{DIGEN_API}/v3/video/get_task?jobId={job_id}", headers)
        if result.get("errCode") == 0:
            data = result["data"]
            video_url = data.get("videoUrl", "") or data.get("videoUrlV1", "")
            return {
                "status": "completed" if video_url else "processing",
                "video_url": video_url,
                "thumbnail": data.get("thumbnail", ""),
                "source": "get_task",
            }
    except Exception:
        pass

    return {"status": "unknown", "video_url": ""}


def generate_video(email, password, prompt, model="sora", duration=5,
                   resolution="720p", aspect_ratio="16:9", wait=True,
                   timeout=300, poll_interval=15):
    """
    Full pipeline: login → submit → poll → return video URL.
    
    Args:
        email, password: Digen.ai credentials
        prompt: Text description for the video
        model: Model name (sora, veo, grok, seedream, soramax)
        duration: Video duration in seconds (3-15)
        resolution: "720p" (free tier max)
        aspect_ratio: "16:9", "9:16", "1:1"
        wait: If True, poll until video is ready
        timeout: Max seconds to wait
        poll_interval: Seconds between polls
    
    Returns:
        dict with job_id, video_url, status, etc.
    """
    # Login
    auth = login(email, password)
    token = auth["token"]

    # Check credits
    credits = get_credits(token)
    model_id = MODEL_IDS.get(model.lower(), "1")
    cost = MODEL_CREDITS.get(model_id, 30)
    if credits is not None and credits < cost:
        return {
            "status": "error",
            "error": f"Not enough credits. Have: {credits}, Need: {cost}",
        }

    # Submit
    job = submit_video(token, prompt, model, duration, resolution, aspect_ratio)
    job_id = job["job_id"]

    if not wait:
        return {
            "status": "submitted",
            "job_id": job_id,
            "video_url": "",
            "credits_remaining": credits,
        }

    # Poll for completion
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(poll_interval)
        status = get_job_status(token, job_id)
        if status["status"] == "completed" and status.get("video_url"):
            status["job_id"] = job_id
            status["credits_remaining"] = credits
            return status
        if status["status"] in ("failed", "error"):
            return {"status": "failed", "job_id": job_id, "error": "Generation failed"}

    return {"status": "timeout", "job_id": job_id, "video_url": ""}


if __name__ == "__main__":
    import sys
    email, password = _load_credentials()
    if not email:
        print("Set DIGEN_EMAIL and DIGEN_PASSWORD in .env file")
        sys.exit(1)

    prompt = sys.argv[1] if len(sys.argv) > 1 else "A beautiful sunset over the ocean"
    model = sys.argv[2] if len(sys.argv) > 2 else "sora"

    print(f"Generating video with model={model}: {prompt}")
    result = generate_video(email, password, prompt, model=model)
    print(json.dumps(result, indent=2))
