from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os
from config import load_config

logger = logging.getLogger(__name__)
config = load_config()

def setup_static_files(app: FastAPI, static_directory: Path):
    app.mount("/static", StaticFiles(directory=static_directory, html=True), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index(request: Request):
        try:
            with open(config['index_html_path'], "r", encoding="utf-8") as file:
                html_content = file.read()
                html_content = html_content.replace("const port = 8025;", f"const port = {config['CLUSTER_BACKEND_PORT']};")
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as e:
            logger.error(f"Error loading index.html: {e}")
            return HTMLResponse(content=f"Error loading index.html: {e}", status_code=500)

    @app.get(f"/{config['browser2_html']}", response_class=HTMLResponse)
    async def serve_browser2(request: Request):
        try:
            with open(config['browser2_html_path'], "r", encoding="utf-8") as file:
                html_content = file.read()
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as e:
            logger.error(f"Error loading browser2.html: {e}")
            return HTMLResponse(content=f"Error loading browser2.html: {e}", status_code=500)
        
    @app.get(f"/{config['browser3_html']}", response_class=HTMLResponse)
    async def serve_browser3(request: Request):
        try:
            with open(config['browser3_html_path'], "r", encoding="utf-8") as file:
                html_content = file.read()
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as e:
            logger.error(f"Error loading browser3.html: {e}")
            return HTMLResponse(content=f"Error loading browser3.html: {e}", status_code=500)
        
    @app.get(f"/{config['weaviateui_html']}", response_class=HTMLResponse)
    async def serve_browser2(request: Request):
        try:
            with open(config['weaviateui_html_path'], "r", encoding="utf-8") as file:
                html_content = file.read()
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as e:
            logger.error(f"Error loading weaviateui.html: {e}")
            return HTMLResponse(content=f"Error loading weaviateui.html: {e}", status_code=500)

    # Serve the favicon
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(static_directory / "favicon.ico")
