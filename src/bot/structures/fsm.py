from aiogram.fsm.state import State, StatesGroup


class User(StatesGroup):
    main_menu = State()

    # Create Task
    create_task_group = State()
    create_task_region = State()
    create_task_title = State()
    create_task_description = State()
    create_task_files = State()

    # My tasks
    my_tasks = State()
    my_task_info = State()
    my_task_write_comment = State()
    change_stage = State()
    delete_task = State()

    # group status
    group_status = State()

    # write review
    write_review = State()


class Registration(StatesGroup):
    language = State()
    name = State()
    job_title = State()
    phone = State()
    checking = State()
