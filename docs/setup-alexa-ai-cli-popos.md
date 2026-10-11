# Setting up the `alexa-ai` CLI on Pop!_OS

Source: Amazon's ["Set Up Your Development Environment"](https://developer.amazon.com/docs/alexaplus/add-ons/set-up-your-development-environment.html)
page. The page lists **macOS and Ubuntu** as supported. Pop!_OS is Ubuntu-based, so it
should work, but it isn't named. I haven't run any of this myself (no AWS/Alexa account in
the sandbox), so check each command against the page if one fails.

**You don't need this to submit.** The Alexa+ track accepts a self-hosted MCP server over
Streamable HTTP (spec 2025-11-25), or a simulated Alexa+ web app. The CLI is how you register
the add-on and test it in Amazon's web simulator, which makes a stronger demo, so do it if
you can, but don't let it block the rest of the work.

## What you need first
- A free **Alexa developer account** (developer.amazon.com), with your profile filled in in
  the Alexa app, phone number and address set, and the marketplace/locale set to one that
  Alexa+ supports (the docs say the toolkit is US-only).
- An **AWS account** (also needed for Bedrock). Don't use the root user for anything below.
- **Node.js 24 or newer.**

## 1. Node 24 (via nvm)
Follow the nvm README for the install script, then:
```bash
nvm install 24 && nvm use 24
node --version        # v24.x
```

## 2. AWS CLI v2
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install
aws --version         # needs >= 2.13.23
```

## 3. An IAM user for the Alexa tooling
In the AWS console create an IAM user (e.g. `alexa-ai-tools`) with programmatic access and
this inline policy (it only lets the user assume Amazon's read-only tooling role):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "sts:AssumeRole",
    "Resource": "arn:aws:iam::372468808636:role/AddOn3PDeveloperToolsRead"
  }]
}
```

## 4. AWS profiles
```bash
aws configure --profile alexa-ai-user          # paste the IAM user's keys
aws configure set profile.alexa-ai.role_arn arn:aws:iam::372468808636:role/AddOn3PDeveloperToolsRead
aws configure set profile.alexa-ai.source_profile alexa-ai-user
aws configure set profile.alexa-ai.region us-west-2
```

## 5. Git access to CodeCommit (used by the tooling)
```bash
git config --global "credential.https://git-codecommit.us-west-2.amazonaws.com.helper" '!aws codecommit credential-helper --profile alexa-ai $@'
git config --global "credential.https://git-codecommit.us-west-2.amazonaws.com.UseHttpPath" true
```

## 6. Log npm in to Amazon's private registry
The CLI is not on public npm. This token expires after 12 hours: re-run it if `npm install`
starts failing with auth errors.
```bash
aws codeartifact login --tool npm --domain alexa-ai --repository npm-packages \
  --domain-owner 372468808636 --region us-west-2 --namespace @alexa-ai --profile alexa-ai
```

## 7. Install and check
```bash
npm install -g @alexa-ai/cli
alexa-ai --version
aws sts get-caller-identity --profile alexa-ai   # Account should be 372468808636
```

## 8. Sign in to Login with Amazon
```bash
alexa-ai configure              # opens a browser; add --no-browser over SSH
```
Credentials are stored in `~/.alexa-ai/credentials`.

## 9. Then
```bash
alexa-ai new mcp --name "Catch Me Up" --locale en-US --mcp-server-url "https://<your-host>/mcp"
alexa-ai deploy        # re-run after ANY change to tools or server details
# test in the web simulator, then:
alexa-ai submit
```
See `addon-package/README.md`.

## Separate AWS profile for Bedrock
Keep the Bedrock credentials separate from the `alexa-ai*` profiles above, e.g. your normal
`default` profile or a new one, and run the pipeline with `AWS_PROFILE=<that profile>`.
Enable model access for Claude in the Bedrock console first (see `docs/bedrock.md`).
