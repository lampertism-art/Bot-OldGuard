import discord
from discord.ext import commands
import asyncpg
import os
import asyncio
from datetime import datetime, timedelta

# ───────── CONFIG ─────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="m!", intents=intents)
db = None

# ───────── DATABASE ─────────
async def init_db():
    global db
    db = await asyncpg.connect(os.getenv("DATABASE_URL"))

    await db.execute("""
    CREATE TABLE IF NOT EXISTS puntos (
        user_id BIGINT PRIMARY KEY,
        puntos INTEGER NOT NULL DEFAULT 0
    );
    """)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS subastas (
        guild_id BIGINT PRIMARY KEY,
        descripcion TEXT,
        mejor_puja INTEGER DEFAULT 0,
        mejor_usuario BIGINT,
        termina_en TIMESTAMP
    );
    """)

# ───────── EVENTOS ─────────
@bot.event
async def on_ready():
    await init_db()
    print(f"✅ Bot conectado como {bot.user}")

# ───────── UTILIDADES ─────────
async def get_puntos(user_id):
    row = await db.fetchrow(
        "SELECT puntos FROM puntos WHERE user_id = $1", user_id
    )
    return row["puntos"] if row else 0

async def set_puntos(user_id, cantidad):
    await db.execute("""
    INSERT INTO puntos (user_id, puntos)
    VALUES ($1, $2)
    ON CONFLICT (user_id)
    DO UPDATE SET puntos = $2
    """, user_id, cantidad)

# ───────── PUNTOS ─────────
@bot.command()
@commands.has_permissions(administrator=True)
async def addpuntos(ctx, user: discord.Member, cantidad: int):
    puntos = await get_puntos(user.id)
    puntos += cantidad
    await set_puntos(user.id, puntos)
    await ctx.send(f"✅ {user.mention} ahora tiene **{puntos} puntos**")

@bot.command()
@commands.has_permissions(administrator=True)
async def quitarpuntos(ctx, user: discord.Member, cantidad: int):
    puntos = max(0, await get_puntos(user.id) - cantidad)
    await set_puntos(user.id, puntos)
    await ctx.send(f"⚠️ {user.mention} ahora tiene **{puntos} puntos**")

@bot.command()
async def puntos(ctx, user: discord.Member = None):
    user = user or ctx.author
    puntos = await get_puntos(user.id)
    await ctx.send(f"💰 {user.mention} tiene **{puntos} puntos**")

# ───────── RANKING ─────────
@bot.command()
async def ranking(ctx):
    rows = await db.fetch("""
    SELECT user_id, puntos FROM puntos
    ORDER BY puntos DESC
    LIMIT 20
    """)

    if not rows:
        await ctx.send("❌ No hay puntos registrados")
        return

    mensaje = "**🏆 Ranking de puntos**\n\n"
    for i, row in enumerate(rows, start=1):
        member = ctx.guild.get_member(row["user_id"])
        nombre = member.display_name if member else f"ID {row['user_id']}"
        mensaje += f"**{i}.** {nombre} → **{row['puntos']}** puntos\n"

    await ctx.send(mensaje)

# ───────── SUBASTAS ─────────
@bot.command()
@commands.has_permissions(administrator=True)
async def subasta(ctx, tiempo: int, *, descripcion: str):
    existe = await db.fetchrow(
        "SELECT 1 FROM subastas WHERE guild_id = $1", ctx.guild.id
    )
    if existe:
        await ctx.send("❌ Ya hay una subasta activa")
        return

    termina = datetime.utcnow() + timedelta(seconds=tiempo)

    await db.execute("""
    INSERT INTO subastas (guild_id, descripcion, termina_en)
    VALUES ($1, $2, $3)
    """, ctx.guild.id, descripcion, termina)

    await ctx.send(
        f"🔥 **SUBASTA INICIADA** 🔥\n"
        f"📝 {descripcion}\n"
        f"⏱ {tiempo} segundos\n"
        f"💸 Usa `m!pujar cantidad`"
    )

    await asyncio.sleep(tiempo)
    await cerrar_subasta(ctx.guild.id, ctx)

async def cerrar_subasta(guild_id, ctx):
    subasta = await db.fetchrow(
        "SELECT * FROM subastas WHERE guild_id = $1", guild_id
    )
    if not subasta:
        return

    if subasta["mejor_usuario"]:
        puntos = await get_puntos(subasta["mejor_usuario"])
        puntos = max(0, puntos - subasta["mejor_puja"])
        await set_puntos(subasta["mejor_usuario"], puntos)

        member = ctx.guild.get_member(subasta["mejor_usuario"])
        await ctx.send(
            f"🏆 **SUBASTA FINALIZADA** 🏆\n"
            f"👤 Ganador: {member.mention}\n"
            f"💰 Puja: {subasta['mejor_puja']} puntos\n"
            f"📉 Restantes: {puntos}"
        )
    else:
        await ctx.send("⏹ Subasta terminada sin pujas")

    await db.execute("DELETE FROM subastas WHERE guild_id = $1", guild_id)

@bot.command()
async def pujar(ctx, cantidad: int):
    subasta = await db.fetchrow(
        "SELECT * FROM subastas WHERE guild_id = $1", ctx.guild.id
    )
    if not subasta:
        await ctx.send("❌ No hay subasta activa")
        return

    puntos = await get_puntos(ctx.author.id)

    if cantidad <= subasta["mejor_puja"]:
        await ctx.send("❌ La puja debe ser mayor")
        return

    if cantidad > puntos:
        await ctx.send("❌ No tenés suficientes puntos")
        return

    await db.execute("""
    UPDATE subastas
    SET mejor_puja = $1, mejor_usuario = $2
    WHERE guild_id = $3
    """, cantidad, ctx.author.id, ctx.guild.id)

    await ctx.send(
        f"💸 Nueva mejor puja: **{cantidad} puntos** por {ctx.author.mention}"
    )

# ───────── ARRANQUE ─────────
bot.run(os.getenv("DISCORD_TOKEN"))

