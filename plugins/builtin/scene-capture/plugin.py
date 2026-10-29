from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Снимок сцены", lambda: activate(context, "screenshot"))

