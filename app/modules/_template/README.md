# New feature module template

Copy this folder to `app/modules/<your_service>/` and rename.

## Required files

| File | Responsibility |
|------|----------------|
| `models.py` | SQLAlchemy tables (inherit `app.db.base.Base`) |
| `schemas.py` | Pydantic request/response models |
| `repository.py` | DB queries only (extend `BaseRepository` if useful) |
| `service.py` | Business rules; call repository, never raw SQL in router |
| `router.py` | FastAPI routes; thin — delegate to `service` |

## Wire-up checklist

1. Import models in `app/db/registry.py` so tables are created.
2. Add `router` to `app/api/v1/router.py`.
3. Add tests under `tests/modules/<your_service>/`.
4. Add module-specific env vars to `.env.example` if needed.

## Example flow

```
HTTP Request → router.py → service.py → repository.py → models.py / DB
                ↓
            schemas.py (validate in/out)
```
