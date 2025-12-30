from .base import Bitrix


class User(Bitrix):
    async def get_users(self) -> list[dict]:
        """Retrieve all users."""
        index = 1
        users = []
        while True:
            result = await self.call_method("user.get", params={"sort": "ID", "start": index})
            if result:
                users += result["result"]
                index += 50
                if len(result["result"]) < 50:
                    break
            else:
                return []

        return users


