from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from paths import BASE_DIR
from routers import creates, credentials, limits, lookups, results, run, steps, uploads

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(creates.router)
app.include_router(credentials.router)
app.include_router(limits.router)
app.include_router(lookups.router)
app.include_router(results.router)
app.include_router(run.router)
app.include_router(steps.router)
app.include_router(uploads.router)


@app.get("/")
@app.get("/{full_path:path}")
async def index(full_path: str = ""):
    # SPA fallback: serve index.html for any client-side route (/onboarding,
    # /credentials, …) so hard-reloads and deep links work. /api and /static
    # are matched earlier by their routers/mount, so they never reach here.
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    return FileResponse(
        str(BASE_DIR / "static" / "index.html"),
        headers={"Cache-Control": "no-cache"},
    )
