"""Реестр встроенных нод Cloud Engine.

Собирает все классы нод в словарь NODE_CLASSES (имя типа -> класс),
используемый сериализатором сцен и инспектором.
"""

from __future__ import annotations

from engine.core.node import Node
from engine.nodes.game_object import GameObject
from engine.nodes.node2d import Node2D
from engine.nodes.sprite2d import Sprite2D
from engine.nodes.animated_sprite import AnimatedSprite2D
from engine.nodes.camera2d import Camera2D, CameraState
from engine.nodes.collision_shape import CollisionShape2D
from engine.nodes.rigidbody2d import RigidBody2D, PhysicsBody2D
from engine.nodes.staticbody2d import StaticBody2D
from engine.nodes.characterbody2d import CharacterBody2D
from engine.nodes.area2d import Area2D
from engine.nodes.raycast2d import RayCast2D
from engine.nodes.tilemap import TileMap
from engine.nodes.particles2d import Particles2D
from engine.nodes.audio_stream import AudioStreamPlayer, AudioStreamPlayer2D
from engine.nodes.timer import Timer
from engine.nodes.parallax_bg import ParallaxBackground, ParallaxLayer
from engine.nodes.parallax2d import Parallax2D
from engine.nodes.canvas_layer import CanvasLayer, TextureRect
from engine.nodes.label import Label
from engine.nodes.button import Button
from engine.nodes.progress_bar import ProgressBar
from engine.nodes.animation_player import AnimationPlayer
from engine.nodes.light2d import Light2D, CanvasModulate, LightOccluder2D
from engine.nodes.post_process import PostProcess

#: Реестр классов нод: имя типа -> класс.
NODE_CLASSES = {
    'GameObject': GameObject,
    "Node": Node,
    "Node2D": Node2D,
    "Sprite2D": Sprite2D,
    "AnimatedSprite2D": AnimatedSprite2D,
    "Camera2D": Camera2D,
    "CollisionShape2D": CollisionShape2D,
    "RigidBody2D": RigidBody2D,
    "PhysicsBody2D": PhysicsBody2D,
    "StaticBody2D": StaticBody2D,
    "CharacterBody2D": CharacterBody2D,
    "Area2D": Area2D,
    "RayCast2D": RayCast2D,
    "TileMap": TileMap,
    "Particles2D": Particles2D,
    "AudioStreamPlayer": AudioStreamPlayer,
    "AudioStreamPlayer2D": AudioStreamPlayer2D,
    "Timer": Timer,
    "ParallaxBackground": ParallaxBackground,
    "ParallaxLayer": ParallaxLayer,
    "Parallax2D": Parallax2D,
    "CanvasLayer": CanvasLayer,
    "TextureRect": TextureRect,
    "Label": Label,
    "Button": Button,
    "ProgressBar": ProgressBar,
    # Анимация, свет и постобработка.
    "AnimationPlayer": AnimationPlayer,
    "Light2D": Light2D,
    "CanvasModulate": CanvasModulate,
    "LightOccluder2D": LightOccluder2D,
    "PostProcess": PostProcess,
}

#: Категории нод для контекстного меню «Добавить ноду».
NODE_CATEGORIES = {
    'Объект': ['GameObject'],
    "Node": ["Node"],
    "Node2D": ["Node2D", "Sprite2D", "AnimatedSprite2D", "Camera2D",
               "ParallaxBackground", "Parallax2D", "Particles2D", "TileMap", "RayCast2D"],
    "Physics": ["StaticBody2D", "RigidBody2D", "CharacterBody2D",
                "Area2D", "CollisionShape2D"],
    "Анимация": ["AnimationPlayer"],
    "Свет": ["Light2D", "CanvasModulate", "LightOccluder2D"],
    "Рендер": ["PostProcess"],
    "Audio": ["AudioStreamPlayer", "AudioStreamPlayer2D"],
    "UI": ["CanvasLayer", "Label", "Button", "ProgressBar", "TextureRect"],
    "Utility": ["Timer"],
}

__all__ = ["NODE_CLASSES", "NODE_CATEGORIES"]
