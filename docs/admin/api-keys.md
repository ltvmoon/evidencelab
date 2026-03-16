## API Keys

Evidence Lab requires an API key to access all API endpoints. Keys can be provided as a global environment variable or generated per-key from the admin panel.

---

### Global API Key

Set a global key via the `API_SECRET_KEY` environment variable in `.env`:

```env
API_SECRET_KEY=your-secret-key-here
```

Generate a secure key:

```bash
openssl rand -hex 32
```

If `API_SECRET_KEY` is not set, the API starts with a warning and rejects all unauthenticated requests.

---

### Admin-Managed Keys

Superusers can generate and revoke standalone API keys from the **API Keys** tab in the admin panel. These keys work alongside the global key.

#### Generating a Key

1. Open the **Admin** panel and select the **API Keys** tab.
2. Enter a descriptive label (e.g. "Production pipeline") and click **Generate Key**.
3. The full key is displayed once in a modal. Copy it immediately — it cannot be retrieved later.

#### Revoking a Key

1. In the **API Keys** tab, find the key in the table.
2. Click **Revoke** and confirm in the dialog.
3. Any application using that key will immediately lose access.

#### Security Details

| Aspect | Implementation |
|--------|---------------|
| Key format | `el_` prefix + 32 bytes of `secrets.token_urlsafe` |
| Storage | SHA-256 hash only — plaintext is never stored |
| Lookup | In-memory cache of active hashes, invalidated on create/revoke |
| Access control | Superuser-only (all CRUD endpoints) |
| Audit logging | Key creation and revocation events are logged |

---

### Using an API Key

Include the key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-key-here" https://your-domain/api/search
```

In the Swagger UI (`/docs`), click **Authorize** and enter your key in the API key field.

---

### API Endpoints

All endpoints require superuser authentication via session cookie.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api-keys/` | List all keys (label, prefix, creator, timestamps) |
| `POST` | `/api-keys/` | Generate a new key (returns full key once) |
| `DELETE` | `/api-keys/{key_id}` | Revoke a key |
