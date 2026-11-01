"""AWS Lambda adapter for the FastAPI Strands service."""

from mangum import Mangum

from main import app

handler = Mangum(app, lifespan="off")
