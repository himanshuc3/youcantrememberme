## Server flow

Application -> ASGI server -> MCP server -> subscribe tools (Common: DB interactions, dispatching jobs)

Dispatching Job for show fetching: Add a job to DB -> polling via the worker (bottleneck is scanning the whole table and not cleaning up, can set auto TTLs which clear DB rows more than 24 hours in the table)
