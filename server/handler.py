"""AWS Lambda entry point (Function URL) via Mangum.

UNVERIFIED: whether Lambda + Mangum works with the MCP SDK's Streamable HTTP in stateless
JSON mode, and whether cold starts fit Alexa+'s 500 ms budget. Day-2 spike. Fallback: run
`server.main:app` in a container on AWS App Runner.
"""

from mangum import Mangum

from server.main import app

handler = Mangum(app, lifespan="auto")
