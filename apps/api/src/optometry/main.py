from fastapi import FastAPI

from optometry.api import appointments, auth, patients
from optometry.api.admin_auth import router as admin_auth_router
from optometry.api.agent_chat import router as agent_chat_router
from optometry.api.agent_confirmations import router as agent_confirmations_router
from optometry.api.availability import router as availability_router
from optometry.api.clinics import router as clinics_router
from optometry.api.llm import router as llm_router
from optometry.api.optometrists import router as optometrists_router
from optometry.api.schedules import router as schedules_router
from optometry.api.services import router as services_router

# creates the api application.
app = FastAPI(
    title="Optometry Booking Agent",
    version="0.1.0",
    description="API for multi-location optometry bookings",
)

# register routers
app.include_router(clinics_router)
app.include_router(optometrists_router)
app.include_router(schedules_router)
app.include_router(services_router)
app.include_router(availability_router)
app.include_router(appointments.router)
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(admin_auth_router)
app.include_router(llm_router)
app.include_router(agent_confirmations_router)
app.include_router(agent_chat_router)


@app.get("/")
# returns the landing-page response for the api.
def home() -> dict[str, str]:
    return {
        "message": "Optometry Booking Agent API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
# checks whether the service is healthy.
def health_check() -> dict[str, str]:
    # report whether api process is running
    return {
        "status": "ok",
        "service": "optometry-booking-api",
    }
