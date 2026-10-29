from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Заметки проекта", lambda: activate(context, "notes"))

