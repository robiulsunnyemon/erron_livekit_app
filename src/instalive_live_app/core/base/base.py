from beanie import Document
from pydantic import Field
from uuid import UUID, uuid4
from pydantic import BaseModel


class BaseCollection(Document):
    id: UUID = Field(default_factory=uuid4, alias="_id")

    async def fetch(self):
        """Re-fetch the document from the database to refresh its state."""
        fresh = await self.__class__.get(self.id)
        if fresh:
            # Update fields in-place
            for field in self.model_fields:
                setattr(self, field, getattr(fresh, field))
        return self


class BaseResponse(BaseModel):
    id: UUID
