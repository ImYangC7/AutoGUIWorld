# -*- coding: utf-8 -*-
"""Mobile home-screen inventory: app pool + layered home-screen sampler.

This is the mobile counterpart of the desktop window inventory in
``environment.py`` (``WINDOW_APP_POOL`` + ``sample_windows``). Desktop seeds get
a reproducible list of open windows (app + position + content + occlusion);
mobile seeds get a reproducible *home screen* — the layered structure a real
phone home screen has:

    status bar  ·  wallpaper  ·  app icon grid  ·  dock  ·  page dots

Modeled on a real tall-screen Android home screen (see project goal): a
4-column icon grid over a photo wallpaper, a fixed bottom dock (phone /
messages / camera), and a page indicator showing which of several home pages
is current. The look is kept vendor-neutral on purpose — no phone-maker
branding.

Nothing here touches the desktop path. ``seed.py`` attaches the sampled layout
to ``env_state['home_screen']`` (parallel to ``env_state['windows']``), and
``state_to_descriptive_text`` renders it via ``home_screen_to_text``.
"""

import random

from autogui.state.registry import is_apple_mobile, is_mobile


# === App pool ====================================================
# (display_name, icon_description, locale) where locale is one of:
#   'cn'   — China-market app (Chinese name / brand)
#   'intl' — international app
#   'both' — globally recognized, fits either locale
# icon_description is a short visual phrase (color + glyph) so the image model
# can render a recognizable, crisp icon instead of a generic colored square.
APP_POOL = {
    'social_comm': [
        ('微信', 'green icon with two overlapping white speech bubbles', 'cn'),
        ('QQ', 'blue icon with a white winking penguin', 'cn'),
        ('微博', 'orange-red icon with a white stylized eye', 'cn'),
        ('小红书', 'red rounded icon with white "小红书" lettering', 'cn'),
        ('钉钉', 'blue icon with a white smiling figure', 'cn'),
        ('飞书', 'blue-to-cyan gradient icon with a white paper-plane swallow', 'cn'),
        ('企业微信', 'blue icon with a white speech bubble and people', 'cn'),
        ('WhatsApp', 'green icon with a white phone inside a speech bubble', 'intl'),
        ('Telegram', 'blue circular icon with a white paper plane', 'intl'),
        ('Messenger', 'blue-purple gradient icon with a white lightning speech bubble', 'intl'),
        ('Discord', 'indigo icon with a white game-controller-like mascot', 'intl'),
        ('LINE', 'green icon with a white speech bubble and "LINE"', 'intl'),
        ('KakaoTalk', 'yellow icon with a brown talking face', 'intl'),
        ('Snapchat', 'yellow icon with a white ghost', 'intl'),
        ('Instagram', 'pink-orange gradient icon with a white camera outline', 'both'),
        ('X', 'black icon with a white X logo', 'both'),
        ('Facebook', 'blue icon with a white lowercase f', 'both'),
        ('Threads', 'black icon with a white @-like thread loop', 'intl'),
        ('Reddit', 'orange-red icon with the white Snoo alien head', 'intl'),
        ('陌陌', 'yellow-green gradient icon with a white "陌" mark', 'cn'),
        ('脉脉', 'blue icon with a white linked-people network mark', 'cn'),
    ],
    'shopping': [
        ('淘宝', 'orange icon with a white "淘" Taobao mark', 'cn'),
        ('天猫', 'red icon with a white cat-head silhouette', 'cn'),
        ('京东', 'red icon with a white dog mascot "JOY"', 'cn'),
        ('拼多多', 'red icon with white "拼多多" lettering', 'cn'),
        ('美团', 'yellow icon with a white kangaroo-and-text mark', 'cn'),
        ('饿了么', 'blue icon with white "饿了么" lettering', 'cn'),
        ('闲鱼', 'yellow icon with a white smiling fish', 'cn'),
        ('唯品会', 'red-pink icon with white "VIP" lettering', 'cn'),
        ('得物', 'black icon with white "得物 POIZON" text', 'cn'),
        ('大众点评', 'orange icon with a white magnifier and dot pattern', 'cn'),
        ('Amazon', 'dark icon with the white Amazon smile arrow', 'both'),
        ('Shopee', 'orange icon with a white shopping bag', 'intl'),
        ('Lazada', 'blue-to-pink gradient icon with a white shopping bag', 'intl'),
        ('eBay', 'white icon with multicolor "ebay" lettering', 'intl'),
        ('Temu', 'orange icon with a white shopping-bag and "Temu"', 'both'),
        ('永辉生活', 'red-orange icon with white "永辉" lettering', 'cn'),
        ('小米商城', 'orange icon with the white "MI" logo', 'cn'),
        ('小米有品', 'orange icon with white "有品" lettering', 'cn'),
        ('华为商城', 'red icon with the white Huawei flower-petal logo', 'cn'),
        ('Shein', 'black icon with white "SHEIN" lettering', 'intl'),
        ('Walmart', 'blue icon with the yellow six-spark sun logo', 'intl'),
    ],
    'video': [
        ('抖音', 'black icon with the white-and-cyan music-note "D"', 'cn'),
        ('快手', 'orange icon with a white quick-camera mark', 'cn'),
        ('哔哩哔哩', 'pink icon with a white smiling-TV bilibili face', 'cn'),
        ('腾讯视频', 'orange icon with a white play triangle', 'cn'),
        ('爱奇艺', 'green icon with a white "iQIYI" play mark', 'cn'),
        ('优酷', 'blue icon with a white "优酷 YOUKU"', 'cn'),
        ('芒果TV', 'orange icon with a white mango and "TV"', 'cn'),
        ('西瓜视频', 'red-and-green watermelon icon with a play triangle', 'cn'),
        ('YouTube', 'white icon with a red rounded rectangle and white play triangle', 'both'),
        ('Netflix', 'black icon with the red "N" ribbon', 'intl'),
        ('TikTok', 'black icon with the white-and-cyan music-note logo', 'intl'),
        ('Disney+', 'navy icon with the white Disney+ script', 'intl'),
        ('Twitch', 'purple icon with a white chat-bubble glitch mark', 'intl'),
        ('好看视频', 'blue icon with a white play triangle and "好看"', 'cn'),
        ('懂球帝', 'red icon with a white soccer ball', 'cn'),
    ],
    'music_audio': [
        ('网易云音乐', 'red icon with a white music note inside a circle', 'cn'),
        ('QQ音乐', 'green icon with a white music-note penguin mark', 'cn'),
        ('酷狗音乐', 'blue icon with a white headphone-wearing figure', 'cn'),
        ('喜马拉雅', 'orange icon with a white "喜" sound-wave mark', 'cn'),
        ('汽水音乐', 'teal icon with a white soda-bottle music note', 'cn'),
        ('Spotify', 'green circular icon with three black sound-wave bars', 'both'),
        ('Apple Music', 'red-pink gradient icon with a white double music note', 'both'),
        ('SoundCloud', 'orange icon with white sound-wave bars', 'intl'),
        ('咪咕音乐', 'pink-purple icon with a white deer-antler music note', 'cn'),
        ('酷我音乐', 'yellow icon with a white "K" music mark', 'cn'),
        ('蜻蜓FM', 'orange icon with a white dragonfly', 'cn'),
    ],
    'travel_maps': [
        ('高德地图', 'blue icon with a white location pin and road', 'cn'),
        ('百度地图', 'blue icon with a white compass-and-pin paw mark', 'cn'),
        ('携程', 'blue icon with a white "携程 Ctrip" mark', 'cn'),
        ('滴滴出行', 'orange icon with a white "滴" car mark', 'cn'),
        ('12306', 'blue icon with a white high-speed-train front', 'cn'),
        ('飞猪', 'orange icon with a white flying-pig mark', 'cn'),
        ('Google Maps', 'white icon with a colored location pin over a map fragment', 'both'),
        ('Uber', 'black icon with white "Uber" lettering', 'intl'),
        ('Booking.com', 'blue icon with white "B." lettering', 'intl'),
        ('Airbnb', 'white icon with the pink Bélo loop logo', 'intl'),
        ('华住会', 'orange icon with a white "H" hotel mark', 'cn'),
        ('神州租车', 'green icon with a white car-and-key mark', 'cn'),
        ('极氪', 'dark icon with the white ZEEKR wordmark', 'cn'),
    ],
    'finance': [
        ('支付宝', 'blue icon with a white "支" alipay mark', 'cn'),
        ('云闪付', 'red icon with the white UnionPay flash mark', 'cn'),
        ('中国银行', 'red icon with the white BOC coin-square logo', 'cn'),
        ('工商银行', 'red icon with the white ICBC square-hole-coin logo', 'cn'),
        ('招商银行', 'red icon with the white CMB bird-wave logo', 'cn'),
        ('同花顺', 'red icon with a white candlestick-chart mark', 'cn'),
        ('东方财富', 'red icon with white "东方财富" and an up-arrow', 'cn'),
        ('PayPal', 'blue icon with the white double-P logo', 'intl'),
        ('Wise', 'green icon with a white flag-wave mark', 'intl'),
        ('Binance', 'black icon with the yellow diamond logo', 'intl'),
        ('财联社', 'red icon with white "财联社" lettering', 'cn'),
    ],
    'productivity': [
        ('WPS Office', 'red icon with a white "W" document mark', 'cn'),
        ('印象笔记', 'green icon with a white elephant head', 'cn'),
        ('滴答清单', 'blue icon with a white checkmark', 'cn'),
        ('倒数日', 'light-blue icon with a white calendar showing a big number', 'cn'),
        ('腾讯会议', 'blue icon with a white camera-in-circle mark', 'cn'),
        ('Notion', 'white icon with the black "N" cube logo', 'both'),
        ('Gmail', 'white icon with the red-and-multicolor M envelope', 'both'),
        ('Outlook', 'blue icon with a white envelope and "O"', 'both'),
        ('网易邮箱大师', 'red icon with a white envelope and "AI" badge', 'cn'),
        ('日历', 'white icon showing the weekday and a large date number', 'cn'),
        ('计算器', 'dark icon with a white calculator keypad grid', 'cn'),
        ('备忘录', 'yellow icon with white note lines and a top bar', 'cn'),
        ('时钟', 'white clock-face icon with black hands', 'cn'),
        ('文件管理', 'blue icon with a white folder', 'cn'),
        ('智谱清言', 'blue-purple gradient icon with a white "Z" AI spark', 'cn'),
        ('扫描全能王', 'orange icon with a white scanner-frame "S"', 'cn'),
        ('万年历', 'red icon with a white calendar page showing a date', 'cn'),
        ('Google Calendar', 'white icon with a colored "31" calendar grid', 'intl'),
        ('Google Keep', 'white icon with a yellow lightbulb mark', 'intl'),
        ('Microsoft To Do', 'blue icon with a white checkmark list mark', 'intl'),
    ],
    'news_reading': [
        ('今日头条', 'red icon with white "头条" lettering', 'cn'),
        ('知乎', 'blue icon with white "知乎" lettering', 'cn'),
        ('微信读书', 'green icon with a white open-book mark', 'cn'),
        ('网易新闻', 'red icon with a white "网易新闻" mark', 'cn'),
        ('豆瓣', 'green icon with white "豆" lettering', 'cn'),
        ('起点读书', 'blue icon with a white "起" book mark', 'cn'),
        ('Kindle', 'black icon with the white reading-under-tree logo', 'intl'),
        ('Medium', 'black icon with a white "M" serif logo', 'intl'),
        ('番茄免费小说', 'red icon with a white tomato and "番茄"', 'cn'),
        ('七猫免费小说', 'orange icon with a white cat and "七猫"', 'cn'),
        ('晋江小说', 'pink icon with white "晋江" lettering', 'cn'),
        ('虎扑', 'orange icon with a white "H" jump mark', 'cn'),
    ],
    'photo_camera': [
        ('相机', 'dark icon with a white camera lens', 'cn'),
        ('图库', 'white icon with a colorful pinwheel-photo mark', 'cn'),
        ('美图秀秀', 'pink icon with a white camera-and-sparkle mark', 'cn'),
        ('醒图', 'black icon with white "醒图" lettering', 'cn'),
        ('轻颜相机', 'pink icon with a white face-outline camera', 'cn'),
        ('Snapseed', 'white icon with the green leaf-aperture logo', 'intl'),
        ('Lightroom', 'dark-blue icon with the "Lr" lettering', 'both'),
        ('VSCO', 'white icon with a black circle logo', 'intl'),
    ],
    'education': [
        ('作业帮', 'blue icon with a white pencil-and-book mark', 'cn'),
        ('网易有道词典', 'red icon with a white "Y" dictionary mark', 'cn'),
        ('学习强国', 'red icon with the white Tiananmen-and-star mark', 'cn'),
        ('力扣 LeetCode', 'white icon with a black-and-yellow angular "LC" mark', 'both'),
        ('Duolingo', 'green icon with the white owl mascot', 'both'),
        ('Coursera', 'blue icon with a white "C" graduation mark', 'intl'),
        ('Quizlet', 'blue icon with a white lightning-card mark', 'intl'),
        ('驾考宝典', 'green icon with a white steering-wheel mark', 'cn'),
    ],
    'food_life': [
        ('下厨房', 'orange icon with a white cooking-pot mark', 'cn'),
        ('Keep', 'black icon with a white "K" running mark', 'cn'),
        ('薄荷健康', 'green icon with a white mint-leaf mark', 'cn'),
        ('咕咚', 'green icon with a white running-figure mark', 'cn'),
        ('Zepp', 'black icon with a white "Z" pulse mark', 'cn'),
        ('天气', 'blue gradient icon with a white sun behind a cloud', 'cn'),
        ('墨迹天气', 'blue icon with a white sun-and-cloud "M"', 'cn'),
        ('Health', 'white icon with a red heart', 'intl'),
        ('Starbucks', 'green circular icon with the white siren logo', 'both'),
        ('亲宝宝', 'orange icon with a white baby-face mark', 'cn'),
        ('猫眼专业版', 'orange icon with a white cat-eye mark', 'cn'),
    ],
    'games': [
        ('王者荣耀', 'dark icon with a golden warrior-helmet crest', 'cn'),
        ('和平精英', 'tan icon with a soldier silhouette and parachute', 'cn'),
        ('原神', 'dark icon with the white Genshin Impact emblem', 'both'),
        ('蛋仔派对', 'pink icon with a cute round jelly character', 'cn'),
        ('第五人格', 'dark icon with a gothic mask-and-feather mark', 'cn'),
        ('Steam', 'dark navy icon with the white steam-valve gear logo', 'both'),
        ('Roblox', 'white icon with the red tilted square logo', 'intl'),
        ('Minecraft', 'icon of a green-brown grass-block cube', 'intl'),
    ],
    'browsers': [
        ('夸克', 'blue icon with a white circular quark mark', 'cn'),
        ('UC浏览器', 'orange icon with a white squirrel "U" mark', 'cn'),
        ('Chrome', 'white icon with the red-green-yellow-blue Chrome circle', 'both'),
        ('Safari', 'white icon with a blue compass face', 'intl'),
        ('Edge', 'icon with a blue-green swirling wave logo', 'both'),
        ('悟空浏览器', 'dark icon with a golden Monkey-King headband mark', 'cn'),
        ('百度', 'blue icon with a white bear-paw mark', 'cn'),
    ],
    'tools_system': [
        ('设置', 'gray icon with a white gear', 'cn'),
        ('应用市场', 'blue icon with a white "A" bag mark', 'cn'),
        ('App Store', 'blue icon with a white stylus-A logo', 'intl'),
        ('Google Play', 'white icon with the colored play triangle', 'intl'),
        ('主题', 'colorful icon with a white paintbrush', 'cn'),
        ('查找设备', 'blue icon with a white radar-locate mark', 'cn'),
        ('钱包', 'black icon with white overlapping cards', 'cn'),
        ('录音机', 'gray icon with a white sound-wave mic', 'cn'),
        ('扫一扫', 'dark icon with a white QR-scan frame', 'cn'),
        ('翻译', 'blue icon with white "文/A" translate glyphs', 'cn'),
    ],
    'work_misc': [
        ('BOSS直聘', 'green icon with white "BOSS直聘" lettering', 'cn'),
        ('阿里云', 'orange icon with white "阿里云" cloud lettering', 'cn'),
        ('百度网盘', 'blue icon with a white cloud-and-bear-paw mark', 'cn'),
        ('腾讯文档', 'blue icon with a white document-and-pen mark', 'cn'),
        ('DJI Mimo', 'black icon with the white DJI gimbal logo', 'both'),
        ('滴滴车主', 'orange icon with a white steering-wheel mark', 'cn'),
        ('顺丰速运', 'black icon with white "SF" express lettering', 'cn'),
        ('菜鸟', 'orange icon with a white hatching-chick mark', 'cn'),
        ('Slack', 'white icon with the multicolor hashtag logo', 'intl'),
        ('GitHub', 'black icon with the white Octocat mark', 'intl'),
        ('58同城', 'blue icon with white "58" lettering', 'cn'),
        ('企查查', 'blue icon with a white magnifier over "企"', 'cn'),
        ('汽车之家', 'orange icon with a white "车" and roof mark', 'cn'),
        ('中国移动云盘', 'blue icon with a white cloud mark', 'cn'),
        ('贝壳找房', 'green icon with a white shell-and-house mark', 'cn'),
        ('安居客', 'orange icon with white "安居客" lettering', 'cn'),
        ('Uber Eats', 'green icon with white "Uber Eats" lettering', 'intl'),
    ],
}


# Platform-exclusive apps: these only ship on one mobile OS, so they must never
# appear on the other (e.g. App Store / Safari are iOS-only; Google Play is
# Android-only). Apps not listed here are treated as cross-platform. Keyed by
# the platform that DOES have the app.
_IOS_ONLY = {'App Store', 'Safari'}
_ANDROID_ONLY = {'Google Play', '应用市场'}


def _excluded_for(is_ios):
    """App names that must be filtered out for the given mobile platform."""
    return _ANDROID_ONLY if is_ios else _IOS_ONLY


# Dock apps (the fixed bottom row). Phone / Messages / Camera are the classic
# trio; Browser sometimes added as a 4th. Each tuple = (name, icon, locale).
DOCK_POOL = {
    'cn': [
        ('电话', 'green icon with a white phone handset', 'cn'),
        ('信息', 'blue icon with a white speech bubble', 'cn'),
        ('相机', 'dark icon with a white camera lens', 'cn'),
        ('浏览器', 'blue icon with a white globe', 'cn'),
    ],
    'intl': [
        ('Phone', 'green icon with a white phone handset', 'intl'),
        ('Messages', 'green icon with a white speech bubble', 'intl'),
        ('Camera', 'dark icon with a white camera lens', 'intl'),
        ('Safari', 'white icon with a blue compass face', 'intl'),
    ],
}

# Visual icon/grid styles. Brand-neutral on purpose — no vendor names and no
# proprietary design-language names, so the rendered screenshot carries no
# obvious phone-maker branding, only a generic modern Android look. iOS is
# fixed separately.
ANDROID_SKINS = [
    'rounded-square icons in a 4-column grid, wallpaper-derived dynamic accent color, a soft pill-shaped dock',
    'flat colorful icons in a 4-column grid with large rounded corners and a translucent dock',
    'squircle icons in a 4-column grid over a tinted glass dock, dynamic accent color',
    'soft rounded icons on a light airy 4-column grid with frosted glass-like containers',
    'clean rounded icons in an evenly spaced 4-column grid, bold wallpaper-derived accent color',
    'circular adaptive icons in a 4-column grid with a minimal translucent dock',
]

# Concrete wallpaper scenes for the photo / artistic wallpaper types. Chosen to
# look like real phone wallpapers (the reference used a border-collie photo).
WALLPAPER_SCENES = {
    'landscape_photo': [
        'a close-up photo of a black-and-white border collie looking up, suburban road and overcast sky behind',
        'a misty green mountain valley at sunrise with layered ridgelines',
        'a calm ocean horizon at golden hour with soft waves',
        'a snow-capped peak under a clear deep-blue sky',
        'a cherry-blossom branch in soft focus against a pale sky',
        'a city skyline at blue hour with glowing windows',
        'a field of lavender stretching to a hazy treeline',
        'a tabby cat curled up on a sunlit windowsill',
        'a desert dune ridge with long evening shadows',
        'a forest path with sunbeams through tall pines',
    ],
    'abstract_art': [
        'a flowing abstract liquid-marble pattern in soft pastels',
        'a colorful low-poly geometric mosaic',
        'an abstract aurora of blended neon gradients',
    ],
    'geometric_pattern': [
        'a repeating geometric pattern of thin lines and dots',
        'an isometric grid of soft 3D cubes',
    ],
}

# Plausible status-bar clock readings (mix of 12h and 24h, like real phones).
_CLOCK_TIMES = ['1:53', '9:41', '7:08', '11:30', '14:26', '16:05', '20:47', '22:17', '8:15', '10:24']

# Optional status-bar indicator glyphs (right cluster, before signal/battery).
_STATUS_INDICATORS = [
    'eye-comfort (low blue light) icon', 'NFC icon', 'Bluetooth icon',
    'location/GPS icon', 'silent/mute icon', 'alarm-clock icon', 'VPN key icon',
]


def _battery_from_state(state, rng):
    """Map the coarse battery_state to a concrete percentage + charging flag."""
    table = {'high': (80, 100), 'medium': (35, 70), 'low': (6, 22), 'charging': (25, 95)}
    lo, hi = table.get(state, (40, 90))
    return rng.randint(lo, hi), (state == 'charging')


def _network_from_state(conn, rng):
    """Map connection_state to a (radio_label, on_wifi) status-bar pair."""
    if conn in ('wifi_home', 'wifi_office'):
        return 'WiFi (full bars)', True
    if conn == 'no_network':
        return 'no signal / airplane mode', False
    if conn == 'cellular_5G':
        return '5G', False
    if conn == 'mobile_data':
        return rng.choice(['5G', '4G', 'LTE']), False
    return rng.choice(['5G', '4G']), False


def _locale_pool(locale, is_ios, rng):
    """Flatten APP_POOL into one shuffled list filtered to locale and platform.

    'chinese'  -> cn + both apps;  'english' -> intl + both apps.
    Platform-exclusive apps for the OTHER OS are dropped (see _excluded_for).
    Returns list of (name, icon) with the locale tag dropped.
    """
    want_cn = locale != 'english'
    excluded = _excluded_for(is_ios)
    out = []
    for apps in APP_POOL.values():
        for name, icon, lc in apps:
            if name in excluded:
                continue
            if lc == 'both' or (lc == 'cn' and want_cn) or (lc == 'intl' and not want_cn):
                out.append((name, icon))
    rng.shuffle(out)
    return out


def _badge_value(rng):
    """A realistic unread badge: red dot, a small count, or 99+."""
    return rng.choice(['•', '1', '2', '3', '5', '8', '12', '13', '23', '99+'])


def sample_home_screen(os_key, env_state, aesthetic, rng=None):
    """Build a reproducible, layered phone home-screen inventory.

    Mobile counterpart of ``sample_windows``. Returns a dict with the layers a
    real home screen has (status bar, wallpaper, app grid, dock, page
    indicator). Only meaningful for mobile OS; returns None otherwise.

    Reads from env_state: identity_locale, home_screen_page,
    unread_app_badges, connection_state, battery_state, do_not_disturb. Reads
    wallpaper_type / wallpaper_tone / theme from the sampled aesthetic.
    """
    if not is_mobile(os_key):
        return None
    if rng is None:
        rng = random.Random()
    is_ios = is_apple_mobile(os_key)
    locale = env_state.get('identity_locale', 'chinese')
    loc_key = 'intl' if locale == 'english' else 'cn'

    # ── Icon / grid visual style ──
    # iOS: real full-color brand icons as glossy squircles with a subtle glass
    # sheen (NOT uniform frosted tiles), in a 4-column grid above a floating
    # translucent glass dock. The OS version / design-language name is carried by
    # the registry (style_directive), not duplicated here. Android: a neutral grid.
    skin = ('full-color app icons as glossy rounded squircles with a subtle '
            'translucent-glass sheen, in a 4-column grid above a floating '
            'translucent glass dock') if is_ios \
        else rng.choice(ANDROID_SKINS)
    cols = 4

    # ── Status bar ──
    radio, on_wifi = _network_from_state(env_state.get('connection_state'), rng)
    pct, charging = _battery_from_state(env_state.get('battery_state'), rng)
    indicators = rng.sample(_STATUS_INDICATORS, rng.randint(1, 3))
    if env_state.get('do_not_disturb'):
        indicators.insert(0, 'Do Not Disturb (crescent moon) icon')
    status_bar = {
        'time': rng.choice(_CLOCK_TIMES),
        'radio': radio,
        'on_wifi': on_wifi,
        'signal_bars': 'full' if env_state.get('connection_state') != 'no_network' else 'none',
        'indicators': indicators,
        'battery_pct': pct,
        'charging': charging,
        'dynamic_island': bool(is_ios) and env_state.get('dynamic_island', 'idle') != 'idle',
    }

    # ── Wallpaper (from aesthetic) ──
    wp_type = aesthetic.get('wallpaper_type', 'gradient')
    tone = aesthetic.get('wallpaper_tone', 'neutral')
    if wp_type in WALLPAPER_SCENES:
        wallpaper = rng.choice(WALLPAPER_SCENES[wp_type])
    elif wp_type == 'solid_color':
        wallpaper = f'a solid {tone}-toned color wallpaper'
    else:  # gradient
        wallpaper = f'a smooth {tone}-toned gradient wallpaper'

    # ── App grid ──
    # Folders are intentionally NOT generated: the image model renders folder
    # mini-grids unreliably (distorted / oversized tiles), so the home screen is
    # a flat grid of single app icons only.
    pool = _locale_pool(locale, is_ios, rng)
    rows = rng.randint(4, 6)
    n_slots = rows * cols
    badge_mode = env_state.get('unread_app_badges', 'none')

    grid = []
    pi = 0  # pool cursor

    def _take(k):
        nonlocal pi
        items = pool[pi:pi + k]
        pi += k
        return items

    # Real home screens often have a partly-empty last row. ~60% of the time
    # leave 1..cols-1 trailing slots blank instead of filling the grid exactly.
    fill = n_slots
    if rng.random() < 0.6:
        fill -= rng.randint(1, cols - 1)
    for name, icon in _take(max(0, fill - len(grid))):
        grid.append({'kind': 'app', 'name': name, 'icon': icon, 'badge': None})

    # Sprinkle unread badges across some tiles.
    if badge_mode != 'none' and grid:
        k = 1 if badge_mode == 'one_app' else rng.randint(2, 4)
        for tile in rng.sample(grid, min(k, len(grid))):
            tile['badge'] = _badge_value(rng)

    # ── Dock ──
    dock_src = DOCK_POOL[loc_key]
    n_dock = rng.choice([3, 3, 4])
    dock = [{'name': n, 'icon': ic, 'badge': None} for n, ic, _ in dock_src[:n_dock]]
    # The intl browser slot is Safari (iOS-only); swap it for a neutral browser on
    # Android so the dock never shows the wrong platform's stock browser.
    excluded = _excluded_for(is_ios)
    for slot in dock:
        if slot['name'] in excluded:
            slot['name'] = 'Chrome'
            slot['icon'] = 'white icon with the red-green-yellow-blue Chrome circle'
    if badge_mode != 'none':
        dock[0]['badge'] = rng.choice(['1', '2', '3'])          # phone: missed calls
        if len(dock) > 1:
            dock[1]['badge'] = rng.choice(['99+', '12', '5'])   # messages

    # ── Page indicator ──
    pages_total = rng.randint(3, 5)
    current_page = min(env_state.get('home_screen_page', 0), pages_total - 1)

    return {
        'vendor_skin': skin,
        'grid_columns': cols,
        'status_bar': status_bar,
        'wallpaper': wallpaper,
        'app_grid': grid,
        'dock': dock,
        'pages_total': pages_total,
        'current_page': current_page,
    }


def _fmt_tile(tile):
    """One grid tile -> compact text token."""
    badge = f' (badge {tile["badge"]})' if tile.get('badge') else ''
    return f'[app] {tile["name"]}{badge}'


def home_screen_to_text(hs):
    """Render a sampled home_screen into the bullet block used by prompts.

    Mirrors the per-window inventory block desktop produces, so the seed
    describer can expand each layer into the rich image prompt.
    """
    sb = hs['status_bar']
    lines = [f'• Mobile home screen — {hs["vendor_skin"]}; portrait, '
             f'{hs["grid_columns"]}-column app icon grid over the wallpaper.']

    ind = ('; indicators: ' + ', '.join(sb['indicators'])) if sb['indicators'] else ''
    batt = f'{sb["battery_pct"]}%' + (' (charging)' if sb['charging'] else '')
    di = ' Dynamic Island active.' if sb.get('dynamic_island') else ''
    lines.append(f'• Status bar (top): time {sb["time"]}; right cluster: signal '
                 f'{sb["signal_bars"]} bars, {sb["radio"]}{ind}; battery {batt}.{di}')
    lines.append(f'• Wallpaper (behind icons): {hs["wallpaper"]}.')

    lines.append(f'• App grid (row by row, up to {hs["grid_columns"]} apps per row, left to right):')
    cols = hs['grid_columns']
    grid = hs['app_grid']
    for r in range(0, len(grid), cols):
        row = grid[r:r + cols]
        note = f'  (then {cols - len(row)} empty slot(s) — rest of the row is blank)' if len(row) < cols else ''
        lines.append('    - ' + ' | '.join(_fmt_tile(t) for t in row) + note)

    dock = ' | '.join(
        f'{d["name"]}' + (f' (badge {d["badge"]})' if d.get('badge') else '')
        for d in hs['dock'])
    lines.append(f'• Dock (fixed bottom row, {len(hs["dock"])} icons): {dock}.')

    lines.append(f'• Page indicator (above dock): page {hs["current_page"] + 1} of '
                 f'{hs["pages_total"]} (current page highlighted as a short white bar, '
                 f'the rest small dots).')
    return '\n'.join(lines)
