## User Administration

The authentication module is opt-in and built on [fastapi-users](https://fastapi-users.github.io/fastapi-users/). It supports three modes via the `USER_MODULE` environment variable:

* `off` (default) — no authentication
* `on_passive` — authentication available but optional; anonymous users can browse freely
* `on_active` — all access requires login

### Authentication

* **Email/password registration** with mandatory email verification. Passwords are hashed with bcrypt and must meet configurable complexity rules.
* **OAuth single sign-on** with Google and Microsoft — users are auto-linked by email.
* **Cookie-based sessions** using httpOnly, secure, SameSite cookies. No tokens are stored in localStorage.
* **CSRF protection** via the double-submit cookie pattern.

### Security

* **Account lockout** — configurable failed login attempts threshold (default 5) with lockout period (default 15 minutes)
* **Rate limiting** — login, registration, and password-reset endpoints are rate-limited per IP address
* **Audit logging** — all security-relevant events recorded in an append-only audit log
* **Domain restriction** — registration can be restricted to approved email domains via `AUTH_ALLOWED_EMAIL_DOMAINS`

### Group-Based Permissions

* Users belong to one or more groups, each granted access to specific data-source keys
* Searches and document views are filtered so users only see data sources their groups allow
* New users are automatically added to a configurable default group
* The first admin is bootstrapped via the `FIRST_SUPERUSER_EMAIL` environment variable

### Admin Panel

Superusers can manage:

* **Users** — activate, verify, promote, and manage user accounts
* **Groups** — create and edit groups, assign data-source access
* **Ratings** — view user ratings with search, sort, pagination, and XLSX export
* **Activity** — view search activity logs with XLSX export

### User Self-Service

* **Profile management** — users can update their display name
* **Account deletion** — permanently deletes account, group memberships, OAuth links, ratings, and activity logs
