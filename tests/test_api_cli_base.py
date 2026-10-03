"""Shared test_api_cli primitives and declarations."""



import secrets

API_TOKEN = secrets.token_hex(24)

HEADERS = {"Authorization": "Bearer " + API_TOKEN}
