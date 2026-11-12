# Issue tracker: GitHub

Issues and their work contracts live in GitHub Issues on `AlexeyDesyatnik/simple-english-tts`. Current design specifications and decisions remain in the repository documents linked from `docs/development.md`. Use the `gh` CLI from inside the clone; it infers the repository automatically.

Use the developer's authenticated `gh`. If it returns HTTP 401, check the authentication
and whether the execution environment can access its credentials before reporting an
access blocker. Do not initiate a new login or fall back to unauthenticated REST for
that error.

## Operations

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --json number,title,body,labels,comments`.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`.
- **Apply or remove labels**: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- **Close an issue**: `gh issue close <number> --comment "..."`.
