"""Application configuration."""
import os

__version__ = "0.1"


DEBUG = os.getenv("DEBUG", True)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = os.getenv("PORT", 5000)

SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT", "http://vocab.nerc.ac.uk/sparql/sparql")
SPARQL_USERNAME = os.getenv("SPARQL_USERNAME", "")
SPARQL_PASSWORD = os.getenv("SPARQL_PASSWORD", "")
SYSTEM_URI = os.getenv("SYSTEM_URI", "http://localhost:5007")
DATA_URI = os.getenv("DATA_URI", "http://vocab.nerc.ac.uk")
ORDS_ENDPOINT_URL = os.getenv("ORDS_ENDPOINT_URL", "https://livbodcsos.bodc.me:8443")
