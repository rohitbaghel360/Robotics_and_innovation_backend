"""
Feature modules — each service lives in its own folder.

Standard layout per module:
  router.py      → HTTP endpoints (thin)
  service.py     → business logic
  repository.py  → database access
  models.py      → SQLAlchemy ORM entities
  schemas.py     → Pydantic request/response DTOs
"""
