import time

from fastapi.testclient import TestClient

from ugc_studio.app import create_app
from ugc_studio.config import Settings

from .conftest import jpeg_bytes
from .test_orchestrator import make_registry


def make_client(tmp_path, api_key=None):
    settings = Settings(data_dir=tmp_path, api_key=api_key)
    app = create_app(settings, make_registry(tmp_path))
    return TestClient(app)


def wait(client, job_id, headers=None, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/jobs/{job_id}", headers=headers).json()
        if job["status"] in ("succeeded", "failed"):
            return job
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_full_job_flow_with_upload(tmp_path):
    with make_client(tmp_path) as c:
        assert c.get("/health").json()["status"] == "ok"
        up = c.post("/uploads", files={"file": ("p.jpg", jpeg_bytes(), "image/jpeg")})
        assert up.status_code == 200
        r = c.post("/jobs", json={"brief": {"title": "GripMount", "price": "28", "description": "Snaps on fast.",
                                            "upload_ids": [up.json()["id"]]},
                                  "platform": "reels", "framework": "AIDA", "target_seconds": 20})
        assert r.status_code == 202
        job = wait(c, r.json()["id"])
        assert job["status"] == "succeeded", job["error"]
        assert job["product"]["images"] and job["script"]["framework"] == "AIDA"
        assert c.get(f"/jobs/{job['id']}/video").headers["content-type"] == "video/mp4"
        assert c.get(f"/jobs/{job['id']}/thumbnail").status_code == 200
        assert any(j["id"] == job["id"] for j in c.get("/jobs").json())


def test_validation_and_errors(tmp_path):
    with make_client(tmp_path) as c:
        assert c.post("/jobs", json={"platform": "tiktok"}).status_code == 422  # no url or brief
        assert c.post("/jobs", json={"url": "https://x.example", "resolution": "8k"}).status_code == 422
        assert c.get("/jobs/nope").status_code == 404
        assert c.post("/jobs", json={"url": "https://x.example", "music_upload_id": "../jobs.db"}).status_code == 400
        assert c.post("/uploads", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415
        bad = c.post("/jobs", json={"brief": {"title": "x", "upload_ids": ["../../etc/passwd"]}})
        job = wait(c, bad.json()["id"])
        assert job["status"] == "failed" and "upload" in job["error"].lower()


def test_api_key_and_plugin_swap(tmp_path):
    with make_client(tmp_path, api_key="s3cret") as c:
        assert c.get("/plugins").status_code == 401
        h = {"X-API-Key": "s3cret"}
        plugins = c.get("/plugins", headers=h).json()
        assert {p["capability"] for p in plugins} >= {"ingest", "analyze", "script", "voice", "align", "render"}
        assert c.put("/plugins/analyze", json={"name": "local"}, headers=h).status_code == 200
        assert c.put("/plugins/analyze", json={"name": "missing"}, headers=h).status_code == 404
        assert c.get("/options", headers=h).json()["frameworks"][0] == "PAS"
