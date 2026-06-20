"""Lazy model fetch + manifest-driven catalog for the LSTM forecast feature.
DB-free: the network fetch is monkeypatched and MODELS_DIR is redirected to tmp."""
import json

import models.predictor as predictor


def test_available_forecasts_reads_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(predictor, "MODELS_DIR", tmp_path)
    (tmp_path / "forecast_manifest.json").write_text(
        json.dumps({"Bihar": ["Wheat", "Rice"]}), encoding="utf-8")
    assert predictor.available_forecasts() == {"Bihar": ["Wheat", "Rice"]}


def test_ensure_local_downloads_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(predictor, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(predictor, "FORECAST_MODELS_BASE_URL", "https://host/models")
    calls = []

    def fake_urlretrieve(url, dest):
        calls.append(url)
        # simulate a successful download by creating the temp file
        open(dest, "w").close()

    monkeypatch.setattr(predictor.urllib.request, "urlretrieve", fake_urlretrieve)

    predictor._ensure_local("Bihar_Wheat")

    assert (tmp_path / "Bihar_Wheat.pt").exists()
    assert (tmp_path / "Bihar_Wheat_scaler.joblib").exists()
    # the .pt and scaler URLs were requested from the configured base
    assert "https://host/models/Bihar_Wheat.pt" in calls


def test_ensure_local_noop_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(predictor, "MODELS_DIR", tmp_path)
    (tmp_path / "Bihar_Wheat.pt").write_text("x")
    (tmp_path / "Bihar_Wheat_scaler.joblib").write_text("x")
    (tmp_path / "Bihar_Wheat_meta.json").write_text("{}")

    def boom(*a, **k):
        raise AssertionError("should not download when files exist")

    monkeypatch.setattr(predictor.urllib.request, "urlretrieve", boom)
    predictor._ensure_local("Bihar_Wheat")  # must not raise


def test_ensure_local_tolerates_missing_meta_sidecar(tmp_path, monkeypatch):
    import urllib.error
    monkeypatch.setattr(predictor, "MODELS_DIR", tmp_path)

    def fake_urlretrieve(url, dest):
        if url.endswith("_meta.json"):
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        open(dest, "w").close()

    monkeypatch.setattr(predictor.urllib.request, "urlretrieve", fake_urlretrieve)
    predictor._ensure_local("Bihar_Wheat")  # 404 on meta must not raise
    assert (tmp_path / "Bihar_Wheat.pt").exists()
    assert not (tmp_path / "Bihar_Wheat_meta.json").exists()
