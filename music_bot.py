import discord
import json
import youtube_dl
import os
import re
import asyncio

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtube_search import YoutubeSearch


ydl_opts = {
    'format': 'bestaudio/best',
}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

class Song: 
    def __init__(self, title, url, duration): 
        self.title = title 
        self.url = url
        self.duration = duration

class MusicBot(discord.Client):

    async def on_ready(self):
        print('Logged on as', self.user)
        self.Client = None
        # Make locking class structures for both musicQueue and searchList
        self.musicQueue = []
        self.searchList = []
        self.emoji =  [i for i in client.emojis if i.name == 'Ice_Bear'][0]
        self.lock = asyncio.Lock()
    
    def finished_song(self, error):
        assert(len(self.musicQueue) != 0)
        print(self.musicQueue)
        self.musicQueue.pop(0)
        self.play_next_song()

    def stream_song(self, song):
        video_info = youtube_dl.YoutubeDL(ydl_opts).extract_info(song.url, download=False)
        self.Client.play(discord.FFmpegPCMAudio(video_info['url'], **FFMPEG_OPTIONS), after=self.finished_song)
        return video_info

    def play_next_song(self):
        if len(self.musicQueue) == 0:
            return
        self.stream_song(self.musicQueue[0])

    async def try_join_voice_channel(self, voice_channel):
        if self.Client == None:
            self.Client = await voice_channel.connect()
        if self.Client.channel.id != voice_channel.id:
            self.Client.stop()
            await voice_channel.disconnect()
            self.Client = await voice_channel.connect()

    async def send_message(self, message, msg):
        embed = discord.Embed()
        embed.description = ">>> {0}".format(msg)
        await message.channel.send(embed=embed)

    def parse_search(self, message):
        print(message)
        if re.match('http', message):
            match =  re.search('playlist/(.*)?', message)
            if match:
                playlist_id = match.group(1)
                playlist_songs = sp.playlist(playlist_id)['tracks']['items']
                song_list = list()
                for song in playlist_songs:
                    search_message = song['track']['name']
                    for artist in song['track']['artists']:
                        search_message += " " + artist['name']
                    song_list.append(search_message + " audio")
                return song_list
            else:
                return [message]
        else:
            return [message]
        

    async def on_message(self, message):
        full_command = message.content.split(' ')
        command = full_command.pop(0)
        if not hasattr(self, 'lock') or self.lock.locked():
            return
        # don't respond to ourselves
        if message.author == self.user:
            return

        await self.lock.acquire()
        if command == "-help" or command == "-h":
            embed = discord.Embed(title="Welcome to the Scuffed Music bot!")
            commands = ["-help|-h", "-play|-p [-n] song", "-skip", "-stop", "-queue", "-remove|-r number", "-search song", "number [-n]"]
            usages = ["For help with commands of the bot.", "Play a song with the option of placing the song next in queue.",
            "Skip the current song.", "Clear the queue.", "Show the list of songs in queue.", "Remove the selected numbered song in the queue.",
            "Search youtube for song, and return 10 results.", "Once search is executed, choose from 1 - 10 for the selected song."]
            embed.add_field(name = "Commands", value = "\n".join(commands), inline = True)
            embed.add_field(name = "Usages", value = "\n".join(usages), inline = True)
            message.channel.send(embed=embed)

        if command == "-queue" or command == "-q":
            queue_result_message =""
            for index, song in enumerate(self.musicQueue):
                queue_result_message += "{0}. [{1}]({2})\n".format(index + 1, song.title, song.url)
            await self.send_message(message, queue_result_message)

        if command == "-remove" or command == "-r":
            if self.Client == None:
                await self.send_message(message, 'Bot is not connected to a channel.')
                self.lock.release()
                return
            if len(full_command) == 0:
                await self.send_message(message, 'Specify a number.')
            index = int(full_command.pop())
            if index <= 0 or index > len(self.musicQueue):
                await self.send_message(message, 'Number out of bounds.')
            if index == 1:
                self.Client.stop()
            else:
                self.musicQueue.pop(index - 1)
            await message.add_reaction(client.get_emoji(self.emoji.id))
            
        if command == "-play" or command == "-p":
            next = False
            if full_command[0] == "next" or full_command[0] == "n":
                next = True
                full_command.pop(0)
            await self.try_join_voice_channel(message.author.voice.channel)
            if (len(full_command) < 0):
                await self.send_message(message, "Ok but play wot?")
                self.lock.release()
                return
            search_list = self.parse_search(" ".join(full_command))
            song = None
            for search in search_list:
                results  = YoutubeSearch(search, max_results = 1).to_dict()
                url = 'https://www.youtube.com' + results[0]['url_suffix']
                song = Song(results[0].get("title"), url, results[0].get('duration'))
                if len(self.musicQueue) == 0:
                    self.stream_song(song)
                self.musicQueue.append(song) if not next else self.musicQueue.insert(1, song)

            if len(search_list) == 1:
                await self.send_message(message, "Queued [{0}]({1})".format(song.title, song.url))
            else:
                await self.send_message(message, "Queued [{0} songs]({1})".format(len(search_list), " ".join(full_command)))
        
        if command == "-search":
            if len(full_command) == 0:
                await message.add_reaction(client.get_emoji(self.emoji.id))
                self.lock.release()
                return
            if len(self.searchList) > 0:
                self.searchList.clear()
            search = " ".join(full_command)
            results  = YoutubeSearch(search, max_results = 10).to_dict()
            assert(len(results) == 10)
            search_result_message = ""
            for index, video in enumerate(results):
                url = 'https://www.youtube.com' + video.get("url_suffix")
                song = Song(video.get("title"), url, video.get("duration"))
                search_result_message += "{0}. [{1}]({2})\n".format(index + 1, song.title, song.url)
                self.searchList.append(song)
            await self.send_message(message, search_result_message)

        if command == "-skip":
            if self.Client == None:
                await self.send_message(message, 'Bot is not connected to a channel.')
                self.lock.release()
                return
            if len(self.musicQueue) == 0:
                await self.send_message(message, 'No song is playing.')
                self.lock.release()
                return
            self.Client.stop()
            await message.add_reaction(client.get_emoji(self.emoji.id))

        if command == "-stop" or command == "-shine":
            if self.Client == None:
                await self.send_message(message, 'Bot is not connected to a channel.')
                self.lock.release()
                return
            if len(self.musicQueue) == 0:
                await self.send_message(message, 'No song is playing.')
                self.lock.release()
                return
            self.Client.stop()
            self.musicQueue.clear()

        if command.isnumeric():
            index = int(command)
            next = False
            if len(full_command) > 0 and (full_command[0] == "next" or full_command[0] == "n"):
                next = True
                full_command.pop(0)
            if len(self.searchList) == 0:
                self.lock.release()
                return
            await self.try_join_voice_channel(message.author.voice.channel)

            if index <= 0 or index > len(self.searchList):
                await self.send_message(message, 'The number you chose is out of bounds.')
                self.lock.release()
                return

            if len(self.musicQueue) == 0:
                self.stream_song(self.searchList[index - 1])
            self.musicQueue.append(self.searchList[index - 1]) if not next else self.musicQueue.insert(1, self.searchList[index - 1])
            self.searchList.clear()
        self.lock.release()

with open('music_secrets.json') as file:
  file_json = json.load(file)

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=file_json['spotify_client'], client_secret=file_json['spotify_secret']))
client = MusicBot()
client.run(file_json['token'])