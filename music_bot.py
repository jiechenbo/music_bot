import discord
import json
import youtube_dl
import os


from youtube_search import YoutubeSearch

ydl_opts = {
    'format': 'bestaudio/best',
}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

class MyClient(discord.Client):

    async def on_ready(self):
        print('Logged on as', self.user)
        self.Client = None
        self.musicQueue = []
        self.searchList = []
    
    def finished_song(self, error):
        assert(len(self.musicQueue) != 0)
        print(self.musicQueue)
        self.musicQueue.pop(0)
        self.play_next_song()

    def stream_song(self, url):
        video_info = youtube_dl.YoutubeDL(ydl_opts).extract_info(url, download=False)
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

    async def on_message(self, message):
        full_command = message.content.split(' ')
        command = full_command.pop(0)
        
        # don't respond to ourselves
        if message.author == self.user:
            return

        if command == "-play" or command == "-p":
            next = False
            if full_command[0] == "next" or full_command[0] == "n":
                next = True
                full_command.pop(0)
            await self.try_join_voice_channel(message.author.voice.channel)
            if (len(full_command) < 0):
                await self.send_message(message, "Ok but play wot?")
                return
            search = " ".join(full_command)
            results  = YoutubeSearch(search, max_results = 1).to_dict()
            url = 'https://www.youtube.com' + results[0]['url_suffix']
            
            if len(self.musicQueue) == 0:
                self.stream_song(url)
            self.musicQueue.append(url) if not next else self.musicQueue.insert(1, url)
            await self.send_message(message, "Queued [{0}]({1})".format(results[0].get("title"), url))
        
        if command == "-search":
            if len(self.searchList) > 0:
                self.searchList.clear()
            full_command.pop(0)
            search = " ".join(full_command)
            results  = YoutubeSearch(search, max_results = 10).to_dict()
            search_result_message = ""
            for index, video in enumerate(results):
                url = 'https://www.youtube.com' + video.get("url_suffix")
                search_result_message += "{0}. [{1}]({2})\n".format(index + 1, video.get("title"), url)
                self.searchList.append(url)
            await self.send_message(message, search_result_message)

        if command == "-skip":
            if self.Client == None:
                await self.send_message(message, 'Bot is not connected to a channel.')
                return
            if len(self.musicQueue) == 0:
                await self.send_message(message, 'No song is playing.')
                return
            self.Client.stop()
            emoji = [i for i in client.emojis if i.name == 'Ice_Bear'][0]
            await message.add_reaction(client.get_emoji(emoji.id))
            
        if command == "-stop":
            if self.Client == None:
                await self.send_message(message, 'Bot is not connected to a channel.')
                return
            if len(self.musicQueue) == 0:
                await self.send_message(message, 'No song is playing.')
                return
            self.Client.stop()
            self.musicQueue.clear()

        if command.isnumeric():
            index = int(command)
            next = False
            if len(full_command) > 0 and (full_command[0] == "next" or full_command[0] == "n"):
                next = True
                full_command.pop(0)
            await self.try_join_voice_channel(message.author.voice.channel)
            if len(self.searchList) == 0:
                return
            if index < 0 or index >= len(self.searchList):
                await self.send_message(message, 'The number you chose is out of bounds.')
                return

            if len(self.musicQueue) == 0:
                self.stream_song(self.searchList[index])
            self.musicQueue.append(self.searchList[index]) if not next else self.musicQueue.insert(1, self.searchList[index])
            print(self.musicQueue)
            self.searchList.clear()

with open('music_secrets.json') as file:
  file_json = json.load(file)

client = MyClient()
client.run(file_json['token'])