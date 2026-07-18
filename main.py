#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سورس حمزة | يوزربوت تيليثون
كل شيء في ملف واحد | تخزين JSON | بدون بوت خارجي | بدون قواعد بيانات
"""

import asyncio
import gzip
import html
import http.client
import io
import json
import os
import random
import re
import string
import sys
import time
import zlib
from datetime import datetime

try:
    import brotli
except ImportError:
    brotli = None

from telethon import TelegramClient, events, functions, types
from telethon.errors import (
    ChatAdminRequiredError,
    FloodWaitError,
    MessageIdInvalidError,
    MessageNotModifiedError,
    UserAdminInvalidError,
    UsernameNotOccupiedError,
    ChannelPrivateError,
    ChannelBannedError,
    UserIdInvalidError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    UserBannedInChannelError,
    UsersTooMuchError,
)
from telethon.sessions import StringSession
from telethon.tl.functions.channels import EditAdminRequest, EditBannedRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import (
    ChatAdminRights,
    ChatBannedRights,
    MessageEntityMentionName,
    ChatInvite,
    ChatInviteAlready,
    User,
    Channel,
    Chat,
)

# ============================================================
#                    الإعداد | CONFIG
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        # لا يوجد ملف — أنشئه واطلب البيانات
        cfg = {}
    else:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    cfg["API_ID"] = int(cfg.get("API_ID") or os.environ.get("API_ID") or 0)
    cfg["API_HASH"] = cfg.get("API_HASH") or os.environ.get("API_HASH") or ""
    cfg["STRING_SESSION"] = (
        cfg.get("STRING_SESSION") or os.environ.get("STRING_SESSION") or ""
    )
    cfg["PREFIX"] = cfg.get("PREFIX") or "."
    cfg["OWNER_NAME"] = cfg.get("OWNER_NAME") or "حمزة"
    # طلب البيانات تفاعلياً عند أول تشغيل
    if not cfg["API_ID"] or not cfg["API_HASH"]:
        print("=" * 45)
        print("  إعداد سورس حمزة — أدخل بياناتك:")
        print("=" * 45)
        try:
            aid = input("🔑 API_ID: ").strip()
            ahash = input("🔑 API_HASH: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("تم الإلغاء")
            sys.exit(1)
        cfg["API_ID"] = int(aid) if aid.isdigit() else 0
        cfg["API_HASH"] = ahash
        if not cfg["API_ID"] or not cfg["API_HASH"]:
            print("بيانات غير صحيحة")
            sys.exit(1)
        # حفظ ما أُدخل (رقم الهاتف يُطلب أثناء تسجيل الدخول)
        _save_cfg_basic(cfg)
        print("✓ تم حفظ API_ID و API_HASH")
    return cfg


def _save_cfg_basic(cfg):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["API_ID"] = cfg["API_ID"]
    data["API_HASH"] = cfg["API_HASH"]
    data["PREFIX"] = cfg["PREFIX"]
    data["OWNER_NAME"] = cfg["OWNER_NAME"]
    data["STRING_SESSION"] = cfg.get("STRING_SESSION", "")
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def save_session(session_str):
    """حفظ كود السيشن المولّد تلقائياً في config.json"""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["STRING_SESSION"] = session_str
    data.setdefault("API_ID", CONFIG["API_ID"])
    data.setdefault("API_HASH", CONFIG["API_HASH"])
    data.setdefault("PREFIX", CONFIG["PREFIX"])
    data.setdefault("OWNER_NAME", CONFIG["OWNER_NAME"])
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


CONFIG = load_config()
PREFIX = CONFIG["PREFIX"]
OWNER_NAME = CONFIG["OWNER_NAME"]

# ============================================================
#                  تخزين JSON | ملفات منفصلة
# ============================================================


def _path(name):
    return os.path.join(DATA_DIR, f"{name}.json")


def db_read(name, default=None):
    """قراءة ملف json | كل ميزة لها ملفها الخاص"""
    p = _path(name)
    if not os.path.exists(p):
        return {} if default is None else default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def db_write(name, data):
    """كتابة ملف json"""
    with open(_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def db_get(name, key, default=None):
    return db_read(name).get(str(key), default)


def db_set(name, key, value):
    data = db_read(name)
    data[str(key)] = value
    db_write(name, data)


def db_del(name, key):
    data = db_read(name)
    if str(key) in data:
        del data[str(key)]
        db_write(name, data)
        return True
    return False


# ============================================================
#                    العميل | CLIENT
# ============================================================

client = TelegramClient(
    StringSession(CONFIG["STRING_SESSION"]),
    CONFIG["API_ID"],
    CONFIG["API_HASH"],
    app_version="حمزة 1.0",
    auto_reconnect=True,
    connection_retries=None,
)

START_TIME = time.time()
CMD_SECTIONS = {}  # لتخزين اقسام الاوامر لعرضها في .الاوامر


# ============================================================
#            الديكوريتر الرئيسي | ar_cmd / cmd
# ============================================================


def cmd(pattern, groups_only=False, private_only=False, edited=True):
    """
    ديكوريتر تسجيل امر جديد
    pattern: النمط بعد البادئة | مثال: r"حظر(?:\\s|$)([\\s\\S]*)"
    """
    reg = re.compile("^\\" + PREFIX + pattern)

    def decorator(func):
        async def wrapper(event):
            if groups_only and not event.is_group:
                return await edit_delete(event, "- هذا الأمر للمجموعات فقط", 8)
            if private_only and not event.is_private:
                return await edit_delete(event, "- هذا الأمر للخاص فقط", 8)
            try:
                await func(event)
            except events.StopPropagation:
                raise
            except MessageNotModifiedError:
                pass
            except MessageIdInvalidError:
                pass
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 3)
            except ChatAdminRequiredError:
                await edit_delete(event, "- لا أملك صلاحيات كافية هنا", 8)
            except Exception as e:
                await edit_delete(event, f"- خطأ:\n`{e}`", 12)

        client.add_event_handler(
            wrapper, events.NewMessage(pattern=reg, outgoing=True)
        )
        if edited:
            client.add_event_handler(
                wrapper, events.MessageEdited(pattern=reg, outgoing=True)
            )
        return wrapper

    return decorator


# ============================================================
#                  دوال مساعدة | HELPERS
# ============================================================


async def edit_or_reply(event, text, link_preview=False, **kwargs):
    """يعدّل رسالتك أو يرد | يتعامل مع النص الطويل كملف | مع fallback عند فشل الإرسال"""
    text = str(text)
    try:
        if len(text) < 4096:
            try:
                return await event.edit(text, link_preview=link_preview, **kwargs)
            except Exception:
                return await event.reply(text, link_preview=link_preview, **kwargs)
        # نص طويل: أرسله كملف نصي
        return await _send_as_file(event, text)
    except MessageNotModifiedError:
        return event
    except Exception:
        # أي خطأ بالإرسال → أرسل كملف منفصل
        try:
            return await _send_as_file(event, text)
        except Exception:
            return event


async def _send_as_file(event, text):
    """يرسل النص كملف نصي مع تجنّب خطأ الإرسال"""
    try:
        file = io.BytesIO(text.encode("utf-8"))
        file.name = "result.txt"
        reply = await event.get_reply_message()
        target = reply or event
        sent = await target.reply("الناتج طويل/كبير — تم إرساله كملف 📄", file=file)
        try:
            await event.delete()
        except Exception:
            pass
        return sent
    except Exception as e:
        # المحاولة الأخيرة: تقسيم لرسائل أقصر
        return await _send_chunks(event, text, str(e))


async def _send_chunks(event, text, err=""):
    limit = 4000
    parts = [text[i:i + limit] for i in range(0, len(text), limit)]
    out = []
    for i, p in enumerate(parts, 1):
        prefix = f"(جزء {i}/{len(parts)}) " if len(parts) > 1 else ""
        try:
            out.append(await event.reply(prefix + p))
        except Exception:
            pass
    if not out and err:
        try:
            await event.reply(f"تعذّر الإرسال: {err}")
        except Exception:
            pass
    return out


async def edit_delete(event, text, seconds=8, link_preview=False):
    """يعدّل الرسالة ثم يحذفها بعد وقت"""
    try:
        msg = await event.edit(text, link_preview=link_preview)
    except Exception:
        try:
            msg = await event.reply(text, link_preview=link_preview)
        except Exception:
            return
    await asyncio.sleep(seconds)
    try:
        await msg.delete()
    except Exception:
        pass


async def get_target_user(event):
    """يجلب المستخدم المستهدف: بالرد أو بالمعرف/الايدي مع الأمر"""
    reply = await event.get_reply_message()
    if reply:
        try:
            user = await event.client.get_entity(reply.sender_id)
            return user, reply.sender_id
        except Exception:
            return None, reply.sender_id
    args = event.pattern_match.group(1)
    if args and args.strip():
        arg = args.strip().split()[0]
        try:
            if arg.isdigit() or (arg.startswith("-") and arg[1:].isdigit()):
                user = await event.client.get_entity(int(arg))
            else:
                user = await event.client.get_entity(arg)
            return user, user.id
        except Exception:
            return None, None
    return None, None


def get_display_name(user):
    if user is None:
        return "مجهول"
    name = user.first_name or ""
    if getattr(user, "last_name", None):
        name += f" {user.last_name}"
    return name.strip() or "مجهول"


def mention(user):
    if user is None:
        return "مجهول"
    return f"[{get_display_name(user)}](tg://user?id={user.id})"


def readable_time(seconds):
    seconds = int(seconds)
    result = ""
    for unit, count in (("ي", 86400), ("س", 3600), ("د", 60), ("ث", 1)):
        if seconds >= count:
            val = seconds // count
            seconds %= count
            result += f"{val}{unit} "
    return result.strip() or "0ث"


# ============================================================
#                 قائمة الأوامر | .الاوامر
# ============================================================

MENU_MAIN = f"""**[ سورس حمزة ]**
✦┅━╍━╍╍━━╍━━╍━┅✦

مرحبا بك عزيزي {OWNER_NAME}
هذه قائمة أقسام الأوامر — أرسل رقم القسم:

`{PREFIX}م1` ◂ أوامر الإدارة
`{PREFIX}م2` ◂ أوامر المجموعة
`{PREFIX}م3` ◂ أوامر الكشف والايدي
`{PREFIX}م4` ◂ أوامر الردود
`{PREFIX}م5` ◂ أوامر الترحيب
`{PREFIX}م6` ◂ أوامر حماية الخاص
`{PREFIX}م7` ◂ أوامر الإذاعة
`{PREFIX}م8` ◂ أوامر البوت
`{PREFIX}م9` ◂ أوامر المنع والترجمة
`{PREFIX}م10` ◂ أوامر السبام والصملات
`{PREFIX}م11` ◂ أوامر البروفايل
`{PREFIX}م12` ◂ أوامر الصيغ
`{PREFIX}م13` ◂ أوامر التسلية
`{PREFIX}م14` ◂ أوامر التحكم
`{PREFIX}م15` ◂ أوامر الذكاء الاصطناعي
`{PREFIX}م16` ◂ أوامر التحديثات
`{PREFIX}م17` ◂ باند و شد (فحص الروابط)"""

MENU = {
    "م1": """**◂ أوامر الإدارة :**

`{p}حظر` ◂ بالرد أو المعرف لحظر شخص
`{p}الغاء حظر` ◂ لفك حظر شخص
`{p}كتم` ◂ لكتم شخص
`{p}الغاء كتم` ◂ لفك كتم شخص
`{p}طرد` ◂ لطرد شخص من المجموعة
`{p}رفع مشرف` <لقب> ◂ لرفع شخص مشرف
`{p}تنزيل مشرف` ◂ لتنزيل مشرف
`{p}تثبيت` ◂ لتثبيت رسالة بالرد
`{p}الغاء تثبيت` ◂ لإلغاء التثبيت
`{p}مسح` <عدد> ◂ لحذف رسائل
`{p}تحذير` ◂ لتحذير عضو
`{p}التحذيرات` ◂ لعرض تحذيرات عضو
`{p}حذف التحذيرات` ◂ لمسح تحذيرات عضو""",
    "م2": """**◂ أوامر المجموعة :**

`{p}المشرفين` ◂ لعرض مشرفي المجموعة
`{p}الاعضاء` ◂ لعرض عدد الأعضاء
`{p}معلومات` ◂ لعرض معلومات المجموعة
`{p}البوتات` ◂ لعرض البوتات في المجموعة""",
    "م3": """**◂ أوامر الكشف والايدي :**

`{p}الايدي` ◂ بالرد أو المعرف لعرض الايدي
`{p}كشف` ◂ لعرض معلومات مستخدم
`{p}صورة` ◂ لجلب صورة مستخدم""",
    "م4": """**◂ أوامر الردود :**

`{p}اضف رد` <كلمة> ◂ بالرد لإضافة رد على كلمة
`{p}حذف رد` <كلمة> ◂ لحذف رد
`{p}الردود` ◂ لعرض جميع الردود
`{p}مسح الردود` ◂ لحذف كل الردود""",
    "م5": """**◂ أوامر الترحيب :**

`{p}ضبط ترحيب` <النص> ◂ لضبط رسالة ترحيب
`{p}الترحيب` ◂ لعرض الترحيب الحالي
`{p}حذف الترحيب` ◂ لإلغاء الترحيب
(المتغيرات: {{name}} {{title}} {{count}})""",
    "م6": """**◂ أوامر حماية الخاص :**

`{p}الحماية تشغيل` ◂ لتشغيل حماية الخاص
`{p}الحماية تعطيل` ◂ لتعطيل حماية الخاص
`{p}سماح` ◂ للسماح لشخص بالخاص
`{p}رفض` ◂ لرفض شخص من الخاص
`{p}المسموحين` ◂ لعرض المسموح لهم""",
    "م7": """**◂ أوامر الإذاعة :**

`{p}للكروبات` <النص> ◂ لنشر رسالة بكل مجموعاتك
`{p}للخاص` <النص> ◂ لإرسال رسالة لكل محادثاتك الخاصة""",
    "م8": """**◂ أوامر البوت :**

`{p}فحص` ◂ لعرض معلومات السورس
`{p}بنك` ◂ لعرض سرعة الاستجابة
`{p}اعادة تشغيل` ◂ لإعادة تشغيل السورس
`{p}الوقت` ◂ لعرض مدة التشغيل""",
    "م9": """**◂ أوامر المنع والترجمة :**

`{p}منع` <كلمة> ◂ لمنع كلمة في المجموعة
`{p}الغاء منع` <كلمة> ◂ لإلغاء منع كلمة
`{p}قائمة المنع` ◂ لعرض الكلمات الممنوعة
`{p}ترجمة` <كود> ◂ بالرد لترجمة النص""",
    "م10": """**◂ أوامر السبام والصملات :**

`{p}نيكه` ◂ سبام سب مولّد تلقائياً (بالرد يستهدف)
`{p}خلاص` ◂ لإيقاف السبام
`{p}سرعه` <ثواني> ◂ لضبط سرعة الإرسال
`{p}تتبع` ◂ رد تلقائي بالسب على أي رسالة خاصة
`{p}كافي` ◂ لإيقاف الرد التلقائي
`{p}معاينة سب` ◂ لعرض عينات من المولّد
`{p}عدد السب` ◂ لعرض عدد التركيبات الممكنة
`{p}اضف سب` <النوع> <النص> ◂ لإثراء المكتبة
  (الأنواع: قريب | فعل | جمله | صفه | لاحقه | ساخره | قالب)
`{p}حماية الفلود` ◂ لتشغيل/إيقاف الحماية
`{p}الفلود` ◂ لعرض إحصائيات الحماية
`{p}تحديد` ◂ بالرد لتحديد رسالة من المحفوظات
`{p}تشغيل التحويل` ◂ لبدء التحويل من المحفوظات
`{p}ايقاف التحويل` ◂ لإيقاف التحويل
`{p}ديلاي` <ثواني> ◂ لضبط زمن التحويل""",
    "م11": """**◂ أوامر البروفايل :**

`{p}تغيير اسم` <الاسم> ◂ لتغيير اسمك
`{p}تغيير بايو` <النص> ◂ لتغيير نبذتك
`{p}تغيير صورة` ◂ بالرد لتغيير صورتك
`{p}حسابي` ◂ لعرض معلومات حسابك""",
    "م12": """**◂ أوامر الصيغ :**

`{p}ملصق` ◂ بالرد على صورة لتحويلها ملصق
`{p}صورة` ◂ بالرد على ملصق لتحويله صورة""",
    "م13": """**◂ أوامر التسلية :**

`{p}نسبة الحب` ◂ لعرض نسبة الحب
`{p}نسبة الغباء` ◂ لعرض نسبة الغباء
`{p}قلوب` ◂ لعرض قلوب متحركة
`{p}عد` <رقم> ◂ للعد التنازلي
`{p}نرد` ◂ لرمي النرد""",
    "م14": """**◂ أوامر التحكم :**

`{p}التحكم تشغيل` ◂ لتفعيل تحكم مستخدمين آخرين
`{p}التحكم تعطيل` ◂ لتعطيل التحكم
`{p}اضف متحكم` ◂ بالرد لإضافة متحكم
`{p}ازالة متحكم` ◂ بالرد لإزالة متحكم
`{p}المتحكمين` ◂ لعرض المتحكمين""",
    "م15": """**◂ أوامر الذكاء الاصطناعي (للمالك فقط):**

`{p}ذكاء` <نص> ◂ محادثة تفاعلية + تنفيذ أدوات Telethon (JSON) ورد النتيجة
`{p}ذكاء مفعل` ◂ تفعيل الوضع الشامل للأمر فقط (يحقن تعريف الأدوات بـ JSON parameters وينفّذ أي أداة بلا حدود). لا رد تلقائي بالخاص
`{p}ذكاء تشغيل` ◂ رد تلقائي بالخاص (بدون أدوات)
`{p}ذكاء تعطيل` ◂ إيقاف الرد التلقائي
`{p}ذكاء سياق` <رقم> ◂ عدد رسائل السياق (الافتراضي 50)
`{p}ذكاء ذاكرة` ◂ عرض الذاكرة | `{p}ذكاء ذاكرة مسح` لمسحها
`{p}ذكاء جلسة` ◂ عرض/مسح جلسة المحادثة التفاعلية
`{p}دليل الذكاء` ◂ توليد دليل السورس | `{p}ادوات الذكاء` لعرض الأدوات
`{p}تعليمات الذكاء` ◂ عرض التعليمات | `<نص>` تعديل | `افتراضي` إرجاع

ملاحظة: في الوضع الشامل يكتب الذكاء استدعاء أداة JSON (بما فيها raw_tl بلا قيود) فينفّذها الكود ويعرض النتيجة ويتابع المحادثة.""",
    "م16": """**◂ أوامر التحديثات :**

`{p}تحديث` ◂ لتنزيل آخر تحديث من GitHub وإعادة التشغيل
`{p}تحديثات` ◂ لعرض آخر التحديثات والإضافات من GitHub
`{p}اخر_تحديث` ◂ لعرض آخر إصدار منشور""",
    "م17": """**◂ باند و شد (فحص الروابط والمجموعات):**

**الفحص:**
`{p}فحص` <رابط/يوزر/آيدي> ◂ لفحص إن كان محظوراً/منتهياً/سكام
`{p}فحص_دفعه` <رابط> ◂ فحص دعوة (ينضم مؤقتاً ويفحص)
`{p}فحص_مجموعه` ◂ فحص المجموعة الحالية

 **الشد الداخلي (بلاغ مستمر):**
`{p}شد_هدف` <رابط/يوزر> ◂ يضع هدف البلاغ
`{p}شد_نوع` <نوع> ◂ نوع المخالفة (سبام/اباحي/عنف/تحرش/حقوق/وهمي/غير_قانوني/اخر)
`{p}شد_رساله` <نص> ◂ نص رسالة البلاغ
`{p}شد_سرعه` <ثواني> ◂ سرعة التأخير بين البلاغات (1-60)
`{p}شد` <رابط/يوزر> ◂ يبدأ البلاغ المستمر (يفحص كل دورة هل الهدف محظور)
`{p}شد_ايقاف` ◂ يوقف البلاغ المستمر
`{p}شد_اعداد` ◂ عرض الإعدادات""",
}


@cmd(r"الاوامر$")
async def _(event):
    await edit_or_reply(event, MENU_MAIN)


for _sec, _txt in MENU.items():
    def _make(txt):
        async def handler(event):
            await edit_or_reply(event, txt.format(p=PREFIX))
        return handler
    client.add_event_handler(
        _make(_txt),
        events.NewMessage(pattern=re.compile("^\\" + PREFIX + _sec + "$"), outgoing=True),
    )
    client.add_event_handler(
        _make(_txt),
        events.MessageEdited(pattern=re.compile("^\\" + PREFIX + _sec + "$"), outgoing=True),
    )


# ============================================================
#                  أوامر الإدارة | ADMIN
# ============================================================

BAN_RIGHTS = ChatBannedRights(until_date=None, view_messages=True)
UNBAN_RIGHTS = ChatBannedRights(
    until_date=None, view_messages=False, send_messages=False,
    send_media=False, send_stickers=False, send_gifs=False,
    send_games=False, send_inline=False, embed_links=False,
)
MUTE_RIGHTS = ChatBannedRights(until_date=None, send_messages=True)
UNMUTE_RIGHTS = ChatBannedRights(until_date=None, send_messages=False)


@cmd(r"حظر(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص أو ضع معرفه", 8)
    try:
        await event.client(EditBannedRequest(event.chat_id, uid, BAN_RIGHTS))
    except Exception as e:
        return await edit_delete(event, f"- تعذر الحظر: `{e}`", 8)
    await edit_or_reply(event, f"تم حظر {mention(user)} ✓")


@cmd(r"الغاء حظر(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص أو ضع معرفه", 8)
    try:
        await event.client(EditBannedRequest(event.chat_id, uid, UNBAN_RIGHTS))
    except Exception as e:
        return await edit_delete(event, f"- تعذر فك الحظر: `{e}`", 8)
    await edit_or_reply(event, f"تم فك حظر {mention(user)} ✓")


@cmd(r"كتم(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص أو ضع معرفه", 8)
    try:
        await event.client(EditBannedRequest(event.chat_id, uid, MUTE_RIGHTS))
    except Exception as e:
        return await edit_delete(event, f"- تعذر الكتم: `{e}`", 8)
    await edit_or_reply(event, f"تم كتم {mention(user)} ✓")


@cmd(r"الغاء كتم(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص أو ضع معرفه", 8)
    try:
        await event.client(EditBannedRequest(event.chat_id, uid, UNMUTE_RIGHTS))
    except Exception as e:
        return await edit_delete(event, f"- تعذر فك الكتم: `{e}`", 8)
    await edit_or_reply(event, f"تم فك كتم {mention(user)} ✓")


@cmd(r"طرد(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص أو ضع معرفه", 8)
    try:
        await event.client.kick_participant(event.chat_id, uid)
    except Exception as e:
        return await edit_delete(event, f"- تعذر الطرد: `{e}`", 8)
    await edit_or_reply(event, f"تم طرد {mention(user)} ✓")


@cmd(r"رفع مشرف(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    reply = await event.get_reply_message()
    title = OWNER_NAME
    args = event.pattern_match.group(1)
    uid = None
    if reply:
        uid = reply.sender_id
        if args and args.strip():
            title = args.strip()
    elif args and args.strip():
        parts = args.strip().split(maxsplit=1)
        try:
            uid = (await event.client.get_entity(parts[0])).id
        except Exception:
            return await edit_delete(event, "- لم أجد المستخدم", 8)
        if len(parts) > 1:
            title = parts[1]
    if not uid:
        return await edit_delete(event, "- رد على شخص لرفعه", 8)
    rights = ChatAdminRights(
        change_info=True, post_messages=True, edit_messages=True,
        delete_messages=True, ban_users=True, invite_users=True,
        pin_messages=True, add_admins=False, manage_call=True,
    )
    try:
        await event.client(EditAdminRequest(event.chat_id, uid, rights, title[:16]))
    except Exception as e:
        return await edit_delete(event, f"- تعذر الرفع: `{e}`", 8)
    user, _ = await get_target_user(event)
    await edit_or_reply(event, f"تم رفع {mention(user)} مشرفاً ✓")


@cmd(r"تنزيل مشرف(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص أو ضع معرفه", 8)
    rights = ChatAdminRights(
        change_info=False, post_messages=False, edit_messages=False,
        delete_messages=False, ban_users=False, invite_users=False,
        pin_messages=False, add_admins=False,
    )
    try:
        await event.client(EditAdminRequest(event.chat_id, uid, rights, ""))
    except Exception as e:
        return await edit_delete(event, f"- تعذر التنزيل: `{e}`", 8)
    await edit_or_reply(event, f"تم تنزيل {mention(user)} من الإشراف ✓")


@cmd(r"تثبيت$", groups_only=True)
async def _(event):
    reply = await event.get_reply_message()
    if not reply:
        return await edit_delete(event, "- رد على رسالة لتثبيتها", 8)
    try:
        await event.client.pin_message(event.chat_id, reply.id, notify=True)
    except Exception as e:
        return await edit_delete(event, f"- تعذر التثبيت: `{e}`", 8)
    await edit_delete(event, "تم التثبيت ✓", 5)


@cmd(r"الغاء تثبيت$", groups_only=True)
async def _(event):
    reply = await event.get_reply_message()
    try:
        if reply:
            await event.client.unpin_message(event.chat_id, reply.id)
        else:
            await event.client.unpin_message(event.chat_id)
    except Exception as e:
        return await edit_delete(event, f"- تعذر الإلغاء: `{e}`", 8)
    await edit_delete(event, "تم إلغاء التثبيت ✓", 5)


@cmd(r"مسح(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    reply = await event.get_reply_message()
    args = event.pattern_match.group(1)
    count = 0
    if reply:
        msgs = []
        async for msg in event.client.iter_messages(
            event.chat_id, min_id=reply.id - 1, reverse=True
        ):
            msgs.append(msg.id)
            if len(msgs) >= 500:
                break
        if msgs:
            await event.client.delete_messages(event.chat_id, msgs)
            count = len(msgs)
    elif args and args.strip().isdigit():
        n = int(args.strip())
        msgs = []
        async for msg in event.client.iter_messages(event.chat_id, limit=n + 1):
            msgs.append(msg.id)
        if msgs:
            await event.client.delete_messages(event.chat_id, msgs)
            count = len(msgs)
    else:
        return await edit_delete(event, "- رد على رسالة أو ضع عدداً", 8)
    m = await event.client.send_message(event.chat_id, f"تم حذف {count} رسالة ✓")
    await asyncio.sleep(4)
    await m.delete()


@cmd(r"تحذير(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص لتحذيره", 8)
    key = f"{event.chat_id}"
    warns = db_read("warns")
    chat = warns.get(key, {})
    chat[str(uid)] = chat.get(str(uid), 0) + 1
    warns[key] = chat
    db_write("warns", warns)
    n = chat[str(uid)]
    text = f"تم تحذير {mention(user)}\nعدد التحذيرات: {n}/3"
    if n >= 3:
        try:
            await event.client(EditBannedRequest(event.chat_id, uid, MUTE_RIGHTS))
            text += "\nتم كتمه لتجاوزه الحد ✓"
        except Exception:
            pass
        chat[str(uid)] = 0
        warns[key] = chat
        db_write("warns", warns)
    await edit_or_reply(event, text)


@cmd(r"التحذيرات(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص", 8)
    n = db_read("warns").get(f"{event.chat_id}", {}).get(str(uid), 0)
    await edit_or_reply(event, f"تحذيرات {mention(user)}: {n}/3")


@cmd(r"حذف التحذيرات(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص", 8)
    warns = db_read("warns")
    key = f"{event.chat_id}"
    if key in warns and str(uid) in warns[key]:
        warns[key][str(uid)] = 0
        db_write("warns", warns)
    await edit_or_reply(event, f"تم حذف تحذيرات {mention(user)} ✓")


# ============================================================
#            أوامر المجموعة + الايدي + الكشف
# ============================================================


@cmd(r"الايدي(?:\s|$)([\s\S]*)")
async def _(event):
    args = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    if args and args.strip():
        try:
            p = await event.client.get_entity(args.strip())
        except Exception as e:
            return await edit_delete(event, f"`{e}`", 6)
        name = getattr(p, "title", None) or get_display_name(p)
        return await edit_or_reply(event, f"ايدي `{name}` هو `{p.id}`")
    if reply:
        txt = f"**ايدي الدردشة:** `{event.chat_id}`\n**ايدي المرسل:** `{reply.sender_id}`"
        if reply.media:
            txt += "\n**نوع:** ميديا"
        return await edit_or_reply(event, txt)
    await edit_or_reply(event, f"**ايدي الدردشة:** `{event.chat_id}`")


@cmd(r"كشف(?:\s|$)([\s\S]*)")
async def _(event):
    user, uid = await get_target_user(event)
    if not user:
        return await edit_delete(event, "- رد على شخص أو ضع معرفه", 8)
    txt = f"""**◂ كشف المستخدم :**
**الاسم:** {get_display_name(user)}
**الايدي:** `{user.id}`
**المعرف:** @{user.username if user.username else 'لا يوجد'}
**بوت:** {'نعم' if user.bot else 'لا'}
**مقيد:** {'نعم' if getattr(user, 'restricted', False) else 'لا'}
**الرابط:** [هنا](tg://user?id={user.id})"""
    await edit_or_reply(event, txt)


@cmd(r"صورة(?:\s|$)([\s\S]*)")
async def _(event):
    user, uid = await get_target_user(event)
    if not user:
        return await edit_delete(event, "- رد على شخص أو ضع معرفه", 8)
    m = await event.edit("- جاري الجلب...")
    try:
        photo = await event.client.download_profile_photo(user.id)
        if not photo:
            return await edit_delete(event, "- لا يوجد صورة", 6)
        await event.client.send_file(
            event.chat_id, photo, caption=f"صورة {mention(user)}"
        )
        os.remove(photo)
        await m.delete()
    except Exception as e:
        await edit_delete(event, f"`{e}`", 6)


@cmd(r"المشرفين$", groups_only=True)
async def _(event):
    admins = []
    async for u in event.client.iter_participants(
        event.chat_id, filter=types.ChannelParticipantsAdmins
    ):
        admins.append(f"• {mention(u)} — `{u.id}`")
    txt = "**◂ مشرفو المجموعة :**\n\n" + "\n".join(admins)
    await edit_or_reply(event, txt)


@cmd(r"الاعضاء$", groups_only=True)
async def _(event):
    chat = await event.get_chat()
    full = await event.client.get_participants(event.chat_id, limit=0)
    await edit_or_reply(
        event, f"**عدد أعضاء** {chat.title}: `{full.total}`"
    )


@cmd(r"البوتات$", groups_only=True)
async def _(event):
    bots = []
    async for u in event.client.iter_participants(event.chat_id):
        if u.bot:
            bots.append(f"• {mention(u)} — `{u.id}`")
    if not bots:
        return await edit_or_reply(event, "- لا يوجد بوتات في هذه المجموعة")
    await edit_or_reply(event, "**◂ البوتات :**\n\n" + "\n".join(bots))


@cmd(r"معلومات$", groups_only=True)
async def _(event):
    chat = await event.get_chat()
    full = await event.client.get_participants(event.chat_id, limit=0)
    txt = f"""**◂ معلومات المجموعة :**
**الاسم:** {chat.title}
**الايدي:** `{event.chat_id}`
**عدد الأعضاء:** `{full.total}`
**المعرف:** @{chat.username if getattr(chat, 'username', None) else 'خاصة'}"""
    await edit_or_reply(event, txt)


# ============================================================
#              أوامر الردود | REPLIES
# ============================================================


@cmd(r"اضف رد(?:\s|$)([\s\S]*)")
async def _(event):
    reply = await event.get_reply_message()
    word = event.pattern_match.group(1)
    if not reply or not word or not word.strip():
        return await edit_delete(event, "- رد على النص واكتب: اضف رد <الكلمة>", 8)
    if not reply.text:
        return await edit_delete(event, "- الرد يجب أن يكون نصاً", 8)
    db_set("replies", word.strip(), reply.text)
    await edit_or_reply(event, f"تم إضافة رد على: `{word.strip()}` ✓")


@cmd(r"حذف رد(?:\s|$)([\s\S]*)")
async def _(event):
    word = event.pattern_match.group(1)
    if not word or not word.strip():
        return await edit_delete(event, "- اكتب: حذف رد <الكلمة>", 8)
    if db_del("replies", word.strip()):
        await edit_or_reply(event, f"تم حذف الرد: `{word.strip()}` ✓")
    else:
        await edit_delete(event, "- لا يوجد رد بهذا الاسم", 8)


@cmd(r"الردود$")
async def _(event):
    data = db_read("replies")
    if not data:
        return await edit_or_reply(event, "- لا يوجد ردود مضافة")
    txt = "**◂ الردود المضافة :**\n\n" + "\n".join(f"• `{k}`" for k in data)
    await edit_or_reply(event, txt)


@cmd(r"مسح الردود$")
async def _(event):
    db_write("replies", {})
    await edit_or_reply(event, "تم حذف جميع الردود ✓")


@client.on(events.NewMessage(incoming=True))
async def _replies_watcher(event):
    if not event.text:
        return
    data = db_read("replies")
    if not data:
        return
    reply = data.get(event.raw_text.strip())
    if reply:
        try:
            await event.reply(reply)
        except Exception:
            pass


# ============================================================
#              أوامر الترحيب | WELCOME
# ============================================================


@cmd(r"ضبط ترحيب(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    text = event.pattern_match.group(1)
    if not text or not text.strip():
        return await edit_delete(event, "- اكتب نص الترحيب بعد الأمر", 8)
    db_set("welcome", event.chat_id, text.strip())
    await edit_or_reply(event, "تم ضبط رسالة الترحيب ✓")


@cmd(r"الترحيب$", groups_only=True)
async def _(event):
    w = db_get("welcome", event.chat_id)
    if not w:
        return await edit_or_reply(event, "- لا يوجد ترحيب مضبوط")
    await edit_or_reply(event, f"**الترحيب الحالي:**\n\n{w}")


@cmd(r"حذف الترحيب$", groups_only=True)
async def _(event):
    if db_del("welcome", event.chat_id):
        await edit_or_reply(event, "تم حذف الترحيب ✓")
    else:
        await edit_or_reply(event, "- لا يوجد ترحيب أصلاً")


@client.on(events.ChatAction)
async def _welcome_watcher(event):
    if not (event.user_joined or event.user_added):
        return
    w = db_get("welcome", event.chat_id)
    if not w:
        return
    try:
        user = await event.get_user()
        chat = await event.get_chat()
        count = (await event.client.get_participants(event.chat_id, limit=0)).total
        msg = w.replace("{name}", get_display_name(user))
        msg = msg.replace("{title}", chat.title)
        msg = msg.replace("{count}", str(count))
        await event.client.send_message(event.chat_id, msg)
    except Exception:
        pass


# ============================================================
#              أوامر المنع | LOCKED WORDS
# ============================================================


@cmd(r"منع(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    word = event.pattern_match.group(1)
    if not word or not word.strip():
        return await edit_delete(event, "- اكتب: منع <الكلمة>", 8)
    data = db_read("locked")
    key = f"{event.chat_id}"
    words = data.get(key, [])
    if word.strip() not in words:
        words.append(word.strip())
    data[key] = words
    db_write("locked", data)
    await edit_or_reply(event, f"تم منع الكلمة: `{word.strip()}` ✓")


@cmd(r"الغاء منع(?:\s|$)([\s\S]*)", groups_only=True)
async def _(event):
    word = event.pattern_match.group(1)
    if not word or not word.strip():
        return await edit_delete(event, "- اكتب: الغاء منع <الكلمة>", 8)
    data = db_read("locked")
    key = f"{event.chat_id}"
    words = data.get(key, [])
    if word.strip() in words:
        words.remove(word.strip())
        data[key] = words
        db_write("locked", data)
        await edit_or_reply(event, f"تم إلغاء منع: `{word.strip()}` ✓")
    else:
        await edit_delete(event, "- الكلمة غير ممنوعة", 8)


@cmd(r"قائمة المنع$", groups_only=True)
async def _(event):
    words = db_read("locked").get(f"{event.chat_id}", [])
    if not words:
        return await edit_or_reply(event, "- لا يوجد كلمات ممنوعة")
    txt = "**◂ الكلمات الممنوعة :**\n\n" + "\n".join(f"• `{w}`" for w in words)
    await edit_or_reply(event, txt)


@client.on(events.NewMessage(incoming=True))
async def _locked_watcher(event):
    if not event.text or not event.is_group:
        return
    words = db_read("locked").get(f"{event.chat_id}", [])
    if not words:
        return
    low = event.raw_text.lower()
    if any(w.lower() in low for w in words):
        try:
            await event.delete()
        except Exception:
            pass


# ============================================================
#            أوامر حماية الخاص | PMPERMIT
# ============================================================

PM_WARN_TEXT = (
    f"**◂ حماية الخاص — سورس حمزة**\n\n"
    "هذا حساب محمي، انتظر موافقة صاحب الحساب.\n"
    "تكرار الرسائل سيؤدي لحظرك."
)
PM_LIMIT = 5


@cmd(r"الحماية تشغيل$")
async def _(event):
    db_set("settings", "pmpermit", True)
    await edit_or_reply(event, "تم تشغيل حماية الخاص ✓")


@cmd(r"الحماية تعطيل$")
async def _(event):
    db_set("settings", "pmpermit", False)
    await edit_or_reply(event, "تم تعطيل حماية الخاص ✓")


@cmd(r"سماح(?:\s|$)([\s\S]*)", private_only=True)
async def _(event):
    uid = event.chat_id
    allowed = db_read("pm_allowed")
    allowed[str(uid)] = True
    db_write("pm_allowed", allowed)
    counts = db_read("pm_counts")
    counts.pop(str(uid), None)
    db_write("pm_counts", counts)
    await edit_or_reply(event, "تم السماح لهذا الشخص بالخاص ✓")


@cmd(r"رفض(?:\s|$)([\s\S]*)", private_only=True)
async def _(event):
    uid = event.chat_id
    allowed = db_read("pm_allowed")
    allowed.pop(str(uid), None)
    db_write("pm_allowed", allowed)
    await edit_or_reply(event, "تم رفض هذا الشخص من الخاص ✓")


@cmd(r"المسموحين$")
async def _(event):
    allowed = db_read("pm_allowed")
    if not allowed:
        return await edit_or_reply(event, "- لا يوجد مسموح لهم")
    txt = "**◂ المسموح لهم بالخاص :**\n\n" + "\n".join(
        f"• `{k}`" for k in allowed
    )
    await edit_or_reply(event, txt)


@client.on(events.NewMessage(incoming=True))
async def _pmpermit_watcher(event):
    if not event.is_private:
        return
    if not db_get("settings", "pmpermit", False):
        return
    sender = await event.get_sender()
    if sender is None or sender.bot or getattr(sender, "verified", False):
        return
    if event.chat_id == (await event.client.get_me()).id:
        return
    uid = str(event.chat_id)
    if db_read("pm_allowed").get(uid):
        return
    if getattr(sender, "is_self", False):
        return
    contact = getattr(sender, "contact", False)
    if contact:
        return
    counts = db_read("pm_counts")
    n = counts.get(uid, 0) + 1
    counts[uid] = n
    db_write("pm_counts", counts)
    if n >= PM_LIMIT:
        try:
            await event.client(BlockRequest(event.chat_id))
            await event.respond("تم حظرك لتكرار الرسائل.")
        except Exception:
            pass
        counts.pop(uid, None)
        db_write("pm_counts", counts)
        return
    try:
        await event.respond(f"{PM_WARN_TEXT}\n\nتحذير {n}/{PM_LIMIT}")
    except Exception:
        pass


# ============================================================
#              أوامر الإذاعة | BROADCAST
# ============================================================


@cmd(r"للكروبات(?:\s|$)([\s\S]*)")
async def _(event):
    reply = await event.get_reply_message()
    text = event.pattern_match.group(1)
    if not reply and not (text and text.strip()):
        return await edit_delete(event, "- اكتب نصاً أو رد على رسالة", 8)
    m = await event.edit("- جاري النشر بالمجموعات...")
    done, failed = 0, 0
    async for dialog in event.client.iter_dialogs():
        if dialog.is_group:
            try:
                if reply:
                    await event.client.send_message(dialog.id, reply)
                else:
                    await event.client.send_message(dialog.id, text.strip())
                done += 1
                await asyncio.sleep(0.5)
            except Exception:
                failed += 1
    await m.edit(f"تم النشر ✓\nنجح: {done} | فشل: {failed}")


@cmd(r"للخاص(?:\s|$)([\s\S]*)")
async def _(event):
    reply = await event.get_reply_message()
    text = event.pattern_match.group(1)
    if not reply and not (text and text.strip()):
        return await edit_delete(event, "- اكتب نصاً أو رد على رسالة", 8)
    m = await event.edit("- جاري النشر بالخاص...")
    done, failed = 0, 0
    async for dialog in event.client.iter_dialogs():
        if dialog.is_user and not dialog.entity.bot:
            try:
                if reply:
                    await event.client.send_message(dialog.id, reply)
                else:
                    await event.client.send_message(dialog.id, text.strip())
                done += 1
                await asyncio.sleep(0.5)
            except Exception:
                failed += 1
    await m.edit(f"تم النشر ✓\nنجح: {done} | فشل: {failed}")


# ============================================================
#              أوامر البوت | SYSTEM
# ============================================================


@cmd(r"بنك$")
async def _(event):
    start = time.time()
    m = await event.edit("...")
    ms = (time.time() - start) * 1000
    await m.edit(f"**السرعة:** `{ms:.2f}` ms")


@cmd(r"الوقت$")
async def _(event):
    up = readable_time(time.time() - START_TIME)
    await edit_or_reply(event, f"**مدة التشغيل:** {up}")


@cmd(r"اعادة تشغيل$")
async def _(event):
    await event.edit("- جاري إعادة التشغيل...")
    db_set("settings", "restart_chat", event.chat_id)
    db_set("settings", "restart_msg", event.id)
    await event.client.disconnect()
    os.execl(sys.executable, sys.executable, os.path.abspath(__file__))


# ============================================================
#              أوامر البروفايل | PROFILE
# ============================================================


@cmd(r"تغيير اسم(?:\s|$)([\s\S]*)")
async def _(event):
    name = event.pattern_match.group(1)
    if not name or not name.strip():
        return await edit_delete(event, "- اكتب الاسم بعد الأمر", 8)
    parts = name.strip().split(maxsplit=1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""
    try:
        await event.client(
            functions.account.UpdateProfileRequest(
                first_name=first, last_name=last
            )
        )
    except Exception as e:
        return await edit_delete(event, f"`{e}`", 8)
    await edit_or_reply(event, "تم تغيير الاسم ✓")


@cmd(r"تغيير بايو(?:\s|$)([\s\S]*)")
async def _(event):
    bio = event.pattern_match.group(1)
    if not bio or not bio.strip():
        return await edit_delete(event, "- اكتب البايو بعد الأمر", 8)
    try:
        await event.client(
            functions.account.UpdateProfileRequest(about=bio.strip())
        )
    except Exception as e:
        return await edit_delete(event, f"`{e}`", 8)
    await edit_or_reply(event, "تم تغيير البايو ✓")


@cmd(r"تغيير صورة$")
async def _(event):
    reply = await event.get_reply_message()
    if not reply or not reply.media:
        return await edit_delete(event, "- رد على صورة", 8)
    m = await event.edit("- جاري التغيير...")
    try:
        photo = await event.client.download_media(reply.media)
        up = await event.client.upload_file(photo)
        await event.client(functions.photos.UploadProfilePhotoRequest(file=up))
        os.remove(photo)
        await m.edit("تم تغيير الصورة ✓")
    except Exception as e:
        await m.edit(f"`{e}`")


@cmd(r"حسابي$")
async def _(event):
    me = await event.client.get_me()
    txt = f"""**◂ معلومات حسابك :**
**الاسم:** {get_display_name(me)}
**الايدي:** `{me.id}`
**المعرف:** @{me.username if me.username else 'لا يوجد'}
**الرقم:** `+{me.phone if me.phone else 'مخفي'}`
**بريميوم:** {'نعم' if getattr(me, 'premium', False) else 'لا'}"""
    await edit_or_reply(event, txt)


# ============================================================
#              أوامر الترجمة | TRANSLATE
# ============================================================


@cmd(r"ترجمة(?:\s|$)([\s\S]*)")
async def _(event):
    reply = await event.get_reply_message()
    arg = event.pattern_match.group(1)
    lang = (arg.strip() or "ar") if arg else "ar"
    if reply and reply.text:
        text = reply.text
    elif arg and len(arg.strip().split(maxsplit=1)) > 1:
        lang, text = arg.strip().split(maxsplit=1)
    else:
        return await edit_delete(event, "- رد على نص | مثال: ترجمة en", 8)
    try:
        from googletrans import Translator
        tr = Translator()
        res = tr.translate(text, dest=lang)
        await edit_or_reply(
            event, f"**الترجمة ({res.src} ◂ {lang}):**\n\n{res.text}"
        )
    except Exception as e:
        await edit_delete(event, f"- تعذر الترجمة (ثبّت googletrans): `{e}`", 10)


# ============================================================
#          أوامر السبام والصملات | SPAM & FORWARD
# ============================================================

# --- الحالة ---
spam_running = False
spam_task = None
spam_typing_task = None
spam_delay = 5.0
follow_running = False
forward_running = False
forward_task = None
forward_delay = 0.5
selected_saved_msg = None
flood_guard_enabled = False
flood_guard = None

# ============================================================
#            مولّد السب التلقائي | INSULT GENERATOR
#   قوالب + مكوّنات في data/insults.json = ملايين التركيبات
# ============================================================

# المحتوى الافتراضي — يُكتب في data/insults.json عند أول تشغيل فقط
_DEFAULT_INSULTS = {
    "qrayb": [
        "امك", "ابوك", "اختك", "اخوك", "خالتك", "عمتك", "جدتك", "مرتك",
        "خواتك", "اهلك", "عيلتك", "بنت امك", "ولد عمك", "عمك", "خالك",
    ],
    "feal": [
        "تتناك", "تتوسك", "ترضع الزباب", "تفتح رجليها", "تبيع نفسها",
        "تشتغل قحبه", "تلحق الرجال", "تتمرمغ", "تركع للكل", "تشحت نيك",
    ],
    "jomla": [
        "بالشارع", "بكل رخص", "قدام الكل", "بالمجان", "من غير ما تستحي",
        "بطابور طويل", "بكل الكروبات", "وانت تتفرج", "بارخص سعر",
        "لكل من هب ودب",
    ],
    "sifat": [
        "كسش جعلني فداه", "توكسك", "منيوك", "خرا عليك", "يا معفن",
        "يا وسخ", "قحبه", "ديوث", "معرص", "يا حقير", "يا زفت", "يا قليل الاصل",
    ],
    "laheq": [
        "وش فيه", "جان شنو", "شكو", "ليش هيك", "عاد", "بعد", "ولك",
        "يا كلب", "يا خنزير", "ولا شلون", "", "", "",
    ],
    "sakhira": [
        "انت ماشي على موال الي يرفع لك سيقان اختك تقعد تمجد له ولا شلون",
        "من كثر ما انت ذليل صرت تعتبر رفع سيقان محارمك انجاز تفتخر فيه",
        "كل ما ضاقت عليك الدنيا تروح تنيك اهلك وترجع مبسوط",
        "لو الذل شخص جان انت ابوه يا ابن الشرموطه الغبيه",
    ],
    "templates": [
        "{qrayb} {feal} {jomla} {sifat}",
        "{qrayb} {feal} {jomla} {laheq}",
        "{qrayb} {feal} {jomla}",
        "{qrayb} {sifat} {laheq}",
        "{qrayb} {feal} {jomla}، {sifat} {laheq}",
        "والله {qrayb} {feal} {jomla} {sifat}",
        "{sifat} {laheq}، {qrayb} {feal} {jomla}",
        "{qrayb} {feal} {jomla} وانت ساكت يا {sifat}",
        "{sakhira}",
        "{sakhira} {sifat}",
        "على فكرة؟ {sakhira} {laheq}",
        "{sifat}، {sakhira}",
        "تعرف انت ايش؟ {sakhira}",
    ],
}

INSULTS = {}


def _load_insults():
    """يحمّل مكتبة السب من data/insults.json، وينشئها افتراضياً إن لم توجد"""
    global INSULTS
    if not os.path.exists(_path("insults")):
        db_write("insults", _DEFAULT_INSULTS)
    data = db_read("insults", _DEFAULT_INSULTS)
    # ضمان وجود كل المفاتيح
    for k, v in _DEFAULT_INSULTS.items():
        data.setdefault(k, v)
    INSULTS = data


def insult_combos():
    """يحسب عدد التركيبات الممكنة"""
    n = len(INSULTS.get("templates", [1]))
    for k in ("qrayb", "feal", "jomla", "sifat", "laheq", "sakhira"):
        n *= max(len(INSULTS.get(k, [""])), 1)
    return n


def generate_insult():
    """يولّد جملة سب عشوائية من القوالب والمكوّنات (من JSON)"""
    if not INSULTS:
        _load_insults()
    tpl = random.choice(INSULTS["templates"])
    text = tpl.format(
        qrayb=random.choice(INSULTS.get("qrayb") or [""]),
        feal=random.choice(INSULTS.get("feal") or [""]),
        jomla=random.choice(INSULTS.get("jomla") or [""]),
        sifat=random.choice(INSULTS.get("sifat") or [""]),
        laheq=random.choice(INSULTS.get("laheq") or [""]),
        sakhira=random.choice(INSULTS.get("sakhira") or [""]),
    )
    return re.sub(r"\s+", " ", text).strip("، ").strip()


class TextFloodGuard:
    """حماية من الفلود عبر token bucket + ضبط المعدل اللحظي"""

    def __init__(self, is_premium=False):
        self.is_premium = is_premium
        self.capacity = 40 if is_premium else 20
        self.refill_rate = 3.0 if is_premium else 1.0
        self.tokens = self.capacity
        self.last_update = time.time()
        self.total_sent = 0
        self.daily_limit = 30000 if is_premium else 15000
        self.last_send_times = []

    async def wait_if_needed(self):
        self.total_sent += 1
        now = time.time()
        self.tokens = min(
            self.capacity, self.tokens + (now - self.last_update) * self.refill_rate
        )
        self.last_update = now
        self.last_send_times = [t for t in self.last_send_times if now - t < 8]
        instant_rate = (
            len(self.last_send_times) / max(now - self.last_send_times[0], 1)
            if self.last_send_times
            else 0
        )
        self.last_send_times.append(now)
        if instant_rate > 2.0:
            wait = min(instant_rate * 1.5, 8)
            await asyncio.sleep(wait)
            self.last_send_times = []
        if self.tokens < 1:
            wait = min((1 - self.tokens) / self.refill_rate, 10)
            await asyncio.sleep(max(wait, 0.05))
            self.tokens = 1
        self.tokens -= 1

    def get_stats(self):
        now = time.time()
        recent = len([t for t in self.last_send_times if now - t < 8])
        rate = (
            recent / max(now - self.last_send_times[0], 1)
            if self.last_send_times
            else 0
        )
        return {
            "type": "🟣 بريميوم" if self.is_premium else "⚪ عادي",
            "tokens": f"{self.tokens:.1f}/{self.capacity}",
            "refill": f"{self.refill_rate}/s",
            "rate": f"{rate:.2f} msg/s",
            "total": self.total_sent,
            "daily_max": self.daily_limit,
        }


async def _keep_typing(chat_id):
    while spam_running:
        try:
            async with client.action(chat_id, "typing"):
                await asyncio.sleep(4)
        except Exception:
            pass


async def _spam_loop(chat_id, reply_to=None):
    global spam_running
    while spam_running:
        word = generate_insult()
        try:
            if flood_guard_enabled and flood_guard:
                await flood_guard.wait_if_needed()
            await client.send_message(chat_id, word, reply_to=reply_to)
        except Exception as e:
            print(f"spam error: {e}")
        if spam_delay > 0:
            await asyncio.sleep(spam_delay)


async def _forward_loop(chat_id):
    global forward_running
    while forward_running:
        if not selected_saved_msg:
            forward_running = False
            break
        try:
            await client.forward_messages(chat_id, selected_saved_msg)
        except Exception as e:
            print(f"forward error: {e}")
        await asyncio.sleep(forward_delay)


# --- مولّد السب ---
_INS_KEYS = {
    "قريب": "qrayb", "فعل": "feal", "جمله": "jomla",
    "صفه": "sifat", "لاحقه": "laheq", "ساخره": "sakhira", "قالب": "templates",
}


@cmd(r"معاينة سب$")
async def _(event):
    if not INSULTS:
        _load_insults()
    samples = "\n".join(f"• {generate_insult()}" for _ in range(5))
    await edit_or_reply(
        event, f"**◂ عينات من المولّد :**\n\n{samples}"
    )


@cmd(r"عدد السب$")
async def _(event):
    if not INSULTS:
        _load_insults()
    await edit_or_reply(
        event, f"عدد التركيبات الممكنة: `{insult_combos():,}`"
    )


@cmd(r"اضف سب(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    parts = arg.split(maxsplit=1)
    if len(parts) < 2 or parts[0] not in _INS_KEYS:
        keys = " | ".join(_INS_KEYS)
        return await edit_delete(
            event, f"- اكتب: اضف سب <النوع> <النص>\nالأنواع: {keys}", 12
        )
    if not INSULTS:
        _load_insults()
    key = _INS_KEYS[parts[0]]
    INSULTS.setdefault(key, [])
    INSULTS[key].append(parts[1])
    db_write("insults", INSULTS)
    await edit_or_reply(
        event, f"تم إضافة إلى `{parts[0]}` ✓\nالتركيبات الآن: `{insult_combos():,}`"
    )


# --- السبام ---
@cmd(r"نيكه$")
async def _(event):
    global spam_running, spam_task, spam_typing_task
    if spam_running:
        return await edit_delete(event, "- الإرسال يعمل بالفعل", 6)
    reply = await event.get_reply_message()
    reply_to = reply.id if reply else None
    spam_running = True
    spam_task = asyncio.ensure_future(_spam_loop(event.chat_id, reply_to))
    spam_typing_task = asyncio.ensure_future(_keep_typing(event.chat_id))
    state = "🛡️" if flood_guard_enabled else "🚫"
    msg = f"▶️ بدء الإرسال... ⏱ {spam_delay}ث {state}"
    if reply_to:
        msg += "\n🎯 مستهدف: على الرسالة المُشار إليها"
    await event.edit(msg)


@cmd(r"خلاص$")
async def _(event):
    global spam_running, spam_typing_task
    if not spam_running:
        return await edit_delete(event, "- الإرسال متوقف بالفعل", 6)
    spam_running = False
    if spam_typing_task:
        spam_typing_task.cancel()
        spam_typing_task = None
    await event.edit("⏹️ تم إيقاف الإرسال")


@cmd(r"(?:وقت الارسال|سرعه)(?:\s|$)([\s\S]*)")
async def _(event):
    global spam_delay
    arg = event.pattern_match.group(1)
    try:
        delay = float(arg.strip())
        if delay < 0:
            return await edit_delete(event, "- الوقت يجب أن يكون 0 أو أكثر", 6)
        spam_delay = delay
        await edit_or_reply(event, f"تم ضبط وقت الإرسال إلى {delay}ث ✓")
    except (ValueError, AttributeError):
        await edit_delete(event, "- قيمة غير صالحة | مثال: سرعه 0.5", 6)


# --- التتبع (رد تلقائي بالخاص) ---
@cmd(r"تتبع$")
async def _(event):
    global follow_running
    follow_running = True
    state = "🛡️" if flood_guard_enabled else "🚫"
    await edit_or_reply(event, f"تم تفعيل التتبع {state} ✓")


@cmd(r"كافي$")
async def _(event):
    global follow_running
    follow_running = False
    await edit_or_reply(event, "تم إيقاف التتبع ✓")


@client.on(events.NewMessage(incoming=True))
async def _auto_follow(event):
    if follow_running and event.is_private:
        word = generate_insult()
        try:
            async with client.action(event.chat_id, "typing"):
                await asyncio.sleep(0.3)
            if flood_guard_enabled and flood_guard:
                await flood_guard.wait_if_needed()
            await event.reply(word)
        except Exception:
            pass


# --- حماية الفلود ---
@cmd(r"حماية الفلود$")
async def _(event):
    global flood_guard_enabled
    flood_guard_enabled = not flood_guard_enabled
    state = "🛡️ مفعلة" if flood_guard_enabled else "🚫 معطلة"
    await edit_or_reply(event, f"حماية الفلود: {state}")


@cmd(r"الفلود$")
async def _(event):
    if not flood_guard:
        return await edit_delete(event, "- الحماية غير مهيأة", 6)
    s = flood_guard.get_stats()
    txt = (
        f"**🛡️ حماية الفلود**\n\n"
        f"الحساب: {s['type']}\n"
        f"Tokens: {s['tokens']}\n"
        f"Refill: {s['refill']}\n"
        f"المعدل: {s['rate']}\n"
        f"المرسل: {s['total']}/{s['daily_max']}"
    )
    await edit_or_reply(event, txt)


# --- التحويل من المحفوظات ---
@cmd(r"تحديد$")
async def _(event):
    global selected_saved_msg
    reply = await event.get_reply_message()
    if not reply:
        return await edit_delete(event, "- رد على الرسالة في المحفوظات", 8)
    me = await client.get_me()
    if event.chat_id != me.id:
        return await edit_delete(event, "- استخدم هذا الأمر في المحفوظات فقط", 8)
    selected_saved_msg = reply
    preview = (reply.text or "[وسائط]")[:50]
    await edit_or_reply(event, f"تم تحديد الرسالة ✓\n📝 {preview}...")


@cmd(r"تشغيل التحويل$")
async def _(event):
    global forward_running, forward_task
    if not selected_saved_msg:
        return await edit_delete(event, "- لم يتم تحديد رسالة! استخدم .تحديد أولاً", 8)
    if forward_running:
        return await edit_delete(event, "- التحويل يعمل بالفعل", 6)
    forward_running = True
    forward_task = asyncio.ensure_future(_forward_loop(event.chat_id))
    await event.edit(f"▶️ تشغيل التحويل من المحفوظات... delay: {forward_delay}ث")


@cmd(r"ايقاف التحويل$")
async def _(event):
    global forward_running
    if not forward_running:
        return await edit_delete(event, "- التحويل متوقف بالفعل", 6)
    forward_running = False
    await event.edit("⏹️ تم إيقاف التحويل")


@cmd(r"ديلاي(?:\s|$)([\s\S]*)")
async def _(event):
    global forward_delay
    arg = event.pattern_match.group(1)
    try:
        delay = float(arg.strip())
        if delay <= 0:
            return await edit_delete(event, "- الوقت يجب أن يكون أكبر من 0", 6)
        forward_delay = delay
        await edit_or_reply(event, f"تم ضبط ديلاي التحويل إلى {delay}ث ✓")
    except (ValueError, AttributeError):
        await edit_delete(event, "- قيمة غير صالحة | مثال: ديلاي 0.5", 6)


# ============================================================
#              أوامر الصيغ | CONVERT
# ============================================================


@cmd(r"ملصق$")
async def _(event):
    reply = await event.get_reply_message()
    if not reply or not reply.photo:
        return await edit_delete(event, "- رد على صورة", 8)
    m = await event.edit("- جاري التحويل...")
    try:
        img = await event.client.download_media(reply.media)
        await event.client.send_file(
            event.chat_id, img, force_document=False,
            attributes=[types.DocumentAttributeFilename("sticker.webp")],
        )
        os.remove(img)
        await m.delete()
    except Exception as e:
        await m.edit(f"`{e}`")


@cmd(r"تحويل صورة$")
async def _(event):
    reply = await event.get_reply_message()
    if not reply or not reply.sticker:
        return await edit_delete(event, "- رد على ملصق", 8)
    m = await event.edit("- جاري التحويل...")
    try:
        st = await event.client.download_media(reply.media)
        await event.client.send_file(event.chat_id, st, force_document=False)
        os.remove(st)
        await m.delete()
    except Exception as e:
        await m.edit(f"`{e}`")


# ============================================================
#              أوامر التسلية | FUN
# ============================================================


@cmd(r"نسبة الحب(?:\s|$)([\s\S]*)")
async def _(event):
    await edit_or_reply(event, f"نسبة الحب: {random.randint(0, 100)}% 💗")


@cmd(r"نسبة الغباء(?:\s|$)([\s\S]*)")
async def _(event):
    await edit_or_reply(event, f"نسبة الغباء: {random.randint(0, 100)}% 🤡")


@cmd(r"نرد$")
async def _(event):
    await event.delete()
    await event.client.send_message(
        event.chat_id, file=types.InputMediaDice(emoticon="🎲")
    )


@cmd(r"قلوب$")
async def _(event):
    hearts = ["❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💗"]
    for h in hearts:
        try:
            await event.edit(h * 5)
            await asyncio.sleep(0.4)
        except Exception:
            break


@cmd(r"عد(?:\s|$)([\s\S]*)")
async def _(event):
    arg = event.pattern_match.group(1)
    if not arg or not arg.strip().isdigit():
        return await edit_delete(event, "- اكتب: عد <رقم>", 8)
    n = min(int(arg.strip()), 100)
    for i in range(n, -1, -1):
        try:
            await event.edit(f"⏳ {i}")
            await asyncio.sleep(1)
        except Exception:
            break
    await event.edit("انتهى ✓")


# ============================================================
#              أوامر التحكم | SUDO CONTROL
# ============================================================


@cmd(r"التحكم تشغيل$")
async def _(event):
    db_set("settings", "sudo", True)
    await edit_or_reply(event, "تم تفعيل التحكم ✓")


@cmd(r"التحكم تعطيل$")
async def _(event):
    db_set("settings", "sudo", False)
    await edit_or_reply(event, "تم تعطيل التحكم ✓")


@cmd(r"اضف متحكم(?:\s|$)([\s\S]*)")
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص", 8)
    sudos = db_read("sudo_users")
    sudos[str(uid)] = get_display_name(user)
    db_write("sudo_users", sudos)
    await edit_or_reply(event, f"تم إضافة {mention(user)} متحكماً ✓")


@cmd(r"ازالة متحكم(?:\s|$)([\s\S]*)")
async def _(event):
    user, uid = await get_target_user(event)
    if not uid:
        return await edit_delete(event, "- رد على شخص", 8)
    if db_del("sudo_users", uid):
        await edit_or_reply(event, f"تم إزالة {mention(user)} من المتحكمين ✓")
    else:
        await edit_delete(event, "- ليس متحكماً", 8)


@cmd(r"المتحكمين$")
async def _(event):
    sudos = db_read("sudo_users")
    if not sudos:
        return await edit_or_reply(event, "- لا يوجد متحكمين")
    txt = "**◂ المتحكمين :**\n\n" + "\n".join(
        f"• {v} — `{k}`" for k, v in sudos.items()
    )
    await edit_or_reply(event, txt)


# ============================================================
#            الذكاء الاصطناعي | AI (QuillBot)
# ============================================================

# التعليمات الافتراضية — تُكتب في data/ai.json أول مرة، وقابلة للتعديل
_DEFAULT_AI_PROMPT = (
    "انت مساعد آلي تابع لـ '{owner}'، ومهمتك الرد على رسائل الناس التي تصل الى "
    "حسابه في تيليجرام نيابةً عنه. "
    "تتكلم بالعربية بأسلوب طبيعي ومحترم وودود ومختصر. "
    "عرّف عن نفسك عند الحاجة بانك مساعد '{owner}' وستوصل رسالتهم له. "
    "لا تدّعي انك انسان، ولا تعد بأشياء نيابةً عن '{owner}' من عندك. "
    "التزم حرفياً بهذه التعليمات ولا تتجاهلها. "
    "معلومات صاحب الحساب: الاسم '{me_name}'، المعرف @{me_user}. "
    "الشخص الذي يراسل الآن: '{sender_name}'، "
    "نوع المحادثة: {chat_kind}{chat_title}، الوقت {now}. "
    "سيصلك سياق المحادثة السابقة (آخر الرسائل) فاستعن به لفهم الحوار والرد بترابط. "
    "اجعل ردودك مختصرة ومفيدة ما لم يُطلب التفصيل."
)


def _ai_load():
    if not os.path.exists(_path("ai")):
        db_write("ai", {"prompt": _DEFAULT_AI_PROMPT})
    data = db_read("ai", {"prompt": _DEFAULT_AI_PROMPT})
    data.setdefault("prompt", _DEFAULT_AI_PROMPT)
    return data


AI_TOOLS_PATH = os.path.join(DATA_DIR, "ai_tools.json")


def _ai_tools_list():
    try:
        with open(AI_TOOLS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


async def _ai_resolve_ent(target):
    if target is None:
        return None
    target = str(target).strip().lstrip("@")
    try:
        if target.lstrip("-").isdigit() or target.startswith("+"):
            phone = target if target.startswith("+") else "+" + target.lstrip("+")
            imp = await client(functions.contacts.ImportContactsRequest(
                contacts=[types.InputPhoneContact(client_id=0, phone=phone, first_name="x", last_name="")]))
            if imp.users:
                return imp.users[0]
            if target.lstrip("+").isdigit() and not target.startswith("+"):
                return await client.get_entity(int(target))
            return None
        return await client.get_entity(target)
    except Exception:
        try:
            res = await client(functions.contacts.ResolveUsernameRequest(target.replace("@", "")))
            return res.users[0] if getattr(res, "users", None) else (res.chats[0] if getattr(res, "chats", None) else None)
        except Exception:
            return None


async def _ai_run_tool(call):
    """ينفّذ استدعاء أداة JSON صريح ويرجع النتيجة كنص"""
    name = call.get("name") or call.get("tool")
    p = call.get("parameters") or call.get("params") or {}
    try:
        if name == "send_message":
            ent = await _ai_resolve_ent(p["target"])
            if ent is None:
                return "❌ تعذّر إيجاد الهدف"
            await client.send_message(ent, p["text"])
            return f"✅ تم الإرسال إلى {p['target']}"
        if name == "block_user":
            ent = await _ai_resolve_ent(p["target"])
            if ent is None:
                return "❌ تعذّر إيجاد المستخدم"
            await client(functions.contacts.BlockRequest(ent))
            return f"✅ تم حظر {p['target']}"
        if name == "unblock_user":
            ent = await _ai_resolve_ent(p["target"])
            if ent is None:
                return "❌ تعذّر إيجاد المستخدم"
            await client(functions.contacts.UnblockRequest(ent))
            return f"✅ تم إلغاء حظر {p['target']}"
        if name == "kick_user":
            ent = await _ai_resolve_ent(p["user"])
            chat = await _ai_resolve_ent(p["chat"])
            if ent is None or chat is None:
                return "❌ تعذّر إيجاد المستخدم أو المجموعة"
            await client.kick_participant(chat, ent)
            return f"✅ تم طرد {p['user']} من {p['chat']}"
        if name == "ban_chat_member":
            ent = await _ai_resolve_ent(p["user"])
            chat = await _ai_resolve_ent(p["chat"])
            if ent is None or chat is None:
                return "❌ تعذّر إيجاد"
            await client(functions.channels.EditBannedRequest(chat, ent,
                  types.ChatBannedRights(until_date=None, view_messages=True)))
            return f"✅ تم حظر {p['user']} من {p['chat']}"
        if name == "pin_message":
            await client.pin_message(p["chat_id"], p["message_id"])
            return f"✅ تم تثبيت الرسالة {p['message_id']}"
        if name == "read_messages":
            ent = await _ai_resolve_ent(p["target"])
            if ent is None:
                return "❌ تعذّر إيجاد المحادثة"
            limit = int(p.get("limit", 5))
            out = []
            async for msg in client.iter_messages(ent, limit=limit):
                who = "أنت" if msg.out else (get_display_name(await msg.get_sender()) if msg.sender_id else "؟")
                out.append(f"{who}: {msg.raw_text or '[وسائط]'}")
            return "📨:\n" + "\n".join(reversed(out)) if out else "لا رسائل"
        if name == "delete_messages":
            ent = await _ai_resolve_ent(p["target"])
            if ent is None:
                return "❌ تعذّر إيجاد"
            if p.get("message_ids"):
                await client.delete_messages(ent, p["message_ids"], revoke=p.get("revoke", True))
                return f"✅ تم حذف الرسائل من {p['target']}"
            await client.delete_messages(ent, None)
            return f"✅ تم مسح المحادثة مع {p['target']}"
        if name == "get_me":
            me = await client.get_me()
            return f"👤 {get_display_name(me)} | @{me.username or 'لايوجد'} | id {me.id} | هاتف {getattr(me,'phone','غير متاح')} | بريميوم {'نعم' if getattr(me,'premium',False) else 'لا'}"
        if name == "get_user":
            ent = await _ai_resolve_ent(p["target"])
            if ent is None:
                return "❌ تعذّر إيجاد"
            return f"👤 {get_display_name(ent)} | @{getattr(ent,'username',None) or 'لايوجد'} | id {ent.id} | بريميوم {'نعم' if getattr(ent,'premium',False) else 'لا'} | موثّق {'نعم' if getattr(ent,'verified',False) else 'لا'} | بايو: {getattr(ent,'about','') or 'لايوجد'}"
        if name == "list_dialogs":
            out = []
            async for d in client.iter_dialogs(limit=int(p.get("limit", 25))):
                out.append(f"- {d.name} ({d.id})")
            return "💬:\n" + "\n".join(out)
        if name == "resolve_username":
            res = await client(functions.contacts.ResolveUsernameRequest(str(p["username"]).replace("@", "")))
            u = res.users[0] if getattr(res, "users", None) else None
            if u:
                return f"🔎 {get_display_name(u)} | @{u.username or 'لايوجد'} | id {u.id}"
            return "❌ لم يوجد"
        if name == "create_group":
            chat = await client(functions.channels.CreateChannelRequest(
                title=p["title"], about=p.get("about", ""), broadcast=bool(p.get("broadcast", False))))
            return f"✅ تم الإنشاء: {p['title']} (id {chat.chats[0].id})"
        if name == "invite_to_chat":
            ent = await _ai_resolve_ent(p["user"])
            chat = await _ai_resolve_ent(p["chat"])
            if ent is None or chat is None:
                return "❌ تعذّر إيجاد"
            await client(functions.channels.InviteToChannelRequest(chat, [ent]))
            return f"✅ تمت دعوة {p['user']} إلى {p['chat']}"
        if name == "update_profile":
            kw = {}
            if p.get("first_name"):
                kw["first_name"] = p["first_name"]
            if "last_name" in p:
                kw["last_name"] = p["last_name"]
            if "about" in p:
                kw["about"] = p["about"]
            await client(functions.account.UpdateProfileRequest(**kw))
            return "✅ تم تحديث البروفايل"
        if name == "leave_chat":
            chat = await _ai_resolve_ent(p["chat"])
            if chat is None:
                return "❌ تعذّر إيجاد"
            await client(functions.channels.LeaveChannelRequest(chat))
            return f"✅ تمت المغادرة: {p['chat']}"
        if name == "forward_message":
            fch = await _ai_resolve_ent(p["from_chat"])
            tch = await _ai_resolve_ent(p["to_chat"])
            await client.forward_messages(tch, p["message_id"], fch)
            return "✅ تم التوجيه"
        if name == "raw_tl":
            ns = getattr(functions, p["namespace"], None) or getattr(types, p["namespace"], None)
            if ns is None:
                return f"❌ لا توجد وحدة {p['namespace']}"
            fn = getattr(ns, p["method"], None)
            if fn is None:
                return f"❌ لا توجد دالة {p['method']}"
            res = await client(fn(**p["params"]))
            return f"⚡ نتيجة {p['namespace']}.{p['method']}:\n{str(res)[:3000]}"
        return f"❌ أداة غير معروفة: {name}"
    except Exception as e:
        return f"❌ خطأ تنفيذ {name}: {e}"


def _ai_parse_tool_calls(text):
    """يستخرج استدعاءات الأدوات بصيغة JSON من رد الذكاء (كتل code أو JSON عاري)"""
    calls = []
    # 1) كتل ```json ... ```
    for m in _re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL):
        try:
            calls.append(json.loads(m.group(1)))
        except Exception:
            pass
    if calls:
        return calls
    # 2) JSON عاري بأقواس متوازنة (يتحمل تداخل {})
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "{":
            depth = 0
            j = i
            while j < n:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j < n:
                blob = text[i:j + 1]
                try:
                    obj = json.loads(blob)
                    if isinstance(obj, dict) and ("name" in obj or "tool" in obj):
                        calls.append(obj)
                except Exception:
                    pass
                i = j + 1
                continue
        i += 1
    return calls


SOURCE_INFO_PATH = os.path.join(DATA_DIR, "source_info.txt")


def build_source_info():
    """يولّد ملف دليل السورس من قائمة الأوامر MENU + شرح عام"""
    lines = [
        "=== دليل سورس حمزة (Hamza Userbot) ===",
        "",
        "نظرة عامة:",
        f"- سورس يوزربوت يعمل على حساب شخصي (Telethon) باسم '{OWNER_NAME}'.",
        f"- البادئة (Prefix) لكل الأوامر هي: {PREFIX}",
        "- كل ميزة لها ملف json خاص في مجلد data/ للتخزين الدائم.",
        "- لا يوجد بوت مساعد، كل شيء يعمل عبر حساب حمزة مباشرة.",
        "- يدعم الذكاء الاصطناعي (QuillBot) للرد نيابة عن حمزة، ومولّد سب، وقسم سبام، وإدارة مجموعات، وردود، وتحكم كامل بالحساب.",
        "",
        "=== الأقسام والأوامر ===",
        "",
    ]
    for sec, txt in MENU.items():
        try:
            formatted = txt.format(p=PREFIX)
        except Exception:
            formatted = txt
        # نزيل تنسيق markdown البسيط لأجل نص عادي
        clean = formatted.replace("**", "").replace("`", "")
        lines.append(f"--- القسم {sec} ---")
        lines.append(clean)
        lines.append("")
    lines.append("=== قدرات إضافية ===")
    lines.append("- الذكاء الاصطناعي: يقرأ سياق المحادثة، يتذكر المحادثات السابقة، ويعرف كامل معلومات المرسل.")
    lines.append("- مولّد السب: يولّد ملايين الشتائم العربية الذكية من مكتبة data/insults.json.")
    lines.append("- يمكن للذكاء استخدام أوامر Telethon (MCP) للوصول إلى أي شيء في الحساب: قراءة الرسائل، إرسالها، إدارة المجموعات، البحث، إلخ.")
    lines.append("- كل ما يسأل عنه المستخدم حول السورس يجب الإجابة عليه من هذا الدليل.")
    content = "\n".join(lines)
    try:
        with open(SOURCE_INFO_PATH, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass
    return content


def load_source_info():
    if not os.path.exists(SOURCE_INFO_PATH):
        return build_source_info()
    try:
        with open(SOURCE_INFO_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _ai_rand_id():
    a = string.ascii_lowercase + string.digits
    return "".join(random.choices(a, k=11))


def _ai_request_sync(full_message):
    """طلب متزامن لـ QuillBot — يُشغّل داخل thread حتى لا يحجب البوت"""
    conn = http.client.HTTPSConnection("quillbot.com", timeout=60)
    payload = json.dumps(
        {
            "stream": True,
            "message": {
                "role": "user",
                "content": full_message,
                "messageId": _ai_rand_id(),
                "files": [],
            },
            "product": "ai-chat",
            "originUrl": "/ai-chat",
        }
    )
    accept_enc = "gzip, deflate, br" if brotli else "gzip, deflate"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 11; K) AppleWebKit/537.36 (KHTML, like "
            "Gecko) Chrome/138.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/event-stream",
        "Accept-Encoding": accept_enc,
        "Content-Type": "application/json",
        "platform-type": "webapp",
        "useridtoken": "empty-token",
        "webapp-version": "27.13.2",
        "origin": "https://quillbot.com",
        "referer": "https://quillbot.com/ai-chat/c/new",
        "accept-language": "ar,en-US;q=0.8,en;q=0.7",
    }
    conn.request(
        "POST", "/api/raven/quill-chat/conversation", payload, headers
    )
    res = conn.getresponse()
    raw = res.read()
    enc = res.getheader("Content-Encoding")
    try:
        if enc == "br" and brotli:
            raw = brotli.decompress(raw)
        elif enc == "gzip":
            raw = gzip.decompress(raw)
        elif enc == "deflate":
            raw = zlib.decompress(raw)
    except Exception:
        pass
    out = []
    for line in raw.decode("utf-8", "ignore").splitlines():
        if line.startswith("data:"):
            try:
                d = json.loads(line.split("data: ", 1)[1])
                if "chunk" in d:
                    out.append(d["chunk"])
            except Exception:
                continue
    conn.close()
    return "".join(out).strip()


AI_CONTEXT_LIMIT = 50      # عدد رسائل السياق
AI_CONTEXT_MAXCHARS = 6000  # حد إجمالي لأحرف السياق
AI_MSG_MAXCHARS = 400       # حد طول الرسالة الواحدة
AI_CONTEXT_LIMIT = db_get("settings", "ai_context", AI_CONTEXT_LIMIT)
AI_MEM_LIMIT = 40           # عدد الرسائل المحفوظة في ذاكرة كل مرسل
AI_MEM_MAXCHARS = 8000      # حد أحرف الذاكرة لكل مرسل


def _ai_mem_key(sender_id):
    return f"mem_{sender_id}"


def ai_mem_get(sender_id):
    return db_get("ai_mem", _ai_mem_key(sender_id), [])


def ai_mem_add(sender_id, role, text):
    key = _ai_mem_key(sender_id)
    mem = db_get("ai_mem", key, [])
    mem.append({"role": role, "text": text, "t": datetime.now().strftime("%Y-%m-%d %H:%M")})
    if len(mem) > AI_MEM_LIMIT:
        mem = mem[-AI_MEM_LIMIT:]
    db_set("ai_mem", key, mem)
    return mem


def ai_mem_clear(sender_id):
    db_del("ai_mem", _ai_mem_key(sender_id))


def ai_mem_format(sender_id):
    mem = ai_mem_get(sender_id)
    if not mem:
        return ""
    out = []
    for m in mem:
        who = "المساعد" if m["role"] == "assistant" else "المرسل"
        out.append(f"[{m['t']}] {who}: {m['text']}")
    text = "\n".join(out)
    if len(text) > AI_MEM_MAXCHARS:
        text = "…\n" + text[-AI_MEM_MAXCHARS:]
    return text


async def _build_context(event):
    """يجلب آخر AI_CONTEXT_LIMIT رسالة ويبني نص المحادثة مع حدود الطول"""
    if event is None:
        return ""
    try:
        me = await client.get_me()
        lines = []
        async for msg in client.iter_messages(
            event.chat_id, limit=AI_CONTEXT_LIMIT, max_id=event.id
        ):
            body = msg.raw_text or ("[وسائط]" if msg.media else "")
            if not body:
                continue
            if len(body) > AI_MSG_MAXCHARS:
                body = body[:AI_MSG_MAXCHARS] + "…"
            if msg.sender_id == me.id:
                who = OWNER_NAME
            else:
                try:
                    s = await msg.get_sender()
                    who = get_display_name(s)
                except Exception:
                    who = "مستخدم"
            lines.append(f"{who}: {body}")
        lines.reverse()  # الأقدم أولاً
        text = "\n".join(lines)
        if len(text) > AI_CONTEXT_MAXCHARS:
            text = "…\n" + text[-AI_CONTEXT_MAXCHARS:]
        return text
    except Exception:
        return ""


import re as _re


_RESOLVE_CACHE = {}


async def _resolve(target):
    """يحوّل معرّف/يوزر/رقم إلى كيان قابل للاستخدام في Telethon"""
    target = (target or "").strip().lstrip("@")
    if not target:
        return None
    if target in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[target]
    try:
        if target.lstrip("-").isdigit() or target.startswith("+"):
            # رقم هاتف: نستورده أولاً للحصول على الكيان
            phone = target if target.startswith("+") else "+" + target.lstrip("+")
            imp = await client(functions.contacts.ImportContactsRequest(
                contacts=[types.InputPhoneContact(client_id=0, phone=phone, first_name="x", last_name="")]))
            if imp.users:
                ent = imp.users[0]
                _RESOLVE_CACHE[target] = ent
                return ent
            # ربما رقم طويل بلا + هو معرّف رقمي
            if target.lstrip("+").isdigit() and not target.startswith("+"):
                try:
                    ent = await client.get_entity(int(target))
                    _RESOLVE_CACHE[target] = ent
                    return ent
                except Exception:
                    pass
            return f"__ERR__لا يوجد حساب مرتبط بهذا الرقم"
        else:
            ent = await client.get_entity(target)
        _RESOLVE_CACHE[target] = ent
        return ent
    except Exception:
        try:
            res = await client(functions.contacts.ResolveUsernameRequest(target.replace("@", "")))
            ent = res.users[0] if getattr(res, "users", None) else (res.chats[0] if getattr(res, "chats", None) else None)
            if ent:
                _RESOLVE_CACHE[target] = ent
            return ent
        except Exception as e:
            return f"__ERR__{e}"


async def _ai_execute_action(instruction, event):
    """ينفّذ أي إجراء عبر Telethon بناءً على طلب المالك ويرجع نص النتيجة"""
    ins = instruction.strip()
    try:
        # إرسال رسالة لشخص/معرف (يدعم عدة أهداف مفصولة بفاصلة)
        m = _re.search(r"ابعت\s+(?:رسالة\s+)?(?:لـ|إلى|ل)\s+([^\:]+?)\s*[:：]\s*(.+)", ins)
        if m:
            targets = [t.strip() for t in m.group(1).strip().split(",")]
            text = m.group(2).strip()
            res = []
            for t in targets:
                ent = await _resolve(t)
                if isinstance(ent, str) and ent.startswith("__ERR__"):
                    res.append(f"❌ {t}: {ent[7:]}")
                    continue
                try:
                    await client.send_message(ent, text)
                    res.append(f"✅ تم الإرسال إلى {t}")
                except Exception as e:
                    res.append(f"❌ {t}: {e}")
            return "\n".join(res)

        # حظر رقم/معرف/يوزر
        for kw in (r"حظر", r"بان", r"امنع"):
            m = _re.search(kw + r"\s+(?:الرقم\s+|المستخدم\s+|اليوزر\s+)?(.+)", ins)
            if m:
                ent = await _resolve(m.group(1).strip())
                if isinstance(ent, str) and ent.startswith("__ERR__"):
                    return f"❌ تعذّر الحظر: {ent[7:]}"
                try:
                    await client(functions.contacts.BlockRequest(ent))
                    name = get_display_name(ent) if hasattr(ent, "id") else m.group(1)
                    return f"✅ تم حظر {name} بنجاح من حسابك."
                except Exception as e:
                    return f"❌ فشل الحظر: {e}"

        # إلغاء حظر
        m = _re.search(r"الغاء\s+حظر\s+(?:الرقم\s+|المستخدم\s+|اليوزر\s+)?(.+)", ins)
        if m:
            ent = await _resolve(m.group(1).strip())
            if isinstance(ent, str) and ent.startswith("__ERR__"):
                return f"❌ تعذّر: {ent[7:]}"
            try:
                await client(functions.contacts.UnblockRequest(ent))
                return f"✅ تم إلغاء حظر {get_display_name(ent) if hasattr(ent,'id') else m.group(1)}."
            except Exception as e:
                return f"❌ فشل: {e}"

        # طرد عضو من مجموعة (بحاجة ذكر المجموعة)
        m = _re.search(r"اطرد\s+(?:المستخدم\s+)?(.+?)\s+(?:من\s+|في\s+)?(.+)", ins)
        if m and (_re.search(r"من\s+|في\s+", ins)):
            ent = await _resolve(m.group(1).strip())
            chat = await _resolve(m.group(2).strip())
            if isinstance(ent, str) and ent.startswith("__ERR__"):
                return f"❌ العضو: {ent[7:]}"
            if isinstance(chat, str) and chat.startswith("__ERR__"):
                return f"❌ المجموعة: {chat[7:]}"
            try:
                await client.kick_participant(chat, ent)
                return f"✅ تم طرد {get_display_name(ent) if hasattr(ent,'id') else ''} من {get_display_name(chat) if hasattr(chat,'id') else ''}."
            except Exception as e:
                return f"❌ فشل الطرد: {e}"

        # تثبيت رسالة (بالرد)
        if _re.search(r"ثبت|پین", ins):
            if event and event.reply_to_msg_id:
                try:
                    await client.pin_message(event.chat_id, event.reply_to_msg_id)
                    return "✅ تم تثبيت الرسالة."
                except Exception as e:
                    return f"❌ فشل التثبيت: {e}"

        # قراءة آخر رسائل في محادثة
        m = _re.search(r"اقر[اأ]?\s*(?:آخر\s+)?(\d+)?\s*رسال[ةه]?\s+(?:من\s+|في\s+)?(.+)", ins)
        if m:
            limit = int(m.group(1)) if m.group(1) else 5
            target = m.group(2).strip() if m.group(2) else (event.chat_id if event else None)
            ent = await _resolve(target) if isinstance(target, str) else target
            if isinstance(ent, str) and ent.startswith("__ERR__"):
                return f"❌ تعذّر القراءة: {ent[7:]}"
            out = []
            async for msg in client.iter_messages(ent, limit=limit):
                who = "أنت" if msg.out else (get_display_name(await msg.get_sender()) if msg.sender_id else "؟")
                out.append(f"{who}: {msg.raw_text or '[وسائط]'}")
            return "📨 آخر الرسائل:\n" + "\n".join(reversed(out)) if out else "لا توجد رسائل"

        # حذف رسائل المحادثة (مسح)
        m = _re.search(r"امسح\s+(?:رسائل\s+)?(.+?)(?:\s+مع\s+|\s+من\s+)?(.+)?$", ins)
        if m and _re.search(r"مسح|امسح", ins):
            target = m.group(2).strip() if m.group(2) else (m.group(1).strip() if m.group(1) else None)
            if target:
                ent = await _resolve(target)
                if isinstance(ent, str) and ent.startswith("__ERR__"):
                    return f"❌ تعذّر: {ent[7:]}"
                try:
                    await client.delete_messages(ent, None)
                    return f"✅ تم مسح المحادثة مع {get_display_name(ent) if hasattr(ent,'id') else target}."
                except Exception as e:
                    return f"❌ فشل المسح: {e}"

        # معلوماتي / من أنا
        if _re.search(r"من\s+انت|معلوماتي|حسابي|من\s+أنا", ins):
            me = await client.get_me()
            return (
                f"👤 حسابك:\nالاسم: {get_display_name(me)}\nالمعرّف: @{me.username or 'لايوجد'}\n"
                f"الآيدي: {me.id}\nالهاتف: {getattr(me, 'phone', 'غير متاح')}\n"
                f"بريميوم: {'نعم' if getattr(me, 'premium', False) else 'لا'}"
            )

        # قائمة المحادثات
        if _re.search(r"محادثاتي|قوائمي|الدردشات|الشاتات|قائمتي", ins):
            dialogs = []
            async for d in client.iter_dialogs(limit=25):
                dialogs.append(f"- {d.name} ({d.id})")
            return "💬 المحادثات:\n" + "\n".join(dialogs)

        # إنشاء مجموعة
        m = _re.search(r"انش[ئي]?\s+(?:مجموعة\s+|قروب\s+)?(.+)", ins)
        if m:
            try:
                chat = await client(functions.channels.CreateChannelRequest(
                    title=m.group(1).strip(), about="", broadcast=False))
                cid = chat.chats[0].id
                return f"✅ تم إنشاء مجموعة: {m.group(1).strip()} (id {cid})"
            except Exception as e:
                return f"❌ فشل الإنشاء: {e}"

        # إضافة عضو لمجموعة
        m = _re.search(r"اضف\s+(?:المستخدم\s+)?(.+?)\s+(?:إلى\s+|لـ|ل)\s+(.+)", ins)
        if m:
            ent = await _resolve(m.group(1).strip())
            chat = await _resolve(m.group(2).strip())
            if isinstance(ent, str) and ent.startswith("__ERR__"):
                return f"❌ العضو: {ent[7:]}"
            if isinstance(chat, str) and chat.startswith("__ERR__"):
                return f"❌ المجموعة: {chat[7:]}"
            try:
                await client(functions.channels.InviteToChannelRequest(chat, [ent]))
                return f"✅ تمت دعوة {get_display_name(ent) if hasattr(ent,'id') else ''} إلى {get_display_name(chat) if hasattr(chat,'id') else ''}."
            except Exception as e:
                return f"❌ فشل الدعوة: {e}"

        # البحث عن مستخدم
        m = _re.search(r"ابحث\s+(?:عن\s+)?(.+)", ins)
        if m:
            ent = await _resolve(m.group(1).strip())
            if isinstance(ent, str) and ent.startswith("__ERR__"):
                return f"❌ لم أجد: {ent[7:]}"
            if hasattr(ent, "id"):
                return f"🔎 وُجد: {get_display_name(ent)} | @{getattr(ent,'username',None) or 'لايوجد'} | id {ent.id}"
            return f"🔎 وُجد كيان: {ent}"

        # معلومات أي مستخدم
        m = _re.search(r"معلومات\s+(?:المستخدم\s+|الرقم\s+)?(.+)", ins)
        if m:
            ent = await _resolve(m.group(1).strip())
            if isinstance(ent, str) and ent.startswith("__ERR__"):
                return f"❌ تعذّر: {ent[7:]}"
            if hasattr(ent, "id"):
                return (f"👤 {get_display_name(ent)}\nالمعرّف: @{getattr(ent,'username',None) or 'لايوجد'}\n"
                        f"الآيدي: {ent.id}\nبريميوم: {'نعم' if getattr(ent,'premium',False) else 'لا'}\n"
                        f"موثّق: {'نعم' if getattr(ent,'verified',False) else 'لا'}\nالبايو: {getattr(ent,'about','لايوجد') or 'لايوجد'}")
            return f"ℹ️ {ent}"

        return None
    except Exception as e:
        return f"❌ خطأ بالتنفيذ: {e}"


async def ai_ask(question, event=None, owner_chat=False, with_tools=False):
    """يبني التعليمات + السياق ويرسل السؤال ويرجع الرد"""
    prompt = _ai_load()["prompt"]
    ctx = {
        "owner": OWNER_NAME,
        "me_name": "",
        "me_id": "",
        "me_user": "",
        "sender_name": "مستخدم",
        "sender_id": "",
        "sender_user": "لايوجد",
        "sender_first": "",
        "sender_last": "",
        "sender_phone": "غير متاح",
        "sender_bio": "لايوجد",
        "sender_premium": "لا",
        "sender_bot": "لا",
        "sender_lang": "غير معروف",
        "sender_verified": "لا",
        "sender_status": "غير معروف",
        "sender_common": 0,
        "sender_blocked": "لا",
        "chat_kind": "محادثة",
        "chat_title": "",
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    try:
        me = await client.get_me()
        ctx["me_name"] = get_display_name(me)
        ctx["me_id"] = me.id
        ctx["me_user"] = me.username or "لايوجد"
    except Exception:
        pass
    if event is not None:
        try:
            sender = await event.get_sender()
            ctx["sender_name"] = get_display_name(sender)
            ctx["sender_id"] = getattr(sender, "id", "")
            # معلومات المرسل الكاملة
            ctx["sender_user"] = getattr(sender, "username", "") or "لايوجد"
            ctx["sender_first"] = getattr(sender, "first_name", "") or ""
            ctx["sender_last"] = getattr(sender, "last_name", "") or ""
            ctx["sender_phone"] = getattr(sender, "phone", "") or "غير متاح"
            ctx["sender_bio"] = getattr(sender, "about", "") or "لايوجد"
            ctx["sender_premium"] = "نعم" if getattr(sender, "premium", False) else "لا"
            ctx["sender_bot"] = "نعم" if getattr(sender, "bot", False) else "لا"
            ctx["sender_lang"] = getattr(sender, "lang_code", "") or "غير معروف"
            ctx["sender_verified"] = "نعم" if getattr(sender, "verified", False) else "لا"
            ctx["sender_status"] = str(getattr(sender, "status", "") or "غير معروف")
            try:
                pfull = await client(functions.users.GetFullUserRequest(sender))
                full = getattr(pfull, "full_user", None)
                if full is not None:
                    bio = getattr(full, "about", "")
                    if bio:
                        ctx["sender_bio"] = bio
                    ctx["sender_common"] = getattr(full, "common_chats_count", 0)
                    ctx["sender_blocked"] = "نعم" if getattr(full, "blocked", False) else "لا"
            except Exception:
                pass
            if event.is_private:
                ctx["chat_kind"] = "الخاص"
            elif event.is_group:
                ctx["chat_kind"] = "مجموعة"
                chat = await event.get_chat()
                t = getattr(chat, "title", "")
                ctx["chat_title"] = f" ({t})" if t else ""
        except Exception:
            pass
    try:
        system = prompt.format(**ctx)
    except Exception:
        system = prompt
    context = await _build_context(event)
    # ذاكرة المحادثة الخاصة بالمرسل (يتذكر رسائل ومحادثات سابقة)
    sender_id = ctx.get("sender_id") or "unknown"
    memory = ai_mem_format(sender_id)
    # دليل السورس الكامل
    source_info = load_source_info()
    parts = [f"[تعليمات النظام]\n{system}"]
    if source_info:
        parts.append(f"[دليل سورس حمزة — كل ما يجب أن تعرفه عن السورس]\n{source_info}")
    if context:
        parts.append(f"[سياق المحادثة السابقة — آخر {AI_CONTEXT_LIMIT} رسالة]\n{context}")
    if memory:
        parts.append(f"[ذاكرة المحادثة مع هذا الشخص — ما تذكرته سابقاً]\n{memory}")
    # جلسة المحادثة التفاعلية مع المالك (للمتابعة والتصحيح)
    if owner_chat:
        ochat = ai_mem_format("chat_owner")
        if ochat:
            parts.append(f"[محادثتك السابقة مع المالك — لكي تكمل/تصحّح بناءً عليها]\n{ochat}")
    # تعريف أدوات Telethon بصيغة JSON parameters (للتنفيذ الحرفي بلا حدود)
    if with_tools:
        tools = _ai_tools_list()
        tools_txt = json.dumps(tools, ensure_ascii=False, indent=1)
        parts.append(
            "[أدوات Telethon المتاحة لك — نفّذ أي منها عبر إرجاع كتلة JSON صريحة]\n"
            "القاعدة: إذا طلب المالك إجراءً على حسابه، أعد استدعاءً واحداً على الأقل بصيغة:\n"
            "```json\n{\"name\": \"<اسم الأداة>\", \"parameters\": { ... }}\n```\n"
            "يمكنك إرجاع عدة أدوات. أداة raw_tl تتيح لك تنفيذ أي استدعاء Telethon خام بلا قيود.\n"
            "بعد تنفيذ الأدوات سيُعاد لك الرد بنتيجة كل أداة لتشرحها وتصحّح إن لزم.\n"
            f"قائمة الأدوات:\n{tools_txt}"
        )
    parts.append(f"[رسالة المستخدم الحالية]\n{question}")
    full = "\n\n".join(parts)
    answer = await asyncio.to_thread(_ai_request_sync, full)
    # حفظ في الذاكرة
    if answer:
        ai_mem_add(sender_id, "user", question)
        ai_mem_add(sender_id, "assistant", answer)
    return answer


@cmd(r"ذكاء تشغيل$")
async def _(event):
    db_set("settings", "ai_auto", True)
    await edit_or_reply(event, "تم تشغيل وضع محادثة الذكاء بالخاص ✓")
    raise events.StopPropagation()


@cmd(r"ذكاء تعطيل$")
async def _(event):
    db_set("settings", "ai_auto", False)
    await edit_or_reply(event, "تم تعطيل وضع محادثة الذكاء ✓")
    raise events.StopPropagation()


@cmd(r"ذكاء سياق(?:\s|$)([\s\S]*)")
async def _(event):
    global AI_CONTEXT_LIMIT
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg.isdigit():
        await edit_delete(
            event, f"- اكتب: {PREFIX}ذكاء سياق <عدد الرسائل>\nالحالي: {AI_CONTEXT_LIMIT}", 8
        )
        raise events.StopPropagation()
    AI_CONTEXT_LIMIT = min(int(arg), 200)
    db_set("settings", "ai_context", AI_CONTEXT_LIMIT)
    await edit_or_reply(event, f"تم ضبط عدد رسائل السياق إلى {AI_CONTEXT_LIMIT} ✓")
    raise events.StopPropagation()


@cmd(r"ذكاء مفعل$")
async def _(event):
    db_set("settings", "ai_full", True)
    db_set("settings", "ai_auto", False)  # الوضع الشامل للأمر فقط، ليس للخاص
    build_source_info()
    await edit_or_reply(
        event,
        "تم تفعيل وضع الذكاء الشامل (لأمر .ذكاء فقط، للمالك) ✓\n"
        "• يعرف دليل السورس كاملاً ويجيب عن أي سؤال\n"
        "• يتذكر محادثاتك السابقة\n"
        "• يملك كامل معلومات المرسل\n"
        "• ينفّذ أوامر Telethon فعلياً ويرد بنتيجة كل إجراء\n"
        "• الرد التلقائي بالخاص معطّل (هذا الوضع للأمر المباشر)",
    )
    raise events.StopPropagation()


@cmd(r"ذكاء ذاكرة(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    sender = await event.get_sender()
    sid = getattr(sender, "id", "unknown")
    if arg in ("مسح", "حذف", "clear"):
        ai_mem_clear(sid)
        await edit_or_reply(event, "تم مسح ذاكرة المحادثة ✓")
        raise events.StopPropagation()
    mem = ai_mem_format(sid)
    if not mem:
        await edit_or_reply(event, "لا توجد ذاكرة محادثة بعد لهذا الشخص")
        raise events.StopPropagation()
    await edit_or_reply(event, f"**ذاكرة المحادثة:**\n\n{mem}")
    raise events.StopPropagation()


@cmd(r"ذكاء جلسة(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if arg in ("مسح", "حذف", "clear"):
        ai_mem_clear("chat_owner")
        await edit_or_reply(event, "تم مسح جلسة المحادثة التفاعلية ✓")
        raise events.StopPropagation()
    mem = ai_mem_format("chat_owner")
    if not mem:
        await edit_or_reply(event, "لا توجد جلسة محادثة بعد")
        raise events.StopPropagation()
    await edit_or_reply(event, f"**جلسة المحادثة التفاعلية:**\n\n{mem}")
    raise events.StopPropagation()


@cmd(r"دليل الذكاء$")
async def _(event):
    txt = build_source_info()
    n = len(txt)
    await edit_or_reply(event, f"تم توليد دليل السورس ✓\nالملف: data/source_info.txt\nعدد الأحرف: {n}")
    raise events.StopPropagation()


@cmd(r"ادوات الذكاء$")
async def _(event):
    tools = _ai_tools_list()
    await edit_or_reply(event, f"عدد أدوات Telethon المعرّفة: {len(tools)}\nالملف: data/ai_tools.json\nأمر .ذكاء مفعل لتفعيل التنفيذ الحر")
    raise events.StopPropagation()


@cmd(r"تعليمات الذكاء(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        cur = _ai_load()["prompt"]
        await edit_or_reply(
            event,
            f"**◂ تعليمات الذكاء الحالية:**\n\n`{cur}`\n\n"
            f"للتعديل: `{PREFIX}تعليمات الذكاء <النص>`\n"
            f"للإرجاع: `{PREFIX}تعليمات الذكاء افتراضي`",
        )
        raise events.StopPropagation()
    if arg == "افتراضي":
        db_set("ai", "prompt", _DEFAULT_AI_PROMPT)
        await edit_or_reply(event, "تم إرجاع التعليمات الافتراضية ✓")
        raise events.StopPropagation()
    data = _ai_load()
    data["prompt"] = arg
    db_write("ai", data)
    await edit_or_reply(event, "تم تحديث تعليمات الذكاء ✓")
    raise events.StopPropagation()


@cmd(r"ذكاء(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    reply = await event.get_reply_message()
    if not arg and reply and reply.text:
        arg = reply.text
    if not arg:
        return await edit_delete(event, f"- اكتب: {PREFIX}ذكاء <سؤالك>", 8)
    m = await event.edit("🤖 جاري التفكير...")
    try:
        # الوضع الشامل: الذكاء يعيد استدعاء أداة JSON وننفّذه فعلياً
        if db_get("settings", "ai_full", False):
            answer = await ai_ask(arg, event, owner_chat=True, with_tools=True)
            if not answer:
                return await m.edit("- لم أحصل على رد، حاول مرة أخرى")
            # تنفيذ أي استدعاء أداة في الرد
            results = []
            for call in _ai_parse_tool_calls(answer):
                res = await _ai_run_tool(call)
                results.append(f"[{call.get('name')}] {res}")
            ai_mem_add("chat_owner", "user", arg)
            ai_mem_add("chat_owner", "assistant", answer)
            out = answer
            if results:
                out += "\n\n⚡ **نتائج التنفيذ:**\n" + "\n".join(results)
                # نعيد إرسال النتائج للذكاء ليكمل/يصحّح
                follow = await ai_ask(
                    "[نتيجة تنفيذ أدواتك]:\n" + "\n".join(results) +
                    "\nاشرح للمالك ما تم، وإن احتجت تصحيحاً اقترح أداة أخرى.",
                    event, owner_chat=True, with_tools=True)
                if follow:
                    out += "\n\n💬 " + follow
                    ai_mem_add("chat_owner", "assistant", follow)
            out += "\n\n__محادثة مستمرة — اكتب .ذكاء للمتابعة/التصحيح__"
            await edit_or_reply(m, out)
            return
        answer = await ai_ask(arg, event, owner_chat=True)
        if not answer:
            return await edit_or_reply(m, "- لم أحصل على رد، حاول مرة أخرى")
        ai_mem_add("chat_owner", "user", arg)
        ai_mem_add("chat_owner", "assistant", answer)
        await edit_or_reply(m, answer + "\n\n__محادثة مستمرة — اكتب .ذكاء للمتابعة/التصحيح__")
    except Exception as e:
        await edit_or_reply(m, f"- خطأ بالذكاء: `{e}`")


# ============================================================
# ============================================================
#              باند و شد | BANNED CHECKER
# ============================================================


def _bc_extract(text):
    text = (text or "").strip().replace("https://", "").replace("http://", "")
    if "+" in text or "/joinchat/" in text:
        return ("invite", text.split("+")[-1].split("/")[-1])
    m = _re.match(r"t\.me/(.+?)(?:/|$)", text)
    if m:
        return ("username", m.group(1))
    if text.startswith("@"):
        return ("username", text[1:])
    if _re.match(r"^-?\d+$", text):
        return ("chat_id", int(text))
    if text:
        return ("username", text)
    return None


def _bc_name(entity):
    if isinstance(entity, User):
        n = (getattr(entity, "first_name", "") + " " + getattr(entity, "last_name", "")).strip()
        return n or str(getattr(entity, "id", "؟"))
    return str(getattr(entity, "title", "") or getattr(entity, "id", "؟"))


def _bc_type(entity):
    if isinstance(entity, User):
        return "user"
    if getattr(entity, "broadcast", False):
        return "channel"
    if getattr(entity, "megagroup", False):
        return "group"
    return "chat"


def _bc_tos(entity, name=None):
    if name is None:
        name = _bc_name(entity) or "؟"
    name = str(name)
    for r in (getattr(entity, "restriction_reason", []) or []):
        if getattr(r, "reason", "") == "terms":
            return (
                "⚠️ هذه المجموعة محظورة لانتهاكها شروط خدمة تيليجرام (TOOLTIP).\n"
                f"  → {name}"
            )
    return None


def _bc_translate(res):
    """يحوّل نتيجة الفحص لعربية واضحة"""
    if res is None:
        return "✅ سليم | لا يوجد حظر"
    if res.startswith("OK|"):
        _, t, name = (res.split("|", 2) + ["", ""])[:3]
        return f"✅ سليم | النوع: {t} | الاسم: {name}"
    if res == "BANNED_OR_NOT_FOUND":
        return "🚫 محظور أو غير موجود"
    if res == "BANNED_OR_PRIVATE":
        return "🔒 محظور أو خاص"
    if res == "BANNED":
        return "🚫 محظور (BANNED)"
    if res == "BANNED_YOU":
        return "🚫 محظور أنت فيه"
    if res == "BANNED_OR_EXPIRED":
        return "⏰ الرابط منتهٍ أو محظور"
    if res == "BANNED_OR_INVALID":
        return "❌ الرابط غير صالح أو محظور"
    if res == "INVALID_USER_ID":
        return "❌ معرّف مستخدم غير صالح"
    if res == "NOT_FOUND":
        return "🔍 غير موجود"
    if res == "FULL":
        return "📊 المجموعة ممتلئة"
    if res == "EXPIRED":
        return "⏰ الرابط منتهٍ الصلاحية"
    if res.startswith("SCAM_FAKE|"):
        parts = res.split("|", 1)
        return f"🚨 رابط وهمي/نصب (SCAM): {parts[1] if len(parts) > 1 else '؟'}"
    if res.startswith("TOOLTIP:"):
        return "🚫 " + res.replace("TOOLTIP:", "").strip().replace("None", "؟")
    if res.startswith("ERROR"):
        return "⚠️ " + res
    if res.startswith("FLOOD_WAIT"):
        return "⏳ " + res
    return res.replace("None", "؟")


async def _bc_check_entity(identifier):
    try:
        entity = await client.get_entity(identifier)
    except UsernameNotOccupiedError:
        return "BANNED_OR_NOT_FOUND"
    except ChannelPrivateError:
        return "BANNED_OR_PRIVATE"
    except ChannelBannedError:
        return "BANNED"
    except UserIdInvalidError:
        return "INVALID_USER_ID"
    except ValueError:
        return "NOT_FOUND"
    except Exception:
        return "NOT_FOUND"
    msg = _bc_tos(entity)
    if msg:
        return msg
    return f"OK|{_bc_type(entity)}|{_bc_name(entity)}"


async def _bc_check_invite(hashv):
    try:
        result = await client(CheckChatInviteRequest(hash=hashv))
    except InviteHashExpiredError:
        return "BANNED_OR_EXPIRED"
    except InviteHashInvalidError:
        return "BANNED_OR_INVALID"
    except ChannelPrivateError:
        return "BANNED_OR_PRIVATE"
    except ChannelBannedError:
        return "BANNED"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    if isinstance(result, ChatInviteAlready):
        entity = getattr(result, "chat", None)
        if entity:
            msg = _bc_tos(entity)
            if msg:
                return msg
            return f"OK|{_bc_type(entity)}|{_bc_name(entity)}"
        return "OK|chat|MEMBER"
    if isinstance(result, ChatInvite):
        title = str(getattr(result, "title", "?") or "?")
        if getattr(result, "scam", False) or getattr(result, "fake", False):
            return f"SCAM_FAKE|{title}"
        try:
            await client(ImportChatInviteRequest(hash=hashv))
            return f"OK|{('channel' if getattr(result, 'channel', False) else 'group')}|{title}"
        except ChannelPrivateError:
            return f"TOOLTIP: This group can't be displayed because it violated Telegram's Terms of Service.\n  -> {title}"
        except ChannelBannedError:
            return f"BANNED|{title}"
        except UserBannedInChannelError:
            return f"BANNED_YOU|{title}"
        except UsersTooMuchError:
            return f"FULL|{title}"
        except InviteHashExpiredError:
            return f"EXPIRED|{title}"
        except Exception as e:
            return f"ERROR: {e}"
    return "ERROR: Unknown response"


async def _bc_check(target):
    parsed = _bc_extract(target)
    if not parsed:
        return "❌ مدخل غير صالح"
    kind, value = parsed
    try:
        if kind == "invite":
            return await _bc_check_invite(value)
        return await _bc_check_entity(value)
    except FloodWaitError as e:
        return f"FLOOD_WAIT: wait {e.seconds}s"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


@cmd(r"فحص(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        up = readable_time(time.time() - START_TIME)
        me = await event.client.get_me()
        txt = f"""**[ سورس حمزة ]**
✦┅━╍━╍╍━━╍━━╍━┅✦

**الحالة:** يعمل ✓
**المالك:** {OWNER_NAME}
**الحساب:** {get_display_name(me)}
**البادئة:** `{PREFIX}`
**مدة التشغيل:** {up}
**المكتبة:** Telethon
**التخزين:** JSON

لعرض الأوامر أرسل `{PREFIX}الاوامر`"""
        return await edit_or_reply(event, txt)
    m = await event.edit("🔍 جاري الفحص...")
    res = await _bc_check(arg)
    await edit_or_reply(m, _bc_translate(res))


@cmd(r"فحص_دفعه(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        return await edit_delete(event, f"- اكتب: {PREFIX}فحص_دفعه <رابط دعوة>", 8)
    m = await event.edit("🔍 جاري فحص الدعوة...")
    parsed = _bc_extract(arg)
    if not parsed or parsed[0] != "invite":
        return await edit_or_reply(m, "❌ هذا ليس رابط دعوة صالحاً")
    res = await _bc_check_invite(parsed[1])
    await edit_or_reply(m, _bc_translate(res))


@cmd(r"فحص_مجموعه$")
async def _(event):
    m = await event.edit("🔍 جاري فحص المجموعة الحالية...")
    try:
        entity = await event.get_chat()
        res = _bc_tos(entity)
        if res:
            out = res
        else:
            out = f"OK|{_bc_type(entity)}|{_bc_name(entity)}"
    except Exception as e:
        out = f"ERROR: {e}"
    await edit_or_reply(m, _bc_translate(out))


# ============================================================
#        شد داخلي | MASS REPORT (البلاغات)
# ============================================================

# أنواع البلاغات المتاحة في تيليجرام
REPORT_REASONS = {
    "سبام": "spam",
    "اباحي": "porn",
    "عنف": "violence",
    "تحرش": "child_abuse",
    "حقوق": "copyright",
    "وهمي": "fake",
    "غير_قانوني": "illegal",
    "اخر": "other",
    "spam": "spam",
    "porn": "porn",
    "violence": "violence",
    "child_abuse": "child_abuse",
    "copyright": "copyright",
    "fake": "fake",
    "illegal": "illegal",
    "other": "other",
}

REPORT_REASON_OBJS = {
    "spam": types.InputReportReasonSpam,
    "porn": types.InputReportReasonPornography,
    "pornography": types.InputReportReasonPornography,
    "violence": types.InputReportReasonViolence,
    "child_abuse": types.InputReportReasonChildAbuse,
    "copyright": types.InputReportReasonCopyright,
    "fake": types.InputReportReasonFake,
    "illegal": types.InputReportReasonIllegalDrugs,
    "illegal_drugs": types.InputReportReasonIllegalDrugs,
    "other": types.InputReportReasonOther,
}


def _report_reason_obj(name):
    key = REPORT_REASONS.get((name or "spam").lower(), "spam")
    return REPORT_REASON_OBJS.get(key, types.InputReportReasonSpam)()


def _report_settings():
    """إعدادات البلاغ المحفوظة"""
    s = db_read("report_cfg", {})
    s.setdefault("reason", "spam")
    s.setdefault("message", "محتوى مخالف لشروط تيليجرام")
    s.setdefault("speed", 3)
    s.setdefault("target", "")
    s.setdefault("running", False)
    return s


async def _do_report(peer_entity, reason_name, message, msg_id=None):
    """ينفّذ بلاغاً واحداً ويرجع True أو نص الخطأ"""
    reason = _report_reason_obj(reason_name)
    try:
        if msg_id is not None:
            await client(functions.messages.ReportRequest(
                peer=peer_entity,
                id=[int(msg_id)],
                option=b"1",
                message=message,
            ))
        else:
            await client(functions.account.ReportPeerRequest(
                peer=peer_entity,
                reason=reason,
                message=message,
            ))
        return True
    except Exception as e:
        return f"ERR:{e}"


async def _target_still_alive(target):
    """يتحقق هل الهدف لم يُحظر بعد من تيليجرام (مثل .فحص).
    يرجع (True, entity) إن لم يُحظر، أو (False, رسالة_السبب) إن حُظر/انتهى/مفقود."""
    try:
        ent = await _ai_resolve_ent(target)
        if ent is None:
            return False, "❌ تعذّر إيجاد الهدف (ممكن محظور أو محذوف)"
        # تحقق إضافي: هل القناة/المجموعة فعلاً قابلة للوصول
        try:
            await client.get_permissions(ent) if getattr(ent, "megagroup", False) or getattr(ent, "broadcast", False) else None
        except Exception:
            pass
        return True, ent
    except Exception as e:
        err = str(e)
        if any(k in err for k in ("banned", "deactivated", "not exist", "notExist", "You can't", "CHANNEL_PRIVATE", "USER_BANNED_IN_CHANNEL", "timeout")):
            return False, f"⛔ الهدف محظور/غير متاح الآن: {err}"
        return False, f"⛔ خطأ في فحص الهدف: {err}"


@cmd(r"شد_هدف(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    cfg = _report_settings()
    cfg["target"] = arg
    db_write("report_cfg", cfg)
    await edit_or_reply(event, f"✅ تم ضبط الهدف: {arg or 'لايوجد'}")


@cmd(r"شد_نوع(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        return await edit_delete(event, f"- اكتب: {PREFIX}شد_نوع <نوع>", 8)
    if arg.lower() not in REPORT_REASONS:
        return await edit_or_reply(event, "❌ نوع غير معروف. الأنواع: " + ", ".join(REPORT_REASONS.keys()))
    cfg = _report_settings()
    cfg["reason"] = arg.lower()
    db_write("report_cfg", cfg)
    await edit_or_reply(event, f"✅ تم ضبط نوع البلاغ: {arg}")


@cmd(r"شد_رساله(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        return await edit_delete(event, f"- اكتب: {PREFIX}شد_رساله <نص البلاغ>", 8)
    cfg = _report_settings()
    cfg["message"] = arg
    db_write("report_cfg", cfg)
    await edit_or_reply(event, f"✅ تم ضبط رسالة البلاغ:\n{arg}")


@cmd(r"شد_سرعه(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg.isdigit():
        return await edit_delete(event, f"- اكتب: {PREFIX}شد_سرعه <ثواني التأخير>", 8)
    cfg = _report_settings()
    cfg["speed"] = max(1, min(int(arg), 60))
    db_write("report_cfg", cfg)
    await edit_or_reply(event, f"✅ سرعة البلاغ (تأخير): {cfg['speed']} ثانية")


@cmd(r"شد_ايقاف$")
async def _(event):
    cfg = _report_settings()
    cfg["running"] = False
    db_write("report_cfg", cfg)
    await edit_or_reply(event, "⏹️ تم طلب إيقاف البلاغ المستمر")


@cmd(r"شد_اعداد$")
async def _(event):
    cfg = _report_settings()
    await edit_or_reply(
        event,
        f"**◂ إعدادات الشد الداخلي:**\n"
        f"الهدف: {cfg['target'] or 'لايوجد'}\n"
        f"النوع: {cfg['reason']}\n"
        f"الرسالة: {cfg['message']}\n"
        f"السرعة: {cfg['speed']} ثانية\n"
        f"يعمل الآن: {'نعم' if cfg['running'] else 'لا'}\n\n"
        f"الأوامر:\n"
        f"`{PREFIX}شد_هدف` <رابط/يوزر>\n"
        f"`{PREFIX}شد_نوع` <نوع>\n"
        f"`{PREFIX}شد_رساله` <نص>\n"
        f"`{PREFIX}شد_سرعه` <ثواني>\n"
        f"`{PREFIX}شد` ◂ يبدأ البلاغ المستمر\n"
        f"`{PREFIX}شد_ايقاف` ◂ يوقفه",
    )


@cmd(r"شد(?:\s|$)([\s\S]*)")
async def _(event):
    arg = (event.pattern_match.group(1) or "").strip()
    cfg = _report_settings()
    target = arg or cfg["target"]
    if not target:
        return await edit_delete(event, f"- اكتب: {PREFIX}شد <رابط/يوزر/آيدي> (أو ضع هدفاً بـ {PREFIX}شد_هدف)", 8)
    cfg["target"] = target
    cfg["running"] = True
    db_write("report_cfg", cfg)
    m = await event.edit(
        f"🚨 بدء البلاغ المستمر على:\n{target}\nالنوع: {cfg['reason']}\nالسرعة: {cfg['speed']}ث\n"
        f"(سيُوقف تلقائياً إذا حُظر الهدف — أو بـ {PREFIX}شد_ايقاف)"
    )
    sent = 0
    err_count = 0
    while True:
        cfg = _report_settings()
        if not cfg.get("running", False):
            await edit_or_reply(m, f"⏹️ تم الإيقاف بطلبك.\n📊 بلاغات مُرسلة: {sent}")
            return
        # فحص كل دورة: هل الهدف لم يُحظر بعد؟
        alive, res = await _target_still_alive(target)
        if not alive:
            await edit_or_reply(m, f"⛔ توقّف البلاغ تلقائياً:\n{res}\n📊 بلاغات مُرسلة: {sent}")
            cfg = _report_settings()
            cfg["running"] = False
            db_write("report_cfg", cfg)
            return
        ent = res
        r = await _do_report(ent, cfg["reason"], cfg["message"])
        if r is True:
            sent += 1
            err_count = 0
            try:
                await m.edit(f"🚨 بلاغ مستمر...\n📊 مُرسل: {sent}\nالنوع: {cfg['reason']}\nالسرعة: {cfg['speed']}ث")
            except Exception:
                pass
        else:
            err_count += 1
            # أخطاء متتالية قد تعني حظر الحساب أو الهدف
            await edit_or_reply(m, f"⚠️ خطأ في البلاغ ({err_count}): {r}\n📊 مُرسل: {sent}")
            if err_count >= 5:
                cfg = _report_settings()
                cfg["running"] = False
                db_write("report_cfg", cfg)
                return await edit_or_reply(m, f"⛔ توقّف بعد أخطاء متتالية.\n📊 بلاغات مُرسلة: {sent}")
        await asyncio.sleep(cfg["speed"])


# ============================================================
#              التحديثات | GITHUB UPDATES
# ============================================================

GITHUB_REPO = "Hmza1112617/Hamza-Userbot"  # مستودع السورس


def _github_get(path):
    """طلب متزامن لـ GitHub API (يُشغَّل داخل thread)"""
    import urllib.request

    url = f"https://api.github.com/repos/{GITHUB_REPO}/{path}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "HamzaUserbot", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


@cmd(r"تحديثات$")
async def _(event):
    m = await event.edit("🔄 جاري فحص التحديثات من GitHub...")
    try:
        commits = await asyncio.to_thread(_github_get, "commits?per_page=8")
        lines = ["**◂ آخر التحديثات والإضافات (GitHub):**\n"]
        for c in commits:
            msg = c["commit"]["message"].split("\n")[0][:80]
            date = c["commit"]["author"]["date"][:10]
            author = c["commit"]["author"]["name"]
            lines.append(f"• `{date}` — {msg}\n  بواسطة: {author}")
        out = "\n".join(lines)
        out += f"\n\nالمستودع: https://github.com/{GITHUB_REPO}"
        await edit_or_reply(m, out)
    except Exception as e:
        await edit_or_reply(m, f"- خطأ بجلب التحديثات: `{e}`")


@cmd(r"اخر_تحديث$")
async def _(event):
    m = await event.edit("🔄 ...")
    try:
        rel = await asyncio.to_thread(_github_get, "releases/latest")
        name = rel.get("name") or rel.get("tag_name") or "بدون اسم"
        body = rel.get("body") or "لا يوجد وصف"
        notes = body[:1500]
        await edit_or_reply(m, f"**◂ آخر إصدار:** `{name}`\n\n{notes}\n\nرابط: {rel.get('html_url','')}")
    except Exception as e:
        await edit_or_reply(m, f"- لا يوجد إصدار بعد أو خطأ: `{e}`")


import subprocess

RESTART_CMD = [sys.executable, os.path.abspath(__file__)]


@cmd(r"تحديث$")
async def _(event):
    m = await event.edit("🔄 جاري تنزيل التحديث من GitHub...")
    try:
        # حفظ مكان الرسالة لإرسال تأكيد بعد إعادة التشغيل
        db_set("settings", "restart_chat", event.chat_id)
        db_set("settings", "restart_msg", event.id)
        # سحب آخر تغييرات (مع تجاوز تحذير ملكية المجلد لي works للكل)
        proc = await asyncio.to_thread(
            subprocess.run,
            ["git", "-c", "safe.directory=*", "pull", "origin", "clean-main"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=120,
        )
        out = (proc.stdout or proc.stderr or "")[:1500]
        if proc.returncode != 0:
            await m.edit(f"- فشل السحب:\n`{out}`")
            # تنظيف مؤشر إعادة التشغيل
            s = db_read("settings")
            s.pop("restart_chat", None)
            s.pop("restart_msg", None)
            db_write("settings", s)
            return
        await m.edit(f"✅ تم تنزيل التحديث:\n`{out}`\n🔁 جاري إعادة التشغيل...")
        await asyncio.sleep(1.5)
        # إعادة تشغيل السورس
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])
    except Exception as e:
        await edit_or_reply(m, f"- خطأ بالتحديث: `{e}`")


@client.on(events.NewMessage(incoming=True))
async def _ai_auto_watcher(event):
    if not event.is_private or not event.text:
        return
    if not db_get("settings", "ai_auto", False):
        return
    if db_get("settings", "ai_full", False):
        return  # الوضع الشامل للأمر فقط، لا رد تلقائي بالخاص
    sender = await event.get_sender()
    if sender is None or getattr(sender, "bot", False):
        return
    me = await client.get_me()
    if event.sender_id == me.id:
        return
    try:
        async with client.action(event.chat_id, "typing"):
            answer = await ai_ask(event.raw_text, event)
        if answer:
            await event.reply(answer)
    except Exception:
        pass


# ============================================================
#                    التشغيل | RUN
# ============================================================


async def _startup():
    global flood_guard
    # ضبط safe.directory تلقائياً ليتجنّب خطأ dubious ownership لأي مستخدم
    try:
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", BASE_DIR],
            cwd=BASE_DIR, capture_output=True, timeout=20,
        )
    except Exception:
        pass
    me = await client.get_me()
    _load_insults()
    build_source_info()
    is_premium = getattr(me, "premium", False)
    flood_guard = TextFloodGuard(is_premium=is_premium)
    print("=" * 45)
    print(f"  سورس حمزة يعمل الآن ✓")
    print(f"  الحساب: {get_display_name(me)} | {me.id}")
    print(f"  البادئة: {PREFIX} | أرسل {PREFIX}الاوامر")
    print(f"  تركيبات السب: {insult_combos():,}")
    print(f"  حماية الفلود: {'🛡️ مفعلة' if flood_guard_enabled else '🚫 معطلة'}")
    print(f"  نوع الحساب: {'بريميوم' if is_premium else 'عادي'}")
    print("=" * 45)
    # رسالة بعد إعادة التشغيل
    rc = db_get("settings", "restart_chat")
    rm = db_get("settings", "restart_msg")
    if rc and rm:
        try:
            await client.edit_message(rc, rm, "تم إعادة التشغيل بنجاح ✓")
        except Exception:
            pass
        s = db_read("settings")
        s.pop("restart_chat", None)
        s.pop("restart_msg", None)
        db_write("settings", s)


def main():
    new_login = not CONFIG["STRING_SESSION"]
    phone = ""
    if new_login:
        print("=" * 45)
        print("  لا يوجد كود سيشن — سيتم تسجيل الدخول الآن")
        print("  أدخل رقم هاتفك مع رمز الدولة (مثال: +96478...)")
        print("=" * 45)
        try:
            phone = input("📱 رقم الهاتف: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("تم الإلغاء")
            sys.exit(1)
        if not phone.startswith("+"):
            phone = "+" + phone.lstrip("+")
    try:
        if new_login and phone:
            client.start(phone=lambda: phone)
        else:
            client.start()
    except Exception as e:
        print(f"خطأ بتسجيل الدخول: {e}")
        # محاولة تفاعلية كاحتياط
        if new_login:
            client.start()
    # حفظ كود السيشن المولّد تلقائياً بعد أول تسجيل دخول
    if new_login:
        try:
            session_str = client.session.save()
            save_session(session_str)
            print("=" * 45)
            print("  تم تسجيل الدخول وحفظ كود السيشن تلقائياً ✓")
            print("  لن يُطلب منك تسجيل الدخول مرة أخرى")
            print("=" * 45)
        except Exception:
            pass
    client.loop.run_until_complete(_startup())
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
