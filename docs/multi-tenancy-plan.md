# MT-001 multi-tenant implementation status

MT-001 is implemented and tested locally. It has not been applied to Neon or deployed.

The design uses one shared analytics database and one frontend/backend deployment. A
canonical Shopify domain maps to an immutable internal `shops.id`. Every analytics row
has a mandatory `shop_id`, and merchant-facing SQL executes through a fail-closed
tenant-scoped SQLAlchemy session.

See `multi-tenant-architecture.md`, `tenant-authentication.md`,
`multi-tenant-migration.md`, `multi-tenant-verification-checklist.md`, and
`milestone-3-sync-plan.md` for the design and release gates.

Production gates still pending:

1. Verify a recoverable Neon backup and create an isolated Neon branch.
2. Rehearse the migration against that branch and compare live counts/KPIs.
3. Create a dedicated tenant-assertion secret and grant secret access to only the two
   existing runtime service accounts.
4. Obtain approval for the live migration, Cloud Run deployments, and IAM changes.
5. Test two authorized stores before beta onboarding.

PostgreSQL row-level security is deliberately deferred. Application authorization is
mandatory and already enforced; RLS requires separate pooling-aware testing.
