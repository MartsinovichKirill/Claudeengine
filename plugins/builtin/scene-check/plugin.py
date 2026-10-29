from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Проверка сцены", lambda: activate(context, "validator"))

