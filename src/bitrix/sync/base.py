from logging import ERROR

from src.bitrix import BitrixAPI
from src.db.database import BitrixDB
from src.db.models import TaskGroup, Stage, Department, DepartmentUser
from src.classes.cls_const import AccessLevelConst
from src.classes.models.logger import LogWriter


class BaseBitSync:
    def __init__(
            self, bitrix_api: BitrixAPI, db: BitrixDB, loger: LogWriter
    ) -> None:
        self.bitrix = bitrix_api
        self.db = db
        self.logger = loger

    async def sync_users(self):
        try:
            bit_users = await self.bitrix.get_users()
            bit_users_in_db = {user.bit_user_id: user for user in await self.db.get_user() if user.bit_user_id}

        except Exception as e:
            await self.logger.send_log(ERROR, "BitSync -> sync_users", e, msg="error getting users from bitrix")
            return
        print(f"\n\n\n\n\n\n\n\n\n\n{bit_users}\n\n\n\n\n\n\n\n\n\n")

        for user in bit_users:
            try:
                if user.get("ACTIVE") is False:   # skip fired employees
                    print(f"\n\n\n\n\n\n\n\n\n\nuser active false {user.get('LAST_NAME')} {user.get('NAME')} {user.get('SECOND_NAME', '')}\n\n\n\n\n\n\n\n\n\n")
                    
                    continue

                user_bit_id = int(user.get("ID"))
                full_name = f"{user.get('LAST_NAME')} {user.get('NAME')} {user.get('SECOND_NAME', '')}"
                print(f"{full_name}, {AccessLevelConst.BITRIX}, {user_bit_id}")
                if user_bit_id not in bit_users_in_db:
                    await self.db.add_user(full_name, AccessLevelConst.BITRIX, bit_user_id=user_bit_id)

                else:
                    change = False
                    user_in_db = bit_users_in_db[user_bit_id]

                    if user_in_db.full_name != full_name:
                        user_in_db.full_name = full_name
                        change = True

                    if user.get("ACTIVE") is False:
                        change = True
                        user_in_db.access_level = AccessLevelConst.BLOCKED

                    if change:
                        await self.db.update_user(update_to=user_in_db)

            except Exception as e:
                await self.logger.send_log(ERROR, "BitSync -> sync_users", e, msg=f"sync {user=}")

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
                is_extranet = group.get("IS_EXTRANET", None)
                if group_bit_id not in groups_in_db and is_extranet == None:
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
