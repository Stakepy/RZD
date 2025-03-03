import discord
from discord.ext import commands
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
GUILD_MAIN =   # ID основного сервера
VOICE_MAIN =   # ID основного голосового канала
TEXT_CHANNEL_MAIN =   # ID основного текстового канала
ROLE_CITIZEN =   # ID роли "Гражданство"

# Другие серверы {guild_id: voice_channel_id}
OTHER_SERVERS = {
    : ,
    : ,
}

# Глобальные переменные
active_connections = {}  # Активные голосовые подключения


async def play_sound_effect(guild, filename):
    """Воспроизведение звукового эффекта в указанной гильдии"""
    try:
        if guild.voice_client and guild.voice_client.is_connected():
            source = discord.FFmpegPCMAudio(filename)
            guild.voice_client.play(source)
            await asyncio.sleep(3)  # Ожидание завершения воспроизведения
    except Exception as e:
        print(f"Ошибка воспроизведения звука на {guild.id}: {e}")


@bot.event
async def on_ready():
    """Обработчик события запуска бота"""
    print(f'Бот авторизован как {bot.user}')

    # Синхронизация команд с Discord
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")

    # Подключение ко всем голосовым каналам
    await connect_to_all_voices()

    # Воспроизведение звука запуска
    for guild_id in [GUILD_MAIN, *OTHER_SERVERS.keys()]:
        guild = bot.get_guild(guild_id)
        if guild:
            await play_sound_effect(guild, 'sound.mp3')


async def connect_to_all_voices():
    """Подключение ко всем указанным голосовым каналам"""
    for guild_id, voice_id in [*OTHER_SERVERS.items(), (GUILD_MAIN, VOICE_MAIN)]:
        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        voice_channel = guild.get_channel(voice_id)
        if not voice_channel:
            continue

        try:
            # Отключение существующего подключения
            if guild.voice_client:
                await guild.voice_client.disconnect()

            # Новое подключение
            vc = await voice_channel.connect()
            active_connections[guild_id] = vc
            await asyncio.sleep(1)  # Задержка между подключениями
        except Exception as e:
            print(f"Ошибка подключения к {guild_id}: {e}")


@bot.event
async def on_voice_state_update(member, before, after):
    """Обработчик изменения голосового статуса"""
    if member == bot.user:
        guild = member.guild  # Получаем гильдию, где произошло изменение
        guild_id = guild.id

        if guild_id in active_connections:
            vc = active_connections[guild_id]
            if not vc.is_connected():
                del active_connections[guild_id]
                # Подключаемся только к голосовому каналу на этом сервере
                voice_id = OTHER_SERVERS.get(guild_id) or VOICE_MAIN  # Используем VOICE_MAIN, если это основной сервер

                voice_channel = guild.get_channel(voice_id)
                if voice_channel:
                    try:
                        # Отключение существующего подключения (если есть)
                        if guild.voice_client:
                            await guild.voice_client.disconnect()

                        # Новое подключение
                        vc = await voice_channel.connect()
                        active_connections[guild_id] = vc
                        print(f"Переподключено к голосовому каналу на сервере {guild_id}")

                    except Exception as e:
                        print(f"Ошибка переподключения к {guild_id}: {e}")



class ServerSelect(Select):
    """Кастомный селектор для выбора сервера"""

    def __init__(self, options):
        super().__init__(
            placeholder="Выберите сервер назначения...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):
        try:
            await interaction.message.delete()
        except discord.errors.NotFound:
            pass  # Сообщение уже удалено или недоступно
        target_guild = bot.get_guild(int(self.values[0]))

        # Воспроизведение звуковых эффектов
        await play_sound_effect(interaction.guild, 'sound.mp3')
        await play_sound_effect(target_guild, 'sound.mp3')

        # Создание приглашения
        try:
            invite = await target_guild.text_channels[0].create_invite(max_uses=1)
            await interaction.user.send(f"Ваш билет: {invite.url}")
        except Exception as e:
            print(f"Ошибка выдачи билета: {e}")

        # Очистка сообщений
        await interaction.channel.purge(limit=1)


@bot.tree.command(name="trip", description="Начать межсерверное путешествие")
@app_commands.guild_only()
async def trip_command(interaction: discord.Interaction):
    """Обработчик команды /trip"""
    is_main_guild = interaction.guild_id == GUILD_MAIN
    options = []

    # Проверки для основного сервера
    if is_main_guild:
        # Проверка роли
        if not interaction.user.get_role(ROLE_CITIZEN):
            return await interaction.response.send_message(
                "⛔ Требуется роль Гражданства!",
                ephemeral=True
            )

        # Проверка голосового канала
        voice_state = interaction.user.voice
        if not voice_state or voice_state.channel.id != VOICE_MAIN:
            return await interaction.response.send_message(
                "⛔ Вы должны находиться в основном войсе!",
                ephemeral=True
            )

        # Проверка текстового канала
        if interaction.channel_id != TEXT_CHANNEL_MAIN:
            return await interaction.response.send_message(
                "⛔ Используйте предназначенный для этого канал!",
                ephemeral=True
            )

    # Формирование списка доступных серверов
    target_servers = [GUILD_MAIN]  # По умолчанию только основной сервер

    # Если команда вызвана на основном сервере - добавляем все сервера
    if is_main_guild:
        target_servers = [*OTHER_SERVERS.keys(), GUILD_MAIN]

    for guild_id in target_servers:
        # Пропускаем текущий сервер
        if guild_id == interaction.guild_id:
            continue

        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        # Проверка наличия пользователя на сервере
        try:
            member = await guild.fetch_member(interaction.user.id)
            if member:
                continue
        except discord.NotFound:
            pass  # Пользователь не состоит на сервере
        except discord.Forbidden:
            print(f"Нет прав для проверки участника на сервере {guild.id}")
            continue

        # Добавляем только основной сервер если команда вызвана не на основном
        if not is_main_guild and guild_id != GUILD_MAIN:
            continue

        options.append(discord.SelectOption(
            label=guild.name,
            value=str(guild.id),
            emoji="🌍"
        ))

    if not options:
        return await interaction.response.send_message(
            "⛔ Нет доступных серверов для путешествия!",
            ephemeral=True
        )

    # Создание интерфейса выбора
    select = ServerSelect(options)
    view = View()
    view.add_item(select)

    await interaction.response.send_message(
        "🚂 Выберите сервер для путешествия:",
        view=view,
        ephemeral=True
    )


# Запуск бота
bot.run(os.getenv('DISCORD_TOKEN'))
