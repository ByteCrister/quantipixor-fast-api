from mangum import Mangum
from main import app  # your FastAPI instance

handler = Mangum(app)