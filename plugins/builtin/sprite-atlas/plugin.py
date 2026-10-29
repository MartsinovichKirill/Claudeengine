from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Сборщик атласов", lambda: activate(context, "atlas"))

