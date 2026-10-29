from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Резервная копия", lambda: activate(context, "backup"))

