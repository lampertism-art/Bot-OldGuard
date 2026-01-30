import discord
from discord.ext import commands
import json
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

PUNTOS_FILE = "puntos.json"
subasta = None

def cargar_puntos():
    try:
        with open(PUNTOS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def guardar_puntos(data):
    with open(PUNTOS_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    print(f"Conectado como {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def addpuntos(ctx, user: discord.Member, cantidad: int):
    puntos = cargar_puntos()
    uid = str(user.id)
    puntos[uid] = puntos.get(uid, 0) + cantidad
    guardar_puntos(puntos)
    await ctx.send(f"{user.mention} ahora tiene {puntos[uid]} puntos")

@bot.command()
@commands.has_permissions(administrator=True)
async def quitarpuntos(ctx, user: discord.Member, cantidad: int):
    puntos = cargar_puntos()
    uid = str(user.id)
    puntos[uid] = max(0, puntos.get(uid, 0) - cantidad)
    guardar_puntos(puntos)
    await ctx.send(f"{user.mention} ahora tiene {puntos[uid]} puntos")

@bot.command()
async def puntos(ctx, user: discord.Member = None):
    user = user or ctx.author
    puntos = cargar_puntos()
    await ctx.send(f"{user.mention} tiene {puntos.get(str(user.id), 0)} puntos")

@bot.command()
@commands.has_permissions(administrator=True)
async def subasta(ctx, item: str, tiempo: int):
    global subasta

    if subasta:
        await ctx.send("Ya hay una subasta activa")
        return

    subasta = {
        "item": item,
        "mejor_puja": 0,
        "mejor_usuario": None,
        "pujas_usadas": set()
    }

    await ctx.send(
        f"SUBASTA INICIADA\n"
        f"Objeto: {item}\n"
        f"Duración: {tiempo} segundos\n"
        f"Usa !pujar <cantidad>"
    )

    await asyncio.sleep(tiempo)

    if subasta["mejor_usuario"]:
        await ctx.send(
            f"GANADOR: {subasta['mejor_usuario'].mention}\n"
            f"Puja: {subasta['mejor_puja']} puntos"
        )
    else:
        await ctx.send("La subasta terminó sin pujas")

    subasta = None

@bot.command()
async def ranking(ctx):
    puntos = cargar_puntos()

    if not puntos:
        await ctx.send("No hay puntos registrados todavía")
        return

    # Ordenar de mayor a menor
    puntos_ordenados = sorted(
        puntos.items(),
        key=lambda x: x[1],
        reverse=True
    )

    mensaje = "**🏆 Ranking de puntos:**\n"

    for posicion, (user_id, cantidad) in enumerate(puntos_ordenados, start=1):
        miembro = ctx.guild.get_member(int(user_id))
        if miembro:
            nombre = miembro.nick if miembro.nick else miembro.name
            mensaje += f"**{posicion}.** {nombre} → **{cantidad}** puntos\n"

    await ctx.send(mensaje)


@bot.command()
async def pujar(ctx, cantidad: int):
    global subasta

    if not subasta:
        await ctx.send("No hay subasta activa")
        return

    puntos = cargar_puntos()
    uid = str(ctx.author.id)

    if cantidad > puntos.get(uid, 0):
        await ctx.send("No tenés suficientes puntos")
        return

    if cantidad in subasta["pujas_usadas"]:
        await ctx.send("Esa puja ya fue usada")
        return

    if cantidad <= subasta["mejor_puja"]:
        await ctx.send("La puja debe ser mayor")
        return

    subasta["mejor_puja"] = cantidad
    subasta["mejor_usuario"] = ctx.author
    subasta["pujas_usadas"].add(cantidad)

    await ctx.send(f"Nueva mejor puja: {cantidad} por {ctx.author.mention}")

import os
bot.run(os.getenv("DISCORD_TOKEN"))