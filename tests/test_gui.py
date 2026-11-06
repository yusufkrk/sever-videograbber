import http.client
import json
import threading
import time

import pytest

from sever_videograbber.core import DownloadResult, VideoGrabber
from sever_videograbber.errors import GrabberError
from sever_videograbber.gui.jobs import JobManager
from sever_videograbber.gui.server import GuiServer
from sever_videograbber.i18n import _UI, set_language
from sever_videograbber.options import DownloadOptions
from sever_videograbber.platforms import detect_platform


@pytest.fixture(autouse=True)
def lang():
    set_language("tr")


def fake_download(self, url, *, task_id=0):
    from sever_videograbber.core import ProgressEvent

    plat = detect_platform(url)
    self._emit(ProgressEvent(task_id, url, "extracting", plat, title="Başlık", thumbnail="https://x/t.jpg"))
    self._emit(ProgressEvent(task_id, url, "downloading", plat, downloaded=50, total=100, speed=10.0))
    if "slow" in url:
        for _ in range(100):
            if self._cancel.is_set():
                return DownloadResult(url=url, platform=plat, error=GrabberError("c", code="cancelled"))
            time.sleep(0.02)
    if "fail" in url:
        return DownloadResult(url=url, platform=plat, error=GrabberError("yok", code="login"))
    return DownloadResult(url=url, platform=plat, title="Başlık", ok=True)


def wait_for(pred, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(VideoGrabber, "download", fake_download)
    return JobManager(max_parallel=2)


def test_jobs_lifecycle(manager):
    ids = manager.add(["https://youtu.be/ok", "https://youtu.be/fail"], DownloadOptions())
    assert wait_for(lambda: manager.active_count() == 0)
    ok, fail = (manager.get(i) for i in ids)
    assert ok.status == "finished" and ok.title == "Başlık" and ok.thumbnail == "https://x/t.jpg"
    assert fail.status == "error" and fail.error_code == "login"
    snap = manager.snapshot()
    assert [j["id"] for j in snap] == ids  # aynı grup: yapıştırma sırası
    assert snap[0]["platform"]["key"] == "youtube"


def test_newest_batch_on_top(manager):
    first = manager.add(["https://youtu.be/a"], DownloadOptions())
    second = manager.add(["https://youtu.be/b"], DownloadOptions())
    assert [j["id"] for j in manager.snapshot()] == second + first


def test_cancel_and_retry(manager):
    (job_id,) = manager.add(["https://youtu.be/slow"], DownloadOptions())
    assert wait_for(lambda: manager.get(job_id).status == "downloading")
    assert manager.cancel(job_id)
    assert manager.get(job_id).status == "cancelled"
    assert wait_for(lambda: manager.active_count() == 0)
    assert manager.get(job_id).status == "cancelled"
    new_id = manager.retry(job_id)
    assert new_id and manager.get(job_id) is None
    manager.cancel(new_id)


def test_clear_finished_keeps_active(manager):
    manager.add(["https://youtu.be/ok"], DownloadOptions())
    assert wait_for(lambda: manager.active_count() == 0)
    (slow,) = manager.add(["https://youtu.be/slow"], DownloadOptions())
    manager.clear_finished()
    assert [j["id"] for j in manager.snapshot()] == [slow]
    manager.cancel(slow)


# ---------------------------------------------------------------------- HTTP


@pytest.fixture
def server(monkeypatch, tmp_path):
    monkeypatch.setattr(VideoGrabber, "download", fake_download)
    srv = GuiServer({"output_dir": str(tmp_path)})
    srv.start()
    yield srv
    srv.stop()


def request(srv, method, path, body=None, *, token=True, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
    headers = {"Content-Type": "application/json", "Host": host or f"127.0.0.1:{srv.port}"}
    if token:
        headers["X-Token"] = srv.token
    conn.request(method, path, body=json.dumps(body or {}) if method == "POST" else None, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def test_index_embeds_bootstrap(server):
    status, html = request(server, "GET", "/")
    assert status == 200
    text = html.decode()
    assert server.token in text and "/*__BOOTSTRAP__*/null" not in text
    assert "Yapıştır" in text


def test_api_requires_token_and_host(server):
    assert request(server, "POST", "/api/jobs", token=False)[0] == 403
    assert request(server, "POST", "/api/jobs", host="evil.example:80")[0] == 403
    assert request(server, "GET", "/", host="evil.example")[0] == 403


def test_download_flow_over_http(server, tmp_path):
    status, raw = request(
        server,
        "POST",
        "/api/download",
        {
            "text": "https://youtu.be/ok\nçöp youtu.be/fail",
            "audio_only": True,
            "audio_format": "m4a",
            "output_dir": str(tmp_path),
            "browser": "firefox",
        },
    )
    data = json.loads(raw)
    assert status == 200 and len(data["ids"]) == 2 and data["invalid"] == ["çöp"]
    job = server.jobs.get(data["ids"][0])
    assert job.options.audio_only and job.options.audio_format == "m4a"
    assert job.options.cookies_from_browser == "firefox"
    assert wait_for(lambda: server.jobs.active_count() == 0)
    jobs = json.loads(request(server, "POST", "/api/jobs")[1])["jobs"]
    assert {j["status"] for j in jobs} == {"finished", "error"}


def test_download_rejects_empty_and_bad_browser(server):
    assert request(server, "POST", "/api/download", {"text": "merhaba"})[0] == 400
    _, raw = request(server, "POST", "/api/download", {"text": "https://youtu.be/ok", "browser": "rm -rf"})
    job = server.jobs.get(json.loads(raw)["ids"][0])
    assert job.options.cookies_from_browser is None


def test_bad_json_and_unknown_route(server):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    conn.request(
        "POST", "/api/jobs", body="{", headers={"X-Token": server.token, "Host": f"127.0.0.1:{server.port}"}
    )
    assert conn.getresponse().status == 400
    conn.close()
    assert request(server, "POST", "/api/nope")[0] == 404


def test_pick_folder_without_window(server):
    data = json.loads(request(server, "POST", "/api/pick-folder")[1])
    assert data == {"path": None, "supported": False}


def test_ui_strings_parity():
    assert set(_UI["tr"]) == set(_UI["en"])


def test_server_threads_are_daemon(server):
    assert all(t.daemon for t in threading.enumerate() if t.name.startswith(("gui-http", "job-")))
