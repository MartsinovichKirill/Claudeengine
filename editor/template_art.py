"""Original procedural artwork for the platformer template."""
import random
from pathlib import Path

def create_art(directory):
    import pygame
    rng = random.Random(728)
    out = Path(directory)
    sky = pygame.Surface((1024,600))
    for y in range(600):
        t=y/600
        pygame.draw.line(sky,(int(12+16*t),int(22+24*t),int(42+30*t)),(0,y),(1023,y))
    for _ in range(180):
        x,y=rng.randrange(1024),rng.randrange(380)
        pygame.draw.circle(sky,(110,151,185),(x,y),rng.choice([1,1,2]))
    for radius,color in [(55,(29,49,76)),(44,(48,71,100)),(32,(192,213,222))]:
        pygame.draw.circle(sky,color,(750,130),radius)
    for _ in range(24):
        x,y=rng.randrange(730,772),rng.randrange(111,150)
        pygame.draw.rect(sky,(153,181,199),(x,y,5,3))
    pygame.image.save(sky,str(out/'sky.png'))
    hills=pygame.Surface((1024,600),pygame.SRCALPHA)
    for base,color in [(320,(23,44,63)),(420,(19,39,52)),(540,(14,31,40))]:
        points=[(0,600),(0,base)]
        for x in range(0,1080,48): points.append((x,base-rng.randrange(20,110)))
        points += [(1024,600)]
        pygame.draw.polygon(hills,color,points)
        for x in range(0,1024,35):
            h=rng.randrange(30,85)
            pygame.draw.polygon(hills,color,[(x,base-90-h),(x-18,base-40),(x+18,base-40)])
    pygame.image.save(hills,str(out/'hills.png'))
    player=pygame.Surface((32,48),pygame.SRCALPHA)
    pygame.draw.polygon(player,(143,54,67),[(10,20),(25,22),(30,39),(5,38)])
    pygame.draw.rect(player,(43,59,79),(10,23,13,17))
    pygame.draw.rect(player,(26,34,49),(9,38,6,9));pygame.draw.rect(player,(26,34,49),(20,38,6,9))
    pygame.draw.rect(player,(213,165,130),(12,9,13,14))
    pygame.draw.rect(player,(26,36,51),(7,5,19,10));pygame.draw.rect(player,(26,36,51),(5,10,7,12))
    pygame.draw.rect(player,(24,32,45),(22,15,3,3))
    pygame.draw.rect(player,(205,170,90),(10,31,14,3))
    pygame.image.save(player,str(out/'player.png'))
    coin=pygame.Surface((20,20),pygame.SRCALPHA)
    pygame.draw.circle(coin,(143,92,36),(10,10),9);pygame.draw.circle(coin,(244,194,78),(10,9),7)
    pygame.draw.line(coin,(255,236,154),(10,4),(10,13),2)
    pygame.image.save(coin,str(out/'coin.png'))
