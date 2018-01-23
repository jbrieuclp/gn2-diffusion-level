import pytest
from pathlib import Path
import sys

# BASE_DIR = Path(__file__).parent.parent
# sys.path.append(str(BASE_DIR))
import server

from geonature.utils.env import load_config, get_config_file_path




@pytest.fixture
def geonature_app():
    """ set the application context """
    config_path = get_config_file_path()
    config = load_config(config_path)
    app = server.get_app(config)
    ctx = app.app_context()
    ctx.push()
    yield app
    ctx.pop()
