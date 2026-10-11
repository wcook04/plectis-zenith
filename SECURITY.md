# Security

Zenith is a local research prototype. Only the current source revision is
maintained; there is no supported hosted service or promise of response times.
The read-only graph API exposes reviewed source metadata and has no provider
execution or private run-data endpoints. Running the research CLI with an
explicit provider can send prompts to that service and incur its stated costs.

Keep keys in environment variables or a private environment file. Never commit
keys, runtime state, collected feeds or provider responses. Candidate Python
and retained optional third-party scripts are trusted local code, not sandboxed
plugins. Read them before execution. Use the offline reproduction path to
inspect the graph without credentials.

Report a vulnerability privately to the maintainer through the channel that
supplied this checkout. If the repository later offers GitHub private
vulnerability reporting, use its Security tab. No dedicated security email
or public reporting endpoint is established here. Do not post secrets or a
sensitive exploit in a public issue. Include the source revision, affected
command and a minimal synthetic reproduction; remove keys and private data.

See [the research boundary](docs/research-boundary.md) for the separate limits
on publishing generated market research and acquired data.
