from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Привязка к сетке", lambda: activate(context, "grid"))

