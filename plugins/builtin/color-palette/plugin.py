from editor.builtin_plugin_tools import activate

def setup(context):
    context.add_action("Палитра объектов", lambda: activate(context, "palette"))

