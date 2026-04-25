from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import risk, compliance, investment, users, explanation
from api.routes import finland

app = FastAPI(
    title="AquaCapital API",
    version="0.3.0",
    description=(
        "Water risk investment intelligence powered by ESA Copernicus satellites, "
        "SYKE Finnish Environment Institute data, and WWF/WRI peer-reviewed methodologies. "
        "CASSINI Hackathon 11 — Finland Oracle edition."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(risk.router)
app.include_router(compliance.router)
app.include_router(investment.router)
app.include_router(users.router)
app.include_router(explanation.router)
app.include_router(finland.router)


@app.get("/")
def root() -> dict:
    return {
        "status": "online",
        "tagline": "Where satellite data meets investment decisions.",
        "docs": "/docs",
        "version": app.version,
    }
