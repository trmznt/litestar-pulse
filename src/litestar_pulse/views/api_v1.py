from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "LGPL v3 or later"

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from litestar import Controller, delete, get, patch, post
from litestar.dto import DTOConfig, DTOData
from litestar.exceptions import NotFoundException
from litestar.plugins.sqlalchemy import SQLAlchemyDTO

# from litestar_pulse.lib.sqlalchemy_imports import SQLAlchemyDTO

from litestar_pulse.db.models.account import UserDomain


class UserDomainReadDTO(SQLAlchemyDTO[UserDomain]):
    config = DTOConfig(exclude={"users", "updated_by"})


class UserDomainCreateDTO(SQLAlchemyDTO[UserDomain]):
    config = DTOConfig(
        exclude={
            "id",
            "uuid",
            "users",
            "created_at",
            "updated_at",
            "updated_by_id",
            "updated_by",
        }
    )


class UserDomainUpdateDTO(SQLAlchemyDTO[UserDomain]):
    config = DTOConfig(
        exclude={
            "id",
            "uuid",
            "users",
            "created_at",
            "updated_at",
            "updated_by_id",
            "updated_by",
        },
        partial=True,
    )


class API_v1(Controller):
    """
    API_v1 is the controller for API version 1
    """

    path = "/api-lp/v1"

    @get("/userdomain-list", return_dto=UserDomainReadDTO)
    async def userdomain_list(self, transaction: AsyncSession) -> list[UserDomain]:
        """
        API endpoint to get the list of user domains
        """
        stmt = select(UserDomain).order_by(UserDomain.domain)
        result = await transaction.execute(stmt)
        return result.scalars().all()

    @post(
        "/userdomain",
        dto=UserDomainCreateDTO,
        return_dto=UserDomainReadDTO,
    )
    async def userdomain_create(
        self, data: DTOData[UserDomain], transaction: AsyncSession
    ) -> UserDomain:
        """
        API endpoint to create a new user domain
        """
        domain = data.create_instance()
        transaction.add(domain)
        await transaction.flush()
        await transaction.refresh(domain)
        return domain

    @get("/userdomain/{dbid:int}", return_dto=UserDomainReadDTO)
    async def userdomain_view(self, dbid: int, transaction: AsyncSession) -> UserDomain:
        """
        API endpoint to get the detail of a user domain by ID
        """
        stmt = select(UserDomain).where(UserDomain.id == dbid)
        result = await transaction.execute(stmt)
        domain = result.scalar_one_or_none()

        if domain is None:
            raise NotFoundException("UserDomain not found")

        return domain

    @patch(
        "/userdomain/{dbid:int}",
        dto=UserDomainUpdateDTO,
        return_dto=UserDomainReadDTO,
    )
    async def userdomain_update(
        self,
        dbid: int,
        data: DTOData[UserDomain],
        transaction: AsyncSession,
    ) -> UserDomain:
        """
        API endpoint to update a user domain by ID
        """
        stmt = select(UserDomain).where(UserDomain.id == dbid)
        result = await transaction.execute(stmt)
        domain = result.scalar_one_or_none()

        if domain is None:
            raise NotFoundException("UserDomain not found")

        data.update_instance(domain)
        await transaction.flush()
        await transaction.refresh(domain)

        return domain

    @delete("/userdomain/{dbid:int}")
    async def userdomain_delete(self, dbid: int, transaction: AsyncSession) -> None:
        """
        API endpoint to delete a user domain by ID
        """
        stmt = select(UserDomain).where(UserDomain.id == dbid)
        result = await transaction.execute(stmt)
        domain = result.scalar_one_or_none()

        if domain is None:
            raise NotFoundException("UserDomain not found")

        await transaction.delete(domain)
        return None


# EOF
