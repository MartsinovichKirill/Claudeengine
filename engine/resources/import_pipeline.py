"""Non-destructive media import shared by previews and runtime resources."""
import hashlib
import io
import json
import wave
import zlib
from pathlib import Path
from engine.resources.prefab import atomic_json, resource_path

AUDIO_MAGIC=b'CLOUD-AUDIO-1\x00'


def import_settings(path):
    try:
        data=json.loads(Path(str(path)+'.import.json').read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):
        return {}


def imported_path(path, project_dir):
    data=import_settings(path)
    if data.get('processed') and project_dir:
        target=resource_path(project_dir,data['processed'])
        if target.is_file(): return str(target)
    return str(path)


def texture_preview(path, settings):
    import pygame
    source=pygame.image.load(str(path))
    maximum=int(settings.get('max_size',4096))
    ratio=min(1,maximum/max(source.get_size()))
    size=(max(1,round(source.get_width()*ratio)),max(1,round(source.get_height()*ratio)))
    filtering=settings.get('filter','nearest')
    result=(pygame.transform.smoothscale if filtering=='linear' else pygame.transform.scale)(source,size)
    width=max(1,int(settings.get('frame_width',size[0])))
    height=max(1,int(settings.get('frame_height',size[1])))
    frames=[{'x':x,'y':y,'width':width,'height':height}
        for y in range(0,size[1]-height+1,height) for x in range(0,size[0]-width+1,width)] if settings.get('atlas') else []
    if settings.get('atlas'):
        if not frames: raise ValueError('Размер кадра больше обработанной текстуры')
        size=(size[0]//width*width,size[1]//height*height)
        result=result.subsurface((0,0,*size)).copy()
    output=io.BytesIO(); pygame.image.save(result,output,'.png')
    return output.getvalue(),{'width':size[0],'height':size[1],'frames':frames,'filter':filtering}


def decode_audio(path):
    import numpy as np
    raw=Path(path).read_bytes()
    if raw.startswith(AUDIO_MAGIC): raw=zlib.decompress(raw[len(AUDIO_MAGIC):])
    try:
        with wave.open(io.BytesIO(raw),'rb') as stream:
            rate=stream.getframerate(); channels=stream.getnchannels(); width=stream.getsampwidth()
            if stream.getcomptype()!='NONE': raise ValueError('Нужен PCM WAV')
            data=stream.readframes(stream.getnframes())
        if width==1: samples=(np.frombuffer(data,np.uint8).astype(np.float32)-128)/128
        elif width==2: samples=np.frombuffer(data,'<i2').astype(np.float32)/32768
        elif width==3:
            parts=np.frombuffer(data,np.uint8).reshape(-1,3).astype(np.int32)
            values=parts[:,0]|(parts[:,1]<<8)|(parts[:,2]<<16)
            values=np.where(values&0x800000,values-0x1000000,values)
            samples=values.astype(np.float32)/8388608
        elif width==4: samples=np.frombuffer(data,'<i4').astype(np.float32)/2147483648
        else: raise ValueError('Неподдерживаемая битность WAV')
        return samples.reshape(-1,channels),rate
    except (wave.Error,EOFError):
        import pygame
        if not pygame.mixer.get_init(): pygame.mixer.init(frequency=44100,size=-16,channels=2)
        sound=pygame.mixer.Sound(file=io.BytesIO(raw))
        samples=pygame.sndarray.array(sound)
        rate,bits,channels=pygame.mixer.get_init()
        samples=samples.astype(np.float32)/(2**(abs(bits)-1))
        if bits>0: samples-=1.0
        return samples.reshape(-1,channels),rate


def audio_preview(path, settings):
    import numpy as np
    samples,source_rate=decode_audio(path)
    target_rate=int(settings.get('sample_rate',44100))
    if target_rate not in (8000,11025,16000,22050,32000,44100,48000):
        raise ValueError('Неподдерживаемая частота')
    channels=int(settings.get('channels',2))
    if channels not in (1,2): raise ValueError('Нужны один или два канала')
    if channels==1: samples=samples.mean(axis=1,keepdims=True)
    elif samples.shape[1]==1: samples=np.repeat(samples,2,axis=1)
    else: samples=samples[:,:2]
    if target_rate<source_rate and len(samples)>64:
        # Anti-aliasing before downsampling.
        index=np.arange(-31,32,dtype=np.float64)
        cutoff=.45*target_rate/source_rate
        kernel=2*cutoff*np.sinc(2*cutoff*index)*np.hanning(63); kernel/=kernel.sum()
        samples=np.stack([np.convolve(samples[:,channel],kernel,mode='same') for channel in range(channels)],axis=1)
    if target_rate!=source_rate and len(samples):
        count=max(1,round(len(samples)*target_rate/source_rate))
        positions=np.arange(count)*source_rate/target_rate
        samples=np.stack([np.interp(positions,np.arange(len(samples)),samples[:,channel]) for channel in range(channels)],axis=1)
    bits=int(settings.get('bits',16))
    if bits not in (8,16): raise ValueError('Поддерживается PCM 8 или 16 бит')
    samples=np.clip(samples,-1,1)
    pcm=((samples*127+128).round().astype(np.uint8) if bits==8 else (samples*32767).round().astype('<i2')).tobytes()
    output=io.BytesIO()
    with wave.open(output,'wb') as stream:
        stream.setnchannels(channels); stream.setsampwidth(bits//8); stream.setframerate(target_rate); stream.writeframes(pcm)
    wav=output.getvalue()
    compressed=settings.get('codec','wav')=='cloud'
    result=AUDIO_MAGIC+zlib.compress(wav,9) if compressed else wav
    return result,wav,{'sample_rate':target_rate,'channels':channels,'bits':bits,
                      'duration':len(samples)/target_rate,'decoded_bytes':len(pcm),'extension':'.caudio' if compressed else '.wav'}


def apply_import(source, project_dir, target_dir, kind, settings):
    """Keep the source unchanged; replace only this asset's derived output."""
    import os
    import tempfile
    import shutil
    source=Path(source).resolve(); root=Path(project_dir).resolve()
    target_dir=resource_path(root,target_dir); target_dir.mkdir(parents=True,exist_ok=True)
    original=source if source.is_relative_to(root) else target_dir/source.name
    if original!=source and original.exists():
        raise ValueError('Исходный файл уже существует в проекте. Переименуйте его или откройте настройки существующего ресурса.')
    if kind=='texture':
        content,metadata=texture_preview(source,settings); extension='.png'
    elif kind=='audio':
        content,_,metadata=audio_preview(source,settings); extension=metadata['extension']
    else: raise ValueError('Неизвестный тип импорта')
    relative=original.relative_to(root).as_posix()
    key=hashlib.sha256(relative.encode()).hexdigest()[:12]
    output=root/'assets'/'Imported'/(original.stem+'_'+key+extension)
    old=import_settings(original)
    if output.exists() and old.get('processed')!=output.relative_to(root).as_posix():
        raise ValueError('Выходной файл уже существует и не принадлежит этому импорту')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('wb',dir=output.parent,delete=False) as stream:
        stream.write(content); temporary=Path(stream.name)
    try:
        if original!=source: shutil.copy2(source,original)
        os.replace(temporary,output)
        data={'version':1,'kind':kind,'source':relative,'processed':output.relative_to(root).as_posix(),
              'settings':settings,'metadata':metadata,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
        atomic_json(str(original)+'.import.json',data)
    finally:
        temporary.unlink(missing_ok=True)
    return str(original)
