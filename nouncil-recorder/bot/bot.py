"""
Nouncil Auto Recording Bot

This bot automatically records voice channels when 3 or more members are present.

Commands:
    !stop       - Stops the current recording (must be used from within the recording channel)
    !forcestop  - Admin only command to stop recording from any channel

Automatic Features:
    - Starts recording when 3+ non-bot members join a voice channel
    - Automatically stops recording when less than 3 members remain
    - Saves recordings with timestamps in the recordings directory
    - Announces start and stop of recordings in the channel
"""

import discord
from discord.ext import commands
import asyncio
import wave
import pyaudio
import logging
from datetime import datetime
import os
from config.config import *

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log'))

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

class AutoRecordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True  # Required for monitoring voice channels
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)
        
        self.recording = False
        self.voice_client = None
        self.current_recording_channel = None
        self.frames = []
        self.audio = None
        self.stream = None
        
        # Add commands
        self.add_command(commands.Command(self.stop, name='stop'))
        self.add_command(commands.Command(self.force_stop, name='forcestop'))

    async def setup_hook(self):
        logger.info("Bot is setting up...")
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        os.makedirs(LOGS_DIR, exist_ok=True)

    async def on_ready(self):
        logger.info(f'Bot is ready! Logged in as {self.user}')
        # Start monitoring all voice channels
        for guild in self.guilds:
            for vc in guild.voice_channels:
                await self.check_channel(vc)

    async def on_voice_state_update(self, member, before, after):
        """Triggered when someone joins/leaves a voice channel"""
        # Check channels that were affected by the change
        if before and before.channel:
            await self.check_channel(before.channel)
        if after and after.channel:
            await self.check_channel(after.channel)

    async def check_channel(self, channel):
        """Check if a channel should be recorded based on member count"""
        member_count = len([m for m in channel.members if not m.bot])
        
        if member_count >= 3 and not self.recording:
            # Start recording if not already recording
            await self.start_recording(channel)
        elif member_count < 3 and self.recording and self.current_recording_channel == channel:
            # Stop recording if currently recording this channel
            await self.stop_recording(auto_stopped=True)

    async def start_recording(self, channel):
        """Start recording a voice channel"""
        if self.recording:
            return
        
        try:
            self.voice_client = await channel.connect()
            self.current_recording_channel = channel
            
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=getattr(pyaudio, 'pa' + FORMAT.upper()),
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            self.recording = True
            self.frames = []
            
            # Announce start of recording
            await self.announce_recording_start(channel)
            
            # Start recording loop
            asyncio.create_task(self.record_loop())
            
            logger.info(f"Started recording in channel: {channel.name}")
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            await self.cleanup_recording()

    async def record_loop(self):
        """Main recording loop"""
        try:
            while self.recording:
                data = self.stream.read(CHUNK)
                self.frames.append(data)
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Error in recording loop: {e}")
            await self.stop_recording(error=True)

    async def stop_recording(self, auto_stopped=False, error=False):
        """Stop the current recording"""
        if not self.recording:
            return
            
        self.recording = False
        channel = self.current_recording_channel
        
        try:
            # Save the recording if we have any frames
            if self.frames:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f'nouncil_recording_{timestamp}'
                wav_path = os.path.join(RECORDINGS_DIR, f'{filename}.wav')
                
                with wave.open(wav_path, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(self.audio.get_sample_size(
                        getattr(pyaudio, 'pa' + FORMAT.upper())))
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(self.frames))
                
                logger.info(f"Saved recording to {wav_path}")
                
                if auto_stopped:
                    await channel.send("Recording stopped - less than 3 members in channel")
                elif error:
                    await channel.send("Recording stopped due to an error")
                else:
                    await channel.send("Recording stopped manually")
                    
                await channel.send(f"Recording saved as: {filename}")
        except Exception as e:
            logger.error(f"Error saving recording: {e}")
            if channel:
                await channel.send("Error saving recording")
        finally:
            await self.cleanup_recording()

    async def cleanup_recording(self):
        """Cleanup recording resources"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if self.voice_client:
            await self.voice_client.disconnect()
            
        self.stream = None
        self.audio = None
        self.voice_client = None
        self.current_recording_channel = None
        self.frames = []
        self.recording = False

    async def announce_recording_start(self, channel):
        """Announce that recording is starting"""
        try:
            await channel.send("🎙️ Recording started - 3 or more members detected in channel")
        except Exception as e:
            logger.error(f"Could not send start announcement: {e}")

    async def stop(self, ctx):
        """Command to stop recording"""
        if not self.recording:
            await ctx.send("Not currently recording!")
            return
            
        if ctx.author.voice and ctx.author.voice.channel == self.current_recording_channel:
            await self.stop_recording()
            await ctx.send("Recording stopped by command")
        else:
            await ctx.send("You must be in the recording channel to stop it")

    async def force_stop(self, ctx):
        """Admin command to force stop recording from any channel"""
        if not self.recording:
            await ctx.send("Not currently recording!")
            return
            
        if ctx.author.guild_permissions.administrator:
            await self.stop_recording()
            await ctx.send("Recording force stopped by admin")
        else:
            await ctx.send("Only administrators can force stop recordings")

    def cog_unload(self):
        """Cleanup when bot is shut down"""
        if self.recording:
            asyncio.create_task(self.stop_recording())