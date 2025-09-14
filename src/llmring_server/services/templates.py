"""Service layer for conversation templates."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from asyncpg import PostgresError
from pgdbm import AsyncDatabaseManager

from llmring_server.models.templates import (
    ConversationTemplate,
    ConversationTemplateCreate,
    ConversationTemplateStats,
    ConversationTemplateUpdate,
)

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing conversation templates."""

    def __init__(self, db: AsyncDatabaseManager):
        self.db = db

    async def create_template(
        self, template_data: ConversationTemplateCreate
    ) -> Optional[ConversationTemplate]:
        """Create a new conversation template."""
        template_id = uuid4()
        now = datetime.now()

        query = """
        INSERT INTO conversation_templates (
            id, project_id, name, description, system_prompt,
            model, temperature, max_tokens, tool_config, created_by,
            is_active, usage_count, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING *
        """

        try:
            result = await self.db.fetch_one(
                query,
                template_id,
                template_data.project_id,
                template_data.name,
                template_data.description,
                template_data.system_prompt,
                template_data.model,
                template_data.temperature,
                template_data.max_tokens,
                template_data.tool_config,
                template_data.created_by,
                True,  # is_active
                0,  # usage_count
                now,  # created_at
                now,  # updated_at
            )

            if result:
                return ConversationTemplate(**result)
            return None

        except (PostgresError, ValueError, TypeError) as e:
            logger.error(f"Error creating conversation template: {e}")
            return None

    async def get_template(
        self, template_id: UUID, project_id: Optional[str] = None
    ) -> Optional[ConversationTemplate]:
        """Get a conversation template by ID."""
        query = """
        SELECT * FROM conversation_templates
        WHERE id = $1 AND is_active = true
        """
        params = [template_id]

        # Add project filter if specified
        if project_id:
            query += " AND (project_id = $2 OR project_id IS NULL)"
            params.append(project_id)

        try:
            result = await self.db.fetch_one(query, *params)
            if result:
                return ConversationTemplate(**result)
            return None

        except (PostgresError, ValueError, TypeError) as e:
            logger.error(f"Error getting conversation template: {e}")
            return None

    async def list_templates(
        self,
        project_id: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConversationTemplate]:
        """List conversation templates."""
        query = """
        SELECT * FROM conversation_templates
        WHERE is_active = true
        """
        params = []

        # Add filters
        if project_id:
            query += " AND (project_id = $1 OR project_id IS NULL)"
            params.append(project_id)

        if created_by:
            param_num = len(params) + 1
            query += f" AND created_by = ${param_num}"
            params.append(created_by)

        # Add ordering and pagination
        query += " ORDER BY created_at DESC"
        param_num = len(params)
        query += f" LIMIT ${param_num + 1} OFFSET ${param_num + 2}"
        params.extend([limit, offset])

        try:
            results = await self.db.fetch_all(query, *params)
            return [ConversationTemplate(**r) for r in results]

        except (PostgresError, ValueError, TypeError) as e:
            logger.error(f"Error listing conversation templates: {e}")
            return []

    async def update_template(
        self,
        template_id: UUID,
        update_data: ConversationTemplateUpdate,
        project_id: Optional[str] = None,
    ) -> Optional[ConversationTemplate]:
        """Update a conversation template."""
        # First check if template exists and belongs to project
        existing = await self.get_template(template_id, project_id)
        if not existing:
            return None

        # Build update query dynamically
        updates = []
        params = []
        param_num = 1

        for field, value in update_data.model_dump(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ${param_num}")
                params.append(value)
                param_num += 1

        if not updates:
            return existing

        # Add updated_at
        updates.append(f"updated_at = ${param_num}")
        params.append(datetime.now())
        param_num += 1

        # Add WHERE clause
        params.append(template_id)
        where_clause = f"WHERE id = ${param_num}"

        query = f"""
        UPDATE conversation_templates
        SET {', '.join(updates)}
        {where_clause}
        RETURNING *
        """

        try:
            result = await self.db.fetch_one(query, *params)
            if result:
                return ConversationTemplate(**result)
            return None

        except (PostgresError, ValueError, TypeError) as e:
            logger.error(f"Error updating conversation template: {e}")
            return None

    async def delete_template(
        self, template_id: UUID, project_id: Optional[str] = None
    ) -> bool:
        """Delete a conversation template (soft delete)."""
        query = """
        UPDATE conversation_templates
        SET is_active = false, updated_at = $1
        WHERE id = $2 AND is_active = true
        """
        params = [datetime.now(), template_id]

        # Add project filter if specified
        if project_id:
            query += " AND (project_id = $3 OR project_id IS NULL)"
            params.append(project_id)

        try:
            result = await self.db.execute(query, *params)
            return result == "UPDATE 1"

        except (PostgresError, ValueError, TypeError) as e:
            logger.error(f"Error deleting conversation template: {e}")
            return False

    async def use_template(
        self, template_id: UUID, project_id: Optional[str] = None
    ) -> Optional[ConversationTemplate]:
        """Mark a template as used and update usage statistics."""
        query = """
        UPDATE conversation_templates
        SET usage_count = usage_count + 1,
            last_used_at = $1,
            updated_at = $1
        WHERE id = $2 AND is_active = true
        """
        params = [datetime.now(), template_id]

        # Add project filter if specified
        if project_id:
            query += " AND (project_id = $3 OR project_id IS NULL)"
            params.append(project_id)

        query += " RETURNING *"

        try:
            result = await self.db.fetch_one(query, *params)
            if result:
                return ConversationTemplate(**result)
            return None

        except (PostgresError, ValueError, TypeError) as e:
            logger.error(f"Error updating template usage: {e}")
            return None

    async def get_template_stats(
        self, project_id: Optional[str] = None, limit: int = 20
    ) -> List[ConversationTemplateStats]:
        """Get usage statistics for conversation templates."""
        query = """
        SELECT id as template_id, name as template_name, usage_count,
               last_used_at, created_at
        FROM conversation_templates
        WHERE is_active = true
        """
        params = []

        # Add project filter if specified
        if project_id:
            query += " AND (project_id = $1 OR project_id IS NULL)"
            params.append(project_id)

        # Order by usage and limit
        query += " ORDER BY usage_count DESC, last_used_at DESC"
        param_num = len(params) + 1
        query += f" LIMIT ${param_num}"
        params.append(limit)

        try:
            results = await self.db.fetch_all(query, *params)
            return [ConversationTemplateStats(**r) for r in results]

        except (PostgresError, ValueError, TypeError) as e:
            logger.error(f"Error getting template stats: {e}")
            return []