# Add-on package

`addon.json` is a DRAFT built from the field list in the Alexa+ quickstart. The exact JSON
nesting (e.g. where `locales`, icons and carousel images go) is not documented in what I
could read, so once the CLI is configured, run:

```
alexa-ai configure
alexa-ai new mcp --name "Catch Me Up" --locale en-US --mcp-server-url "https://<your-host>/mcp"
```

and copy our descriptions, phrases and URLs into the skeleton it generates. Then
`alexa-ai deploy`, test in the web simulator, and `alexa-ai submit`.

Limits from the docs: name <= 30 chars, short description <= 123, full description <= 4000,
3-4 example phrases (<= 200 chars each), HTTPS privacy/terms URLs, six light icon sizes
(72, 64, 88, 126, 180, 241), one 600x900 carousel image with alt text (<= 250 chars),
optional 1200x600 banner.

Open question: the docs only list `ride_booking` as an MCP add-on category. Check whether an
uncategorized/entertainment add-on is allowed (the Add-on Agent Skill or simulator should say).

`make_assets.py` generates the icon sizes from `images/source.png` (not created yet).
