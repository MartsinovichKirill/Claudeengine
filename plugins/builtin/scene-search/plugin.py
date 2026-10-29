from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Поиск объектов", lambda: activate(context, "find"))

