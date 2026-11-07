"""The built console must be served with types a browser will execute.

On Windows the registry often maps .js to text/plain; a browser then refuses the module script and the
console renders blank, although index.html itself is served fine.
"""
import re

from fastapi.testclient import TestClient

from app.main import app


def test_console_scripts_and_styles_are_served_as_javascript_and_css():
    client = TestClient(app)
    index = client.get("/")
    assert index.status_code == 200
    scripts = re.findall(r'src="(/assets/[^"]+\.js)"', index.text)
    styles = re.findall(r'href="(/assets/[^"]+\.css)"', index.text)
    assert scripts, "index.html references no built script"
    for path in scripts:
        r = client.get(path)
        assert r.status_code == 200
        assert "javascript" in r.headers["content-type"], (path, r.headers["content-type"])
    for path in styles:
        r = client.get(path)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/css"), (path, r.headers["content-type"])
