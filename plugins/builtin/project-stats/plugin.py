from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Статистика проекта", lambda: activate(context, "statistics"))

