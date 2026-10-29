"""Catalog for component authoring. No prebuilt gameplay behaviours."""
from engine.components.component import Component

COMPONENT_CLASSES = {}
COMPONENT_CATEGORIES = {}
VISUAL_COMPONENTS = frozenset()
HIDDEN_COMPONENTS = frozenset({'Transform'})

def get_component_class(type_name):
    return COMPONENT_CLASSES.get(type_name)

def create_component(type_name):
    cls = get_component_class(type_name)
    return cls() if cls else None

def register_component(cls, category='Прочее', visual=False):
    global VISUAL_COMPONENTS
    name = cls.get_type_name()
    COMPONENT_CLASSES[name] = cls
    if visual:
        VISUAL_COMPONENTS = VISUAL_COMPONENTS | {name}
        return
    bucket = COMPONENT_CATEGORIES.setdefault(category, [])
    if name not in bucket:
        bucket.append(name)

def is_visual_component(type_name):
    return type_name in VISUAL_COMPONENTS

def is_hidden(type_name):
    return type_name in HIDDEN_COMPONENTS or is_visual_component(type_name)

def visible_categories():
    return {category: [name for name in names if not is_hidden(name)]
        for category, names in COMPONENT_CATEGORIES.items()
        if any(not is_hidden(name) for name in names)}

def all_visible_components():
    return sorted({name for names in visible_categories().values() for name in names})

def component_description(type_name):
    return getattr(get_component_class(type_name), 'description', '')

from engine.components.transform import Transform
from engine.components.object_components import SpriteRenderer, Rigidbody2D, BoxCollider2D, CircleCollider2D
from engine.components.animator import Animator
from engine.components.behaviour import ScriptBehaviour
from engine.components.audio_source import AudioSource
from engine.components.scene_features import Camera2D, Light2D
Animator.allow_multiple = False
for _cls, _category in ((Transform, 'Объект'), (SpriteRenderer, 'Отрисовка'),
        (Camera2D, 'Отрисовка'), (Light2D, 'Отрисовка'),
        (Rigidbody2D, 'Физика 2D'), (BoxCollider2D, 'Физика 2D'),
        (CircleCollider2D, 'Физика 2D'), (Animator, 'Анимация'),
        (AudioSource, 'Звук'), (ScriptBehaviour, 'Скрипты')):
    register_component(_cls, _category)

from engine.components.technical import TECHNICAL_COMPONENTS
for _cls, _category in TECHNICAL_COMPONENTS:
    register_component(_cls, _category)
from engine.components.ui_layout import RectTransform
register_component(RectTransform, "Интерфейс")

from engine.components.ui_layout import HorizontalLayout, VerticalLayout
register_component(HorizontalLayout,"Интерфейс")
register_component(VerticalLayout,"Интерфейс")

from engine.components.render_tools import TileMapCollider2D, TileMapTint, PostProcessVolume
register_component(TileMapCollider2D, 'TileMap')
register_component(TileMapTint, 'TileMap')
register_component(PostProcessVolume, 'Отрисовка')
from engine.components.data_source import DataSource
register_component(DataSource, 'Игровые данные')
from engine.components.enemy_ai import EnemyAI
register_component(EnemyAI, 'Поведение')
