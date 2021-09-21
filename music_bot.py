import discord
import json
import youtube_dl
import os


from youtube_search import YoutubeSearch

ydl_opts = {
    'format': 'bestaudio/best',
}

class MyClient(discord.Client):

    async def on_ready(self):
        print('Logged on as', self.user)
        self.Client = None
        self.musicQueue = []
    
    def finished_song(self, error):
        assert(len(self.musicQueue) != 0)
        print(self.musicQueue)
        self.musicQueue.pop(0)
        self.play_next_song()

    def play_next_song(self):
        if len(self.musicQueue) == 0:
            return
        self.Client.play(discord.FFmpegPCMAudio(self.musicQueue[0]), after=self.finished_song)
        
        
    async def send_message(self, message, msg):
        embed = discord.Embed()
        embed.description = ">>> {0}".format(msg)
        await message.channel.send(embed=embed)

    async def on_message(self, message):
        command = message.content.split(' ')[0]
        
        # don't respond to ourselves
        if message.author == self.user:
            return

        if command == "-play":
            voice_channel = message.author.voice.channel
            if self.Client == None:
                self.Client = await voice_channel.connect()
            if self.Client.channel.id != message.author.voice.channel.id:
                self.Client.stop()
                await self.Client.move_to(message.author.voice.channel)
            if (len(message.content.split(" ")) < 2):
                await self.send_message(message, "Ok but play wot?")
                return
            search = " ".join(message.content.split(' ')[1:])
            results  = YoutubeSearch(search, max_results = 3).to_dict()
            url = 'https://www.youtube.com' + results[0]['url_suffix']
            info_dict = youtube_dl.YoutubeDL(ydl_opts).extract_info(url, download=False)
            name = info_dict['url']
            
            if len(self.musicQueue) == 0:
                self.Client.play(discord.FFmpegPCMAudio(name), after=self.finished_song)
            self.musicQueue.append(name)

            await self.send_message(message, "Queued [{0}]({1})".format(info_dict.get("title"), url))
        if command == "-skip":
            if self.Client == None:
                await self.send_message(message, 'Bot is not connected to a channel.')
                return
            if len(self.musicQueue) == 0:
                await self.send_message(message, 'No song is playing.')
                return
            self.Client.stop()
            #os.remove(name)
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

with open('music_secrets.json') as file:
  file_json = json.load(file)

client = MyClient()
client.run(file_json['token'])