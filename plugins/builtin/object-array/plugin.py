from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Ряд объектов", lambda: activate(context, "array"))

