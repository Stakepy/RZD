import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Select, View
import asyncio
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка интентов
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Конфигурационные константы
GUILD_MAIN = 1225075859333845154
VOICE_MAIN = 1289694911234310155
TEXT_CHANNEL_MAIN = 1345863315569512558
ROLE_CITIZEN = 1289911579097436232

OTHER_SERVERS = {
    1119377303198236784: 1288580688420802622,
    1284541768888487966: 1345775160292020348,
    1346215194933592107: 1346215196250734757,
}


async def play_sound_effect(guild, filename):
    """Воспроизведение звукового эффекта"""
    try:
        if guild.voice_client and guild.voice_client.is_connected():
            source = discord.FFmpegPCMAudio(filename)
            guild.voice_client.play(source)
            await asyncio.sleep(3)
    except Exception as e:
        print(f"Ошибка воспроизведения звука на {guild.id}: {e}")


@tasks.loop(seconds=10)
async def voice_control():
    """Основной цикл контроля голосовых подключений"""
    for guild_id, voice_id in {GUILD_MAIN: VOICE_MAIN, **OTHER_SERVERS}.items():
        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        voice_channel = guild.get_channel(voice_id)
        if not voice_channel:
            continue

        vc = guild.voice_client

        # Проверка текущего состояния
        if vc:
            if vc.channel.id != voice_id or not vc.is_connected():
                try:
                    await vc.disconnect()
                except:
                    pass
                vc = None

        if not vc:
            try:
                await voice_channel.connect(reconnect=True, timeout=30)
                print(f"Успешное подключение к {guild.name}")
                await play_sound_effect(guild, 'sound.mp3')
            except Exception as e:
                print(f"Ошибка подключения к {guild.name}: {str(e)}")
                await asyncio.sleep(5)


@voice_control.before_loop
async def before_voice_control():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    """Обработчик запуска бота"""
    print(f'Бот {bot.user} успешно запущен!')

    try:
        await bot.tree.sync()
        print("Команды синхронизированы")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

    voice_control.start()


@bot.event
async def on_voice_state_update(member, before, after):
    """Обработчик изменений в голосовых каналах"""
    if member.id == bot.user.id:
        guild = member.guild
        target_channel_id = OTHER_SERVERS.get(guild.id) or VOICE_MAIN

        # Если бота переместили или отключили
        if not after.channel or after.channel.id != target_channel_id:
            await asyncio.sleep(2)
            voice_channel = guild.get_channel(target_channel_id)

            if voice_channel and not guild.voice_client:
                try:
                    await voice_channel.connect(reconnect=True)
                    print(f"Экстренное переподключение к {guild.name}")
                except Exception as e:
                    print(f"Ошибка экстренного подключения: {e}")


class ServerSelect(Select):
    """Селектор серверов для путешествий"""

    def __init__(self, options):
        super().__init__(
            placeholder="🌍 Выберите сервер назначения...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):
        try:
            await interaction.message.delete()
        except:
            pass

        target_guild = bot.get_guild(int(self.values[0]))

        # Воспроизведение звука
        await play_sound_effect(interaction.guild, 'sound.mp3')
        if target_guild:
            await play_sound_effect(target_guild, 'sound.mp3')

        # Создание приглашения
        try:
            invite = await target_guild.text_channels[0].create_invite(max_uses=1)
            await interaction.user.send(f"🚀 Ваш билет: {invite.url}")
        except Exception as e:
            print(f"Ошибка создания приглашения: {e}")


@bot.tree.command(name="trip", description="Начать межсерверное путешествие")
@app_commands.guild_only()
async def trip_command(interaction: discord.Interaction):
    """Команда для путешествий"""
    is_main = interaction.guild_id == GUILD_MAIN
    options = []

    # Проверки для основного сервера
    if is_main:
        if not interaction.user.get_role(ROLE_CITIZEN):
            return await interaction.response.send_message(
                "⛔ Требуется гражданство!", ephemeral=True)

        voice_state = interaction.user.voice
        if not voice_state or voice_state.channel.id != VOICE_MAIN:
            return await interaction.response.send_message(
                "⛔ Вы должны быть в основном войсе!", ephemeral=True)

        if interaction.channel_id != TEXT_CHANNEL_MAIN:
            return await interaction.response.send_message(
                "⛔ Неправильный канал!", ephemeral=True)

    # Формирование списка серверов
    target_servers = list(OTHER_SERVERS.keys()) + [GUILD_MAIN] if is_main else [GUILD_MAIN]

    for guild_id in target_servers:
        if guild_id == interaction.guild_id:
            continue

        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        try:
            if await guild.fetch_member(interaction.user.id):
                continue
        except:
            pass

        options.append(discord.SelectOption(
            label=guild.name,
            value=str(guild.id),
            emoji="🌍"
        ))

    if not options:
        return await interaction.response.send_message(
            "⛔ Нет доступных серверов!", ephemeral=True)

    # Отправка интерфейса
    view = View().add_item(ServerSelect(options))
    await interaction.response.send_message(
        "🚂 Выберите пункт назначения:", view=view, ephemeral=True)


# Запуск бота
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN'))