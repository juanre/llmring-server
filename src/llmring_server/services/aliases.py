from typing import List, Optional

from pgdbm import AsyncDatabaseManager

from llmring_server.models.aliases import Alias


class AliasesService:
    def __init__(self, db: AsyncDatabaseManager):
        self.db = db

    async def list_aliases(
        self, project_id: str, profile: str | None = None
    ) -> List[Alias]:
        if profile:
            rows = await self.db.fetch_all(
                "SELECT * FROM {{tables.aliases}} WHERE project_id = $1 AND profile = $2 ORDER BY alias",
                project_id,
                profile,
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT * FROM {{tables.aliases}} WHERE project_id = $1 ORDER BY alias",
                project_id,
            )
        return [Alias(**row) for row in rows]

    async def get_alias(
        self, project_id: str, alias: str, profile: str = "default"
    ) -> Optional[Alias]:
        row = await self.db.fetch_one(
            "SELECT * FROM {{tables.aliases}} WHERE project_id = $1 AND profile = $2 AND alias = $3",
            project_id,
            profile,
            alias,
        )
        return Alias(**row) if row else None

    async def upsert_alias(
        self,
        project_id: str,
        alias: str,
        model: str,
        metadata: Optional[dict] = None,
        profile: str = "default",
    ) -> Alias:
        await self.db.execute(
            """
            INSERT INTO {{tables.aliases}} (project_id, profile, alias, model, metadata)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (project_id, profile, alias) DO UPDATE SET
                model = EXCLUDED.model,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            """,
            project_id,
            profile,
            alias,
            model,
            metadata,
        )
        saved = await self.get_alias(project_id, alias, profile)
        assert saved is not None
        return saved

    async def delete_alias(
        self, project_id: str, alias: str, profile: str = "default"
    ) -> bool:
        result = await self.db.execute(
            "DELETE FROM {{tables.aliases}} WHERE project_id = $1 AND profile = $2 AND alias = $3",
            project_id,
            profile,
            alias,
        )
        return result.startswith("DELETE ")

    async def bulk_upsert(
        self, project_id: str, profile: str, items: list[dict]
    ) -> int:
        affected = 0
        for item in items:
            await self.upsert_alias(
                project_id=project_id,
                alias=item["alias"],
                model=item["model"],
                metadata=item.get("metadata"),
                profile=profile,
            )
            affected += 1
        return affected
