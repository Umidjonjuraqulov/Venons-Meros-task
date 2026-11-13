from logging import ERROR, WARNING

from src.bitrix import BitrixAPI
from src.db.database import BitrixDB
from src.db.models import TaskGroup, Stage, Department, DepartmentUser, User
from src.classes.cls_const import AccessLevelConst
from src.classes.models.logger import LogWriter


class BaseBitSync:
    def __init__(
            self, bitrix_api: BitrixAPI, db: BitrixDB, loger: LogWriter,
            tg_id_field: str | None = None, user_manager=None
    ) -> None:
        """
        tg_id_field: code of the Bitrix user field holding the Telegram ID (e.g. "UF_USR_1794565374094");
            empty disables linking Bitrix users to Telegram accounts.
        user_manager: UsersManager whose cache is dropped for every tg_id the sync links.
        """
        self.bitrix = bitrix_api
        self.db = db
        self.logger = loger
        self.tg_id_field = tg_id_field
        self.user_manager = user_manager

    @staticmethod
    def parse_tg_id(value) -> int | None:
        """Bitrix returns the field as a string (a list if the field is multiple); anything but digits is ignored."""
        if isinstance(value, list):
            value = value[0] if value else None

        value = str(value or "").strip()
        return int(value) if value.isdigit() else None

    def forget_cached_user(self, *tg_ids: int | None) -> None:
        if self.user_manager:
            for tg_id in tg_ids:
                if tg_id:
                    self.user_manager.delete_user(tg_id)

    async def sync_users(self):
        try:
            bit_users = await self.bitrix.get_users()
            users_in_db = await self.db.get_user()
            bit_users_in_db: dict[int, User] = {user.bit_user_id: user for user in users_in_db if user.bit_user_id}
            tg_users_in_db: dict[int, User] = {user.tg_id: user for user in users_in_db if user.tg_id}

        except Exception as e:
            await self.logger.send_log(ERROR, "BitSync -> sync_users", e, msg="error getting users from bitrix")
            return

        for user in bit_users:
            try:
                if user.get("ACTIVE") is False:   # skip fired employees
                    continue

                user_bit_id = int(user.get("ID"))
                full_name = f"{user.get('LAST_NAME')} {user.get('NAME')} {user.get('SECOND_NAME', '')}"
                tg_id = self.parse_tg_id(user.get(self.tg_id_field)) if self.tg_id_field else None

                user_in_db = bit_users_in_db.get(user_bit_id)
                if user_in_db and user_in_db.full_name != full_name:
                    user_in_db = await self.db.update_user_fields(user_in_db.id, full_name=full_name) or user_in_db
                    bit_users_in_db[user_bit_id] = user_in_db

                if tg_id:
                    user_in_db = await self.link_tg_user(user_bit_id, full_name, tg_id, user_in_db, tg_users_in_db)
                    if user_in_db:
                        bit_users_in_db[user_bit_id] = user_in_db

                if not user_in_db:
                    user_in_db = await self.db.add_user(full_name, AccessLevelConst.BITRIX, bit_user_id=user_bit_id)
                    bit_users_in_db[user_bit_id] = user_in_db

            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> sync_users", e, msg=f"sync {user=}")

    async def link_tg_user(
            self, user_bit_id: int, full_name: str, tg_id: int,
            user_in_db: User | None, tg_users_in_db: dict[int, User]
    ) -> User | None:
        """Connect the Bitrix user to the Telegram account from its "Telegram ID" field.

        - nobody in the DB has this tg_id: put it on the Bitrix user (created here if missing),
          so the person is recognised when they open the bot;
        - the person already registered in the bot: link that row to Bitrix, merging the
          Bitrix-only row into it if there is one.
        Conflicts (the tg_id or the Bitrix user already linked elsewhere) are left alone and logged,
        so a typo in Bitrix can't detach a working account.
        Returns the DB row now holding user_bit_id, or None if there isn't one yet.
        """
        tg_user = tg_users_in_db.get(tg_id)
        if user_in_db and tg_user and user_in_db.id == tg_user.id:
            return user_in_db  # already linked

        if tg_user and tg_user.bit_user_id:
            self.logger.write_log(
                WARNING, "BitSync -> link_tg_user",
                msg=f"Telegram ID {tg_id} of Bitrix user {user_bit_id} already belongs to Bitrix user "
                    f"{tg_user.bit_user_id} (db id {tg_user.id}); not linked"
            )
            return user_in_db

        if user_in_db and user_in_db.tg_id:
            self.logger.write_log(
                WARNING, "BitSync -> link_tg_user",
                msg=f"Bitrix user {user_bit_id} (db id {user_in_db.id}) already has Telegram ID "
                    f"{user_in_db.tg_id}, Bitrix field says {tg_id}; not changed"
            )
            return user_in_db

        if tg_user:  # registered in the bot before the sync knew the tg_id
            if user_in_db:
                linked = await self.db.merge_users(
                    to_user_id=tg_user.id, from_user_id=user_in_db.id, bit_user_id=user_bit_id
                )
            else:
                linked = await self.db.update_user_fields(tg_user.id, bit_user_id=user_bit_id, full_name=full_name)

            if not linked:
                raise Exception(f"linking Bitrix user {user_bit_id} to db user {tg_user.id} (tg {tg_id}) failed")

        elif user_in_db:  # not in the bot yet: pre-link so the first /start finds the account
            linked = await self.db.update_user_fields(user_in_db.id, tg_id=tg_id)

        else:
            linked = await self.db.add_user(full_name, AccessLevelConst.BITRIX, tg_id=tg_id, bit_user_id=user_bit_id)

        if not linked:  # a failed pre-link must not make sync_users add a duplicate row
            return user_in_db

        tg_users_in_db[tg_id] = linked
        self.forget_cached_user(tg_id)
        return linked

    async def sync_groups(self):
        try:
            bit_groups = await self.bitrix.get_groups()
            groups_in_db = await self.db.select_info(TaskGroup.bit_group_id)
        except Exception as e:
            await self.logger.send_log(ERROR, "BitSync -> sync_groups", e, msg="error getting groups from bitrix")
            return

        for group in bit_groups:
            try:
                group_bit_id = int(group.get("GROUP_ID"))
                name = group.get("GROUP_NAME")
                if group_bit_id not in groups_in_db:
                    folder_id = await self.bitrix.create_folder(
                        target_id=self.bitrix.conf.data.user_storage_id, name=name, subfolder=False
                    )
                    await self.db.add_task_group(bit_group_id=int(group_bit_id), bit_folder_id=folder_id, title=name)

            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> sync_groups", e, msg=f"get {group=}")

    async def sync_stages(self):
        try:
            groups_in_db = await self.db.get_task_group()
        except Exception as e:
            await self.logger.send_log(ERROR, "BitSync -> sync_stages", e, msg="error getting groups from db")
            return

        for group in groups_in_db:
            try:
                bit_stages = await self.bitrix.get_stages(group_id=group.bit_group_id)
                stages_in_db = {stage.bit_stage_id: stage for stage in await self.db.get_task_stage(group_id=group.id)}
            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> sync_stages", e, msg="error getting stages from bitrix")
                continue

            for stage_id, stage_info in bit_stages.items():
                stage_id = int(stage_id)
                try:
                    if stage_id in stages_in_db.keys():
                        update = False
                        s = stages_in_db.get(stage_id)
                        if s.sort != int(stage_info["SORT"]):
                            s.sort = int(stage_info["SORT"])
                            update = True

                        if s.title != stage_info["TITLE"]:
                            s.title = stage_info["TITLE"]
                            update = True

                        if update:
                            await self.db.update_task_stage(s)

                        del stages_in_db[stage_id]

                    else:
                        await self.db.add_task_stage(
                            group_id=group.id,
                            bit_stage_id=stage_id,
                            bit_sort=int(stage_info["SORT"]),
                            title=stage_info["TITLE"]
                        )
                except Exception as e:
                    await self.logger.send_log(ERROR, "BitSync -> sync_stages", e, msg=f"sync {stage_info=}")

            # delete stages that are not in bitrix but are in the DB
            for stage_bit_id_del, stage_info_del in stages_in_db.items():
                try:
                    await self.db.delete_info(selected_model=Stage, id_=stage_info_del.id)
                except Exception as e:
                    await self.logger.send_log(ERROR, "BitSync -> sync_stages", e, msg=f"del {stage_info_del=}")

    async def sync_departments(self):
        try:
            departments_in_bit = await self.bitrix.get_departments()
            departments_in_db = {d.bit_dep_id: d for d in await self.db.get_department(bit_filter=True)}
            checked_departments = set()
        except Exception as e:
            await self.logger.send_log(ERROR, "BitSync -> sync_departments", e, msg="error getting departments_in_bit")
            return

        for bit_dep in departments_in_bit:
            try:
                bit_dep_id = int(bit_dep.get("ID"))
                checked_departments.add(bit_dep_id)

                # Check new departments
                if bit_dep_id not in departments_in_db:
                    """Create new department if it doesn't exist"""
                    parent_bit_id = int(bit_dep["PARENT"]) if bit_dep.get("PARENT") else None
                    if parent_bit_id in departments_in_db:
                        parent_id = departments_in_db.get(int(parent_bit_id)).id
                    else:
                        parent_id = None

                    department_in_db = await self.db.add_department(
                        bit_dep_id=int(bit_dep.get("ID")),
                        name=bit_dep.get("NAME"),
                        parent_id=parent_id
                    )
                    departments_in_db[bit_dep_id] = department_in_db

                # Check existing
                else:
                    department_in_db = departments_in_db[bit_dep_id]
                    change = False

                    if department_in_db.name != bit_dep.get("NAME"):
                        change = True
                        department_in_db.name = bit_dep.get("NAME")

                    if bit_dep.get("PARENT"):
                        parent_in_db = departments_in_db.get(int(bit_dep["PARENT"]))
                        parent_id = departments_in_db[parent_in_db.bit_dep_id].id if parent_in_db else None
                    else:
                        parent_id = None

                    if department_in_db.parent_id != parent_id:
                        change = True
                        department_in_db.parent_id = parent_id

                    if change:
                        await self.db.update_department(department=department_in_db)

                await self.check_head(
                    department_db_id=department_in_db.id,
                    head_bit_user_id=int(bit_dep.get("UF_HEAD", 0)) or None,
                    parent_department_db_id=parent_id
                )
            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> sync_departments", e, msg=f"sync {bit_dep=}")

        # Delete
        for dep_bit_id, dep_info in departments_in_db.items():
            try:
                if dep_bit_id not in checked_departments:
                    await self.db.delete_info(selected_model=Department, id_=dep_info.id)
            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> sync_departments", e, msg=f"del {dep_info=}")

    async def check_head(
            self, department_db_id: int, head_bit_user_id: int = None, parent_department_db_id: int = None
    ):
        try:
            # get all managers with bit_id
            managers: dict[int, DepartmentUser] = {
                dep_user.user.bit_user_id: dep_user
                for dep_user in await self.db.get_dep_users(department_id=department_db_id, head=True)
                if dep_user.user.bit_user_id
            }

            # if department not have head/manager
            if ((head_bit_user_id is None) or (head_bit_user_id == 0)) and parent_department_db_id:
                parent_head = await self.db.get_dep_users(department_id=parent_department_db_id, head=True)
                if parent_head[0].user.bit_user_id in managers:
                    del managers[parent_head[0].user.bit_user_id]
                else:
                    await self.db.add_dep_user(user_id=parent_head[0].user_id, head=True, department_id=department_db_id)

            # if in db, check him
            elif head_bit_user_id in managers:
                del managers[head_bit_user_id]

            # else add him
            else:
                head = await self.db.get_user(bit_id=head_bit_user_id)
                await self.db.add_dep_user(user_id=head[0].id, head=True, department_id=department_db_id)

            for del_manager in managers.values():
                await self.db.delete_info(selected_model=DepartmentUser, id_=del_manager.id)

        except Exception as e:
            await self.logger.send_log(
                ERROR,
                "BitSync -> check_head",
                e,
                msg=f"sync {department_db_id=}, {head_bit_user_id=}, {parent_department_db_id=}"
            )

    async def sync_departments_users(self):
        try:
            all_bit_users = {user.bit_user_id: user for user in await self.db.get_users(with_bit_id=True)}
            dep_in_db = await self.db.get_department()
            dep_users_in_db: dict[int, dict[int, DepartmentUser]] = {i.id: {} for i in dep_in_db}
            print(all_bit_users)
            for dep_user in await self.db.get_dep_users():  # Get all department users in db with bit_id
                if dep_user.user.bit_user_id:
                    dep_users_in_db[dep_user.department_id][dep_user.user.bit_user_id] = dep_user

        except Exception as e:
            await self.logger.send_log(ERROR, "BitSync -> sync_departments_users", e, msg="getting from bitrix/db")
            return

        for department in dep_in_db:
            try:
                department_employees_bit = await self.bitrix.employees_departments(department.bit_dep_id)
            except Exception as e:
                await self.logger.send_log(
                    ERROR, "BitSync -> sync_departments_users", e, msg=f"get from db {department=}"
                )
                return

            for employee in department_employees_bit:
                try:
                    employee_bit_id = int(employee.get("ID"))
                    employee_status = employee.get("ACTIVE")
                    print(employee_bit_id)
                    print(employee_status)

                    if employee_bit_id not in dep_users_in_db[department.id]:
                        if employee_status is False:  # Skip users with ACTIVE == False
                            continue
                        print(f"\ng\ng\ng\ng, {department.id}, {employee_bit_id}")
                        await self.db.add_dep_user(
                            user_id=all_bit_users[employee_bit_id].id, head=False, department_id=department.id
                        )

                    else:
                        # delete existing to delete irrelevant
                        del dep_users_in_db[department.id][employee_bit_id]

                except Exception as e:
                    await self.logger.send_log(
                        ERROR, "BitSync -> sync_departments_users", e, msg=f"sync {employee=}"
                    )

            for deleting_dep_user in dep_users_in_db[department.id].values():
                try:
                    if not deleting_dep_user.head:
                        await self.db.delete_info(selected_model=DepartmentUser, id_=deleting_dep_user.id)
                except Exception as e:
                    await self.logger.send_log(
                        ERROR, "BitSync -> sync_departments_users", e, msg=f"del {deleting_dep_user=}"
                    )
