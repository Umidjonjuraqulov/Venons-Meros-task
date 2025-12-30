from .base import Bitrix


class Department(Bitrix):
    async def get_departments(self) -> list[dict] | None:  # TODO
        """Returns a list of all departments."""

        index = 1
        all_departments = []
        while True:
            departments = await self.call_method(method="department.get", params={"sort": "ID", "start": index})
            if departments:
                all_departments += departments["result"]
                index += 50
                if len(departments["result"]) < 50:
                    break

        return all_departments

    async def employees_departments(self, department_id: int) -> list[dict] | None:
        """Returns a list of all users in a department."""
        result = await self.call_method(method="user.get", params={"FILTER": {"UF_DEPARTMENT": department_id}})
        if result:
            return result.get("result")
