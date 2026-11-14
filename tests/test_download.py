import io
import zipfile

import pytest

from retail_analytics.contracts import CONTRACTS
from retail_analytics.download import download_olist


def archive_bytes(extra=False, payload="synthetic"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for contract in CONTRACTS.values():
            archive.writestr(contract.filename, payload)
        if extra:
            archive.writestr("../escape.csv", "unexpected")
    return buffer.getvalue()


def mock_response(monkeypatch, data):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(data))


def test_download_contract_and_idempotence(monkeypatch, tmp_path):
    mock_response(monkeypatch, archive_bytes())
    result = download_olist(tmp_path)
    assert len(result["files"]) == 9
    assert (tmp_path / "download_manifest.json").is_file()
    assert download_olist(tmp_path) == result


def test_download_protects_existing_data(monkeypatch, tmp_path):
    mock_response(monkeypatch, archive_bytes())
    download_olist(tmp_path)
    file = tmp_path / CONTRACTS["orders"].filename
    file.write_text("user-modified-source")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        download_olist(tmp_path)
    assert file.read_text() == "user-modified-source"


@pytest.mark.parametrize(
    "content,message",
    [
        (b"<html>authentication required</html>", "did not return a ZIP"),
        (archive_bytes(extra=True), "Unexpected Olist archive"),
    ],
)
def test_download_rejects_html_and_path_traversal(monkeypatch, tmp_path, content, message):
    mock_response(monkeypatch, content)
    with pytest.raises(ValueError, match=message):
        download_olist(tmp_path)
