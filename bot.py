import discord
import os
from discord.ext import commands, tasks
from discord.ui import Select, View, Button
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True

# تعيين help_command=None لإلغاء أمر المساعدة الافتراضي لمنع التضارب
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ==========================================
# ⚙️ إعدادات رتب اللفلات
# ==========================================
LEVEL_ROLES = {
    5: "lvl 5",
    10: "lvl 10",
    20: "lvl 20",
    30: "lvl 30",
    40: "lvl 40",
    50: "lvl 50"
}

afk_users = {}

# ==========================================
# 🎫 نظام التذاكر التراكمي (Ticket System)
# ==========================================

def get_next_ticket_number():
    file_path = "ticket_counter.txt"
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("0")
    
    with open(file_path, "r") as f:
        try:
            current_num = int(f.read().strip())
        except ValueError:
            current_num = 0
            
    next_num = current_num + 1
    
    with open(file_path, "w") as f:
        f.write(str(next_num))
        
    return next_num

class ConfirmCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_channels:
            return True
        await interaction.response.send_message("❌ عذراً، هذا الزر مخصص لطاقم الإدارة فقط!", ephemeral=True)
        return False

    @discord.ui.button(label="تأكيد الإغلاق", style=discord.ButtonStyle.danger, emoji="✅", custom_id="confirm_close_btn")
    async def confirm_close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("⚠️ سيتم حذف التذكرة خلال 3 ثوانٍ...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

    @discord.ui.button(label="تراجع", style=discord.ButtonStyle.secondary, emoji="❌", custom_id="cancel_close_btn")
    async def cancel_close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("❌ تم إلغاء طلب الإغلاق.", ephemeral=True)
        await interaction.message.delete()

class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_channels:
            return True
        await interaction.response.send_message("❌ عذراً، هذه الأزرار مخصصة لطاقم الإدارة فقط!", ephemeral=True)
        return False

    @discord.ui.button(label="استلام", style=discord.ButtonStyle.success, emoji="🙋‍♂️", custom_id="claim_ticket_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        await interaction.response.send_message(f"✅ تم استلام الطلب بواسطة الإداري: {user.mention}")
        button.disabled = True
        button.label = f"مستلمة بواسطة {user.name}"
        await interaction.message.edit(view=self)

    @discord.ui.button(label="إغلاق", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="⚠️ تأكيد الإغلاق",
            description="هل أنت متأكد من أنك تريد إغلاق هذه التذكرة؟ لا يمكن التراجع عن هذا الإجراء.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView(), ephemeral=False)

class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="للأسئلة والاستفسارات", description="اضغط هنا لإجراء تذكرة للأسئلة والاستفسارات", emoji="❓", value="inquiry"),
            discord.SelectOption(label="للتقديم على رتبة", description="اضغط هنا للتقديم على رتبة (إدارة، ميديا، أو أخرى)", emoji="🌟", value="apply"),
            discord.SelectOption(label="للإبلاغ عن عضو", description="اضغط هنا لإجراء تذكرة للإبلاغ عن عضو", emoji="❗", value="report_user"),
            discord.SelectOption(label="للإبلاغ عن إداري", description="اضغط هنا لإجراء تذكرة للإبلاغ عن إداري", emoji="🛡️", value="report_admin"),
            discord.SelectOption(label="طلب فتح قروب", description="اضغط هنا لطلب إنشاء قروب أو روم خاص", emoji="👥", value="group"),
        ]
        super().__init__(placeholder="اختر أحد الأسباب لإنشاء التذكرة...", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        guild = interaction.guild
        user = interaction.user

        ticket_number = get_next_ticket_number()
        channel_name = f"ticket-{ticket_number}"

        ticket_details = {
            "inquiry": "استفسارات", "apply": "تقديم-رتبة",
            "report_user": "بلاغ-عضو", "report_admin": "بلاغ-إداري", "group": "طلب-قروب"
        }

        title_name = ticket_details.get(selected_value, "تذكرة")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)

        embed = discord.Embed(
            title=f"🎫 تذكرة جديدة: {title_name}",
            description=f"مرحبًا {user.mention} 👋\n\nيرجى كتابة تفاصيل طلبك هنا بوضوح، وسيقوم فريق الإدارة بالرد عليك في أقرب وقت.",
            color=discord.Color.dark_grey()
        )

        await ticket_channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✅ تم إنشاء تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)

class TicketSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ==========================================
# ⭐ نظام اللفلز والـ AFK
# ==========================================

user_xp = {}

async def add_xp(member, guild, channel_to_send, amount):
    user_id = member.id
    if user_id not in user_xp:
        user_xp[user_id] = {"xp": 0, "level": 1}

    user_xp[user_id]["xp"] += amount
    current_xp = user_xp[user_id]["xp"]
    current_level = user_xp[user_id]["level"]

    needed_xp = current_level * 100

    if current_xp >= needed_xp:
        user_xp[user_id]["level"] += 1
        new_level = user_xp[user_id]["level"]

        level_channel = discord.utils.get(guild.text_channels, name="levels") or channel_to_send

        role_text = ""
        if new_level in LEVEL_ROLES:
            new_role_name = LEVEL_ROLES[new_level]
            new_role = discord.utils.get(guild.roles, name=new_role_name)

            if new_role:
                for lvl, role_name in LEVEL_ROLES.items():
                    if lvl < new_level:
                        old_role = discord.utils.get(guild.roles, name=role_name)
                        if old_role and old_role in member.roles:
                            await member.remove_roles(old_role)

                await member.add_roles(new_role)
                role_text = f"\n🎖️ **مكافأة الرتبة:** حصلت على رتبة **{new_role.name}** وتمت إزالة الرتبة السابقة!"

        embed = discord.Embed(
            title="🎉 مبروك صعود لفل جديد!",
            description=f"كفو {member.mention}! لقد صعدت إلى **المستوى (Level {new_level})** 🚀{role_text}",
            color=discord.Color.gold()
        )
        await level_channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id

    if user_id in afk_users:
        reason = afk_users.pop(user_id)
        try:
            clean_name = message.author.display_name.replace("[AFK] ", "")
            await message.author.edit(nick=clean_name)
        except:
            pass
        embed = discord.Embed(
            description=f"👋 أهلاً بعودتك {message.author.mention}! تم إلغاء وضع الـ AFK تلقائياً.",
            color=discord.Color.green()
        )
        await message.channel.send(embed=embed, delete_after=5)

    if message.mentions:
        for mentioned in message.mentions:
            if mentioned.id in afk_users:
                reason = afk_users[mentioned.id]
                embed = discord.Embed(
                    title="💤 العضو في وضع الابتعاد (AFK)",
                    description=f"العضو {mentioned.mention} غير متواجد حالياً.\n**السبب:** {reason}",
                    color=discord.Color.blue()
                )
                await message.channel.send(embed=embed)

    await add_xp(message.author, message.guild, message.channel, 10)
    await bot.process_commands(message)

@tasks.loop(minutes=1.0)
async def voice_xp_loop():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot or member.voice.self_mute or member.voice.self_deaf:
                    continue
                level_channel = discord.utils.get(guild.text_channels, name="levels") or guild.system_channel
                if level_channel:
                    await add_xp(member, guild, level_channel, 5)

@voice_xp_loop.before_loop
async def before_voice_loop():
    await bot.wait_until_ready()

@bot.command()
async def afk(ctx, *, reason: str = "بدون سبب"):
    afk_users[ctx.author.id] = reason
    try:
        await ctx.author.edit(nick=f"[AFK] {ctx.author.display_name}")
    except:
        pass

    embed = discord.Embed(
        title=f"💤 {ctx.author.name} في وضع AFK",
        description=f"**الرسالة:** {reason}\n\n*سأقوم بالرد على أي رسالة تنوه بذكرك تلقائياً.*",
        color=discord.Color.dark_blue()
    )
    await ctx.send(embed=embed)

@bot.command(aliases=["rank", "لفل", "رانك"])
async def level_status(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_data = user_xp.get(target.id, {"xp": 0, "level": 1})
    
    embed = discord.Embed(title=f"📊 بطاقة إنجاز العضو: {target.name}", color=discord.Color.blue())
    embed.add_field(name="⭐ المستوى (Level)", value=str(user_data["level"]), inline=True)
    embed.add_field(name="✨ نقاط التفاعل (XP)", value=str(user_data["xp"]), inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

# ==========================================
# 🛠️ أوامر الإدارة والمساعدة الشاملة
# ==========================================

@bot.command(aliases=["clean", "p", "مسح"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 تم مسح `{amount}` رسالة بنجاح.")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(aliases=["قفل"])
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 تم قفل هذه القناة.")

@bot.command(aliases=["فتح"])
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 تم فتح هذه القناة.")

@bot.command(aliases=["طرد"])
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "لم يتم ذكر سبب"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 تم طرد العضو {member.mention} | السبب: {reason}")

@bot.command(aliases=["حظر", "بان"])
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "لم يتم ذكر سبب"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 تم حظر العضو {member.mention} | السبب: {reason}")

@bot.command(aliases=["قل", "قول"])
@commands.has_permissions(administrator=True)
async def say(ctx, *, message: str):
    await ctx.message.delete()
    embed = discord.Embed(description=message, color=discord.Color.blue())
    await ctx.send(embed=embed)

# أمر الأوامر الشامل (بكلمة cmds)
@bot.command(aliases=["cmds", "commands"])
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🤖 دليل أوامر البوت الشامل",
        description="إليك قائمة بجميع الأوامر المتاحة واستخداماتها في السيرفر:",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="👥 أوامر عامة (لكافة الأعضاء):",
        value=(
            "• `!cmds` أو `!commands` : عرض قائمة الأوامر هذه.\n"
            "• `!afk [السبب]` : تفعيل وضع الابتعاد والرد التلقائي عند التنويه.\n"
            "• `!rank` : عرض مستوى اللفل الحالي ونقاط التفاعل (XP)."
        ),
        inline=False
    )
    
    embed.add_field(
        name="🛡️ أوامر الإدارة والإشراف:",
        value=(
            "• `!setup_ticket` : إرسال لوحة تذاكر الدعم الفني والقائمة المنسدلة.\n"
            "• `!clear [العدد]` : مسح عدد محدد من الرسائل في القناة.\n"
            "• `!lock` : قفل القناة الحالية عن الكتابة.\n"
            "• `!unlock` : إعادة فتح القناة الحالية للكتابة.\n"
            "• `!kick @العضو` : طرد عضو من السيرفر.\n"
            "• `!ban @العضو` : حظر عضو من السيرفر.\n"
            "• `!say [النص]` : إرسال إعلان أو إشعار رسمي بأسلوب Embed."
        ),
        inline=False
    )
    
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

# ==========================================
# 🚀 تشغيل البوت
# ==========================================

@bot.event
async def on_ready():
    bot.add_view(TicketSelectView())
    bot.add_view(TicketControlView())
    bot.add_view(ConfirmCloseView())
    if not voice_xp_loop.is_running():
        voice_xp_loop.start()
    print(f'✅ تم تشغيل البوت والأوامر بنجاح باسم: {bot.user}')

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="تذاكر الدعم",
        description="يرجى عدم الاختيار إلا في الحالات الهامة جداً لإتمام التذكرة، قم باختيار السبب الذي تحتاجه ليتم فتح تذكرة لك مع أفضل الإداريين الذين سيساعدونك.",
        color=discord.Color.dark_grey()
    )
    embed.set_image(url="https://i.pinimg.com/1200x/12/9b/76/129b7630baa815012a13afb634f96d36.jpg")
    await ctx.send(embed=embed, view=TicketSelectView())

bot.run(os.getanv("DISCORD_TOKEN"))
