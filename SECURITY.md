# Security

## What this tool does to your machine

`prove-your-tests` edits files in the repository you point it at (one planted bug at a time) and runs the test
command you give it. Treat it like running your own test suite:

- Run it only on code and test commands you trust. The test command runs in a shell with your permissions.
- It refuses a repository with uncommitted changes, so `git status` can always show what a crash left behind.
- Before it changes any file it writes a journal; `prove-your-tests recover <out dir>` puts every file back.
- It never sends your code anywhere. The optional plant writer (`write-plants`) sends the source files you name to
  the model provider you configure, and reads the API key only from an environment variable. It never stores,
  prints or logs the key.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private vulnerability reporting
("Security" tab, "Report a vulnerability") on this repository. We aim to answer within 5 working days and to
ship a fix or a mitigation within 30 days of confirming the report.

Especially welcome: any way a run can leave a planted change in a user's files, report PASS for a plant that
was not run and killed, or leak an API key.
