from fastapi import FastAPI

from optometry.api.clinics import router as clinics_router

# creates the central FastAPI application
app = FastAPI(
    title="Optometry Booking Agent",
    version="0.1.0",
    description="API for multi-location optometry bookings",
)

# register router
app.include_router(clinics_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    # report whether api process is running
    return {
        "status": "ok",
        "service": "optometry-booking-api",
    }
