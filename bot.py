import discord
import yt_dlp
from discord.ext import commands
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import asyncio
import shutil
import re
from urllib.parse import urlparse, parse_qs
from flask import Flask

app.run(host='0.0.0.0', port=5000)

# Configuración del bot
TOKEN = os.getenv('DISCORD_TOKEN')
SPOTIFY_CLIENT_ID = '92f72b2bc1024c88bec00469140f4ad4'
SPOTIFY_CLIENT_SECRET = '2aea17e528044bbe90e4d8cb3125cfe3'

spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='sk.', intents=intents)

# Verificación de FFmpeg
if not shutil.which("ffmpeg"):
    print("¡FFmpeg no está instalado o no está en el PATH!")
    exit()

class MyLogger:
    def debug(self, msg):
        print(f"DEBUG: {msg}")

    def info(self, msg):
        print(f"INFO: {msg}")

    def warning(self, msg):
        print(f"WARNING: {msg}")

    def error(self, msg):
        print(f"ERROR: {msg}")

# Configuración de ytdl_opts para mejorar la conexión
ytdl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': False,
    'default_search': 'ytsearch',
    'extractaudio': True,
    'extract_flat': True,  # No descarga los videos, solo obtiene los enlaces
    'prefer_ffmpeg': True,
    'no_warnings': True,
    'geo_bypass': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
    'logger': MyLogger(),
    'ffmpeg_location': 'C:\\ffmpeg\\bin',
    'cachedir': 'C:/path/to/cache'  # Cambia a la ruta de la carpeta de caché en tu sistema
}


# Opciones de FFmpeg
ffmpeg_options = {
    'executable': 'C:/ffmpeg/bin/ffmpeg.exe',  # Asegúrate de que la ruta a ffmpeg es correcta
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10',
    'options': '-vn -loglevel debug -probesize 10000000 -analyzeduration 20000000',  # Aumentando probesize y analyzeduration
}


ytdl = yt_dlp.YoutubeDL(ytdl_opts)
queue = []  # Cola global para las canciones


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True, volume=0.5, ffmpeg_options=None):
        loop = loop or asyncio.get_event_loop()
        ffmpeg_options = ffmpeg_options or {}

        try:
            # Si la URL ya es de un archivo de audio directo (como el que proporcionaste), se usa directamente.
            if url.endswith('.webm') or url.endswith('.mp3'):
                return cls(discord.FFmpegPCMAudio(url, **ffmpeg_options), data={'title': 'Audio Directo'},
                           volume=volume)

            # Si no es un enlace directo, entonces extraemos la información usando yt-dlp
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

            # Buscar un formato de audio compatible
            audio_url = None
            for fmt in data.get('formats', []):
                if fmt.get('ext') in ['m4a', 'opus']:  # Preferencia por formatos compatibles con Discord
                    audio_url = fmt['url']
                    break

            if not audio_url:
                raise Exception("No se encontró un formato de audio compatible")

            # Usar la URL de audio seleccionada
            return cls(discord.FFmpegPCMAudio(audio_url, **ffmpeg_options), data=data, volume=volume)

        except Exception as e:
            print(f"Error al extraer información de YouTube: {e}")
            return None

async def search_media(query):
    # Patrones para detectar enlaces de YouTube y Spotify
    youtube_video_pattern = r"(https?://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]+))|(?:https?://youtu\.be/([A-Za-z0-9_-]+))"
    youtube_playlist_pattern = r"https?://(?:www\.)?youtube\.com/playlist\?list=([A-Za-z0-9_-]+)"
    spotify_track_pattern = r"https?://(?:open\.)?spotify\.com(?:/[a-zA-Z0-9_-]+)?/track/([A-Za-z0-9_-]+)(?:\?[^ ]*)?"
    spotify_playlist_pattern = r"https?://(?:open\.)?spotify\.com/playlist/([A-Za-z0-9_-]+)"

    # Verificar si es un enlace de YouTube o Spotify
    match_youtube_video = re.match(youtube_video_pattern, query)
    match_youtube_playlist = re.match(youtube_playlist_pattern, query)
    match_spotify_track = re.match(spotify_track_pattern, query)
    match_spotify_playlist_url = re.match(spotify_playlist_pattern, query)

    # Si es un video de YouTube
    if match_youtube_video:
        print("El enlace es un video de YouTube")
        video_id = match_youtube_video.group(2) if match_youtube_video.group(2) else match_youtube_video.group(3)
        print(f"https://www.youtube.com/watch?v={video_id}")
        return [query]

    # Si es una lista de reproducción de YouTube
    elif match_youtube_playlist:
        print("El enlace es una lista de reproducción de YouTube")
        playlist_id = match_youtube_playlist.group(1)

        try:
            # Usar asyncio.to_thread para ejecutar la tarea sin bloquear el hilo principal
            video_urls = extract_playlist_links(query)
            print(f"Enlaces de videos extraídos: {video_urls}")
            return video_urls

        except Exception as e:
            print(f"Error extrayendo la playlist de YouTube: {e}")
            return []

    # Si es una canción de Spotify
    elif match_spotify_track:
        print("El enlace es una canción de Spotify")
        try:
            track_info = await get_spotify_track_info(query)
            track_name = track_info['name']
            artist_name = track_info['artists'][0]['name']
            return await search_in_youtube(f"{track_name} de {artist_name}")
        except Exception as e:
            print(f"Error accediendo a Spotify: {e}")
            return await search_in_youtube(query)  # Si ocurre un error, buscar en YouTube

    # Si es una lista de reproducción de Spotify
    elif match_spotify_playlist_url:
        print("El enlace es una lista de reproducción de Spotify")
        playlist_id = match_spotify_playlist_url.group(1)
        try:
            # Este bloque puede ser personalizado si se requiere extraer más información de la playlist
            #playlist_info = await get_spotify_playlist_info(query)
            #print(f"Playlist info: {playlist_info}")
            # Aquí también puedes obtener la información de las canciones dentro de la playlist
            return await search_in_youtube(f"Lista de reproducción de Spotify {playlist_id}")
        except Exception as e:
            print(f"Error accediendo a la lista de reproducción de Spotify: {e}")
            return await search_in_youtube(query)  # Buscar en YouTube si hay un error

    # Si no es un enlace, realizar una búsqueda en YouTube o Spotify
    else:
        # Primero, buscar en YouTube
        return await search_in_youtube(query)



# Función para extraer los enlaces de la lista de reproducción usando yt_dlp
def extract_playlist_links(playlist_url):
    # Extraer el playlist_id del enlace
    parsed_url = urlparse(playlist_url)
    playlist_id = parse_qs(parsed_url.query).get('list', [None])[0]

    if not playlist_id:
        print("No se encontró el ID de la lista de reproducción.")
        return []

    # URL de la lista de reproducción de YouTube
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

    # Usar yt-dlp para obtener la información de la lista de reproducción
    with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
        result = ydl.extract_info(playlist_url, download=False)

        # Comprobar si la información obtenida es una lista de reproducción
        if 'entries' in result:
            # Extraer los links de cada video en la lista
            video_links = [entry['url'] for entry in result['entries']]
            return video_links
        else:
            return []


async def search_in_youtube(query):
    # Crear opciones para yt-dlp
    ydl_opts = {
        'quiet': True,  # No imprimir demasiados logs
        'extract_flat': True,  # Solo obtener metadatos sin descargar el video
        'force_generic_extractor': True  # Forzar el extractor genérico para YouTube
    }

    # Ejecutar la búsqueda asincrónica con yt-dlp
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Buscar el primer video que coincida con el query
        result = await asyncio.to_thread(ydl.extract_info, f"ytsearch:{query}", download=False)
        
        # Si se encontró algún resultado
        if 'entries' in result and result['entries']:
            first_video = result['entries'][0]  # El primer video
            video_url = first_video['url']  # Obtener la URL
            return video_url
        else:
            return "No se encontraron resultados."


async def play_queue(ctx, volume):
    print("Iniciando función play_queue")

    if not ctx.voice_client:
        await ctx.send("No estoy conectado a un canal de voz.")
        print("Error: No estoy conectado a un canal de voz.")
        return

    if not queue:
        await ctx.send("La cola está vacía.")
        print("Error: La cola está vacía.")
        return

    url = queue.pop(0)
    print(f"Reproduciendo canción: {url}")

    # Detecta si el enlace es de Spotify
    if 'spotify.com' in url:
        # Lógica para manejar Spotify
        await play_spotify(ctx, url, volume)
        return

    # Si es YouTube, sigue el flujo actual con YTDLSource
    try:
        print("Intentando crear el player...")
        player = await YTDLSource.from_url(url, loop=bot.loop, volume=volume)

        if player is None:
            await ctx.send(f"El video '{url}' no está disponible. Saltando a la siguiente canción.")
            print(f"El video '{url}' no está disponible.")
            if queue:
                await play_queue(ctx, volume)
            return

        print(f"Player creado correctamente: {player.title}")

        if ctx.voice_client.is_playing():
            await ctx.send("Ya se está reproduciendo algo, esperando a que termine...")
            print("Ya se está reproduciendo algo, esperando a que termine.")
            return

        # Iniciamos la reproducción
        ctx.voice_client.play(
            player,
            after=lambda e: bot.loop.create_task(play_queue(ctx, volume)) if queue else None
        )

        await ctx.send(f'🎶 Reproduciendo: {player.title} a volumen {volume * 100:.0f}% 🎶')
        print(f"Reproduciendo: {player.title} a volumen {volume * 100:.0f}%")

    except Exception as e:
        print(f"Error ocurrió: {e}")
        if "Video unavailable" in str(e):
            await ctx.send(f"El video '{url}' ya no está disponible. Saltando a la siguiente canción.")
            print(f"Error: El video '{url}' ya no está disponible.")
        else:
            await ctx.send(f"Hubo un error al intentar reproducir la canción: {e}")
            print(f"Error: {e}")

        if queue:
            await play_queue(ctx, volume)


# Función para obtener información de la canción
async def get_spotify_track_info(url):
    track_id = url.split('/')[-1]  # Obtiene el ID de la canción de la URL
    track_info = spotify.track(track_id)
    return track_info


# Función para reproducir desde Spotify
async def play_spotify(ctx, url, volume):
    print("Reproduciendo desde Spotify...")

    # Obtener información de la canción usando la API de Spotify
    try:
        track_info = await get_spotify_track_info(url)
        track_url = track_info['external_urls']['spotify']
        track_name = track_info['name']
        artist_name = track_info['artists'][0]['name']

        await ctx.send(f'🎶 Reproduciendo: {track_name} de {artist_name} 🎶')
        print(f"Reproduciendo: {track_name} de {artist_name}")

        # Aquí agregarías la lógica para enviar la URL de Spotify a Lavalink y reproducirla en Discord.
        # await play_music_in_voice_channel(ctx, track_url, volume)  # Aquí deberías implementar la reproducción

    except Exception as e:
        print(f"Error al reproducir desde Spotify: {e}")


async def next_song(ctx, volume):
    # Función auxiliar para continuar con la siguiente canción en la cola
    if queue:
        await play_queue(ctx, volume)
    else:
        # Si la cola está vacía, desconectar del canal de voz
        await ctx.send("La cola está vacía. Desconectando...")
        print("La cola está vacía, desconectando...")  # Confirmamos que la cola está vacía
        await ctx.voice_client.disconnect()  # Desconectar del canal de voz

@bot.command(name='play', help='Reproduce música desde YouTube o Spotify en el canal de voz')
async def sk_play(ctx, *, url: str, volume: float = 1):
    if ctx.author.voice is None:
        await ctx.send("¡Primero únete a un canal de voz, bebé! 😘")
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    # Validar volumen, asegurándose de que sea un número y esté entre 0 y 1
    try:
        # Asegurarse de que el parámetro 'volume' es un número válido
        volume = float(volume)
        if volume < 0 or volume > 1:
            await ctx.send("El volumen debe estar entre 0 y 1.")
            return
    except ValueError:
        await ctx.send("Por favor, ingresa un valor numérico válido para el volumen.")
        return

    # Llamar a la función search_media para obtener la URL o URLs válidas
    video_urls = await search_media(url)
    print(video_urls)

    # Asegúrate de que video_urls sea una lista
    if isinstance(video_urls, str):
        video_urls = [video_urls]  # Convertir en lista si es una cadena

    # Agregar todas las URLs encontradas a la cola
    if video_urls:
        queue.extend(video_urls)

        # Si no se está reproduciendo música, empezar a reproducir la cola
        if not ctx.voice_client.is_playing():
            if queue:
                await play_queue(ctx, volume)  # Iniciar la reproducción de la cola
            else:
                await ctx.send("La cola está vacía. 😔 Asegúrate de haber añadido canciones.")
        else:
            await ctx.send("Ya estoy reproduciendo música. Las canciones se han añadido a la cola. 🎶")
    else:
        await ctx.send("No se pudo encontrar ningún video. 😔")

@bot.command(name='volume', help='Cambia el volumen de la música')
async def volume(ctx, volume: float):  
    if 0 <= volume <= 1:
        if ctx.voice_client:
            ctx.voice_client.source.volume = volume
            await ctx.send(f'Volumen ajustado a {volume * 100:.0f}% 🎶')
        else:
            await ctx.send("No estoy conectado a un canal de voz.")
    else:
        await ctx.send("El volumen debe estar entre 0 y 1.")


@bot.command()
async def lol(ctx):
    if ctx.author.voice is None:
        await ctx.send("¡Primero únete a un canal de voz, bebé! 😘")
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    # Enlace de la lista de reproducción de YouTube
    playlist_url = "https://youtube.com/playlist?list=PLoBxjlCeJhSWAGfNa8O8LKj4vtF7Q7lZv&si=HJ0aI2-KcjDQ8S1v"

    # Llamar a la función 'extract_playlist_links' con el enlace de la lista de reproducción
    video_urls = extract_playlist_links(playlist_url)
    print(video_urls)
    # Verificar si se obtuvieron enlaces de videos
    if video_urls:
        queue.extend(video_urls)
        # Si no se está reproduciendo música, empezar a reproducir la cola
        if not ctx.voice_client.is_playing():
            if queue:
                await play_queue(ctx, 1)  # Iniciar la reproducción de la cola
            else:
                await ctx.send("La cola está vacía. 😔 Asegúrate de haber añadido canciones.")
        else:
            await ctx.send("Ya estoy reproduciendo música. Las canciones se han añadido a la cola. 🎶")
    else:
        await ctx.send("No se pudo encontrar ningún video. 😔")


@bot.command(name='leave', help='Deja el canal de voz')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("¡Me voy! 😘")
    else:
        await ctx.send("No estoy en un canal de voz.")

@bot.command(name='skip', help='Salta a la siguiente canción')
async def skip(ctx):
    if ctx.voice_client is None:
        await ctx.send("No estoy conectado a un canal de voz.")
        return

    if not ctx.voice_client.is_playing():
        await ctx.send("No hay música reproduciéndose en este momento.")
        return

    # Detener la canción actual
    ctx.voice_client.stop()
    await ctx.send("¡Saltando la canción! 🎵")

    # Reproducir la siguiente canción de la cola si hay alguna
    if queue:
        next_song = queue.pop(0)  # Sacar la siguiente canción de la cola

        try:
            player = await YTDLSource.from_url(next_song, loop=bot.loop, volume=0.5)
        except Exception as e:
            await ctx.send(f"Error al cargar la canción: {e}")
            return

        if player is None or not isinstance(player, discord.PCMVolumeTransformer):
            await ctx.send("No se pudo obtener una fuente de audio válida.")
            return

        def after_playing(error):
            if error:
                print(f"Error en reproducción: {error}")
            if queue:
                coro = play_queue(ctx, 0.5)
                future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                try:
                    future.result()
                except Exception as e:
                    print(f"Error en after_playing: {e}")

        # Reproducir la siguiente canción
        ctx.voice_client.play(player, after=after_playing)
        await ctx.send(f"🎶 Reproduciendo: {player.title}")
    else:
        # Si no hay más canciones en la cola, desconectar el bot
        await ctx.voice_client.disconnect()
        await ctx.send("No hay más canciones en la cola. ¡Desconectándome! 😘")
bot.run(TOKEN)
