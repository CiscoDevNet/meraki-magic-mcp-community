# Security Policies and Procedures

This document outlines security procedures and general policies for the
`meraki-magic-mcp-community` project.

- [Deployment Guidance](#deployment-guidance)
- [Reporting a Bug](#reporting-a-bug)
- [Disclosure Policy](#disclosure-policy)
- [Comments on this Policy](#comments-on-this-policy)

## Deployment Guidance

The MCP server acts with the permissions of the Meraki API key it is given.

- **Read-only mode** is on by default (`READ_ONLY_MODE=true`). Turn it off only when you intend to make changes, and prefer an API key for a read-only dashboard administrator when writes are never needed.
- **stdio transport** (the default) is only reachable by the local MCP client that starts the server.
- **HTTP and SSE transports** expose every tool to anyone who can reach the port. Keep `MCP_HOST=127.0.0.1` unless remote access is required, set `MCP_AUTH_TOKEN` to require `Authorization: Bearer <token>` on every request, and terminate TLS at a reverse proxy for access across a network.
- **Docker**: the image runs as an unprivileged user, and the default `docker-compose.yml` publishes the port on the host's loopback interface only.
- **Cached responses** can contain sensitive configuration. They are written with owner-only permissions and pruned automatically; set `ENABLE_FILE_CACHING=false` on shared hosts if you do not need them.

## Reporting a Bug

The `meraki-magic-mcp-community` team and community take all security bugs in
`meraki-magic-mcp-community` seriously. Thank you for improving the security of
`meraki-magic-mcp-community`. We appreciate your efforts and responsible disclosure and
will make every effort to acknowledge your contributions.

Report security bugs by emailing `oss-security@cisco.com`.

The lead maintainer will acknowledge your email within 48 hours, and will send a
more detailed response within 48 hours indicating the next steps in handling
your report. After the initial reply to your report, the security team will
endeavor to keep you informed of the progress towards a fix and full
announcement, and may ask for additional information or guidance.

## Disclosure Policy

When the security team receives a security bug report, they will assign it to a
primary handler. This person will coordinate the fix and release process,
involving the following steps:

- Confirm the problem and determine the affected versions.
- Audit code to find any potential similar problems.
- Prepare fixes for all releases still under maintenance. These fixes will be
  released as quickly as possible.

## Comments on this Policy

If you have suggestions on how this process could be improved please submit a
pull request.
