from typing import Optional, List
from pgdbm import AsyncDatabaseManager

from llmring_server.models.aliases import Alias


class AliasesService:
    def __init__(self, db: AsyncDatabaseManager):
        self.db = db

    async def list_aliases(self, project_id: str) -> List[Alias]:
        rows = await self.db.fetch_all(
            "SELECT * FROM {{tables.aliases}} WHERE project_id = $1 ORDER BY alias",
            project_id,
        )
        return [Alias(**row) for row in rows]

    async def get_alias(self, project_id: str, alias: str) -> Optional[Alias]:
        row = await self.db.fetch_one(
            "SELECT * FROM {{tables.aliases}} WHERE project_id = $1 AND alias = $2",
            project_id,
            alias,
        )
        return Alias(**row) if row else None

    async def upsert_alias(self, project_id: str, alias: str, model: str, metadata: Optional[dict] = None) -> Alias:
        await self.db.execute(
            """
            INSERT INTO {{tables.aliases}} (project_id, alias, model, metadata)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (project_id, alias) DO UPDATE SET
                model = EXCLUDED.model,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            """,
            project_id,
            alias,
            model,
            metadata,
        )
        saved = await self.get_alias(project_id, alias)
        assert saved is not None
        return saved

    async def delete_alias(self, project_id: str, alias: str) -> bool:
        result = await self.db.execute(
            "DELETE FROM {{tables.aliases}} WHERE project_id = $1 AND alias = $2",
            project_id,
            alias,
        )
        return result.startswith("DELETE ")


