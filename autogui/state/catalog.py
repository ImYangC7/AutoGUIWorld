# -*- coding: utf-8 -*-
"""Static web reference data shared across OS state modules (no logic).

Split out of ``environment.py`` so the large brand/content tables live apart
from sampling and rendering logic. Consumed by ``web.py`` (page/tab model) and
re-exported from ``environment.py`` for backward compatibility.
"""

# Categorized web-page catalog (Category -> Site -> [content templates]).
# Browsers (Chrome/Edge/Safari) draw from this so a browser window shows a
# realistic, named site rather than a generic "web app". Templates are grounded
# in web research of each site's signature pages.
WEB_CATALOG = {
    'Search': {
        'Google': [
            'a google search homepage with a centered search box, shortcut icons, and account controls',
            'a google search results page with blue result links, snippets, knowledge panel, and related searches',
            'a google images results page with image tiles, filter chips, and a search bar at the top',
            'a google maps search results page with a map, place cards, ratings, and route buttons',
        ],
        'Bing': [
            'a bing homepage with a large background image, centered search box, and quick link tiles',
            'a bing search results page with web result cards, news snippets, and a right-side info panel',
            'a bing images results page with masonry image thumbnails and filter controls',
        ],
        'DuckDuckGo': [
            'a duckduckgo search homepage with a centered search field and privacy-focused header',
            'a duckduckgo search results page with clean result cards, region filters, and instant answers',
        ],
        'Yandex': [
            'a yandex search homepage with a central search bar, service icons, weather, and news widgets',
            'a yandex search results page with snippets, image blocks, and service navigation tabs',
        ],
        'Baidu': [
            'a baidu homepage with a centered search box, navigation links, hot search topics, and account controls',
            'a baidu search results page with Chinese result snippets, related searches, and right-side cards',
        ],
        'Naver': [
            'a naver portal homepage with a green search bar, news modules, shopping links, and login panel',
            'a naver search results page with integrated results, blogs, news, shopping, and knowledge sections',
        ],
    },
    'AI': {
        'ChatGPT': [
            'a chatgpt conversation page with a left sidebar of past chats, a central assistant response, and a message composer',
            'a chatgpt new chat page with model selector, prompt suggestions, and a centered message input box',
            'a chatgpt settings or account menu open over the chat interface with workspace controls',
        ],
        'Gemini': [
            'a gemini chat page with a clean prompt input, suggestion cards, and a Google account avatar',
            'a gemini conversation page with a generated response, source chips, and a message composer at the bottom',
        ],
        'Claude': [
            'a claude.ai chat page with a left project sidebar, a central conversation, and a message input area',
            'a claude.ai new chat screen with recent chats, file upload controls, and a prompt composer',
        ],
    },
    'Travelling': {
        'Skyscanner': [
            'a skyscanner flight-search homepage with origin and destination fields and a date picker',
            'a skyscanner results page listing flights with prices, airline logos, and stop counts',
            'a skyscanner price calendar showing color-coded daily fares for the cheapest days',
            'a skyscanner explore-everywhere page with a map and destinations sorted by price',
        ],
    },
    'Commerce': {
        'AliExpress': [
            'an aliexpress homepage with a flash-deals strip, category icons, and a product grid',
            'an aliexpress search results page with product cards showing prices, ratings, and shipping badges',
            'an aliexpress product page with an image gallery, color and size variants, and an add-to-cart button',
            'an aliexpress product reviews section with star ratings and buyer photo uploads',
        ],
        'JD': [
            'a jd.com homepage with a left category menu, rotating promo banners, and flash-sale tiles',
            'a jd.com search results page with a product grid, price filters, and a brand sidebar',
            'a jd.com electronics product page with zoomable photos, specs, price, and a buy-now button',
            'a jd.com checkout page with address selection, delivery options, and a payment summary',
        ],
        'Revolut': [
            'a revolut dashboard with the account balance, recent transactions, and modular widgets',
            'a revolut spending analytics screen with categorized expenses and colorful charts',
            'a revolut cards page showing a virtual card, a freeze toggle, and spending limits',
            'a revolut crypto and stocks screen with a price chart and a buy button',
        ],
        'Shopee': [
            'a shopee homepage with an orange nav bar, category icons, and a flash-sale countdown strip',
            'a shopee search results page with product cards showing prices, discounts, and sold counts',
            'a shopee product page with photo thumbnails, voucher tags, variants, and an add-to-cart button',
            'a shopee cart page with seller-grouped items, checkboxes, and a total price bar',
        ],
        'Shopify': [
            'a shopify admin dashboard with a sidebar, sales overview cards, and a recent-orders list',
            'a shopify orders page with a table of orders, fulfillment status, and filter tabs',
            'a shopify product editor with image upload, pricing fields, variants, and inventory tracking',
            'a shopify analytics page with revenue charts, conversion rates, and traffic sources',
        ],
        'Walmart': [
            'a walmart homepage with a blue nav bar, department tiles, and seasonal deal banners',
            'a walmart search results page with a product grid, price filters, and pickup-or-delivery badges',
            'a walmart product page with large photos, price, an add-to-cart button, and related items',
            'a walmart grocery page with food category cards, a cart sidebar, and a delivery time slot',
        ],
        'Amazon': [
            'an amazon homepage with a search bar, department navigation, deal tiles, and personalized product rows',
            'an amazon search results page with product cards, price filters, ratings, Prime badges, and sponsored results',
            'an amazon product page with image gallery, title, star rating, price, variant selectors, and add-to-cart box',
            'an amazon cart page with item rows, quantity selectors, subtotal, and checkout button',
        ],
        'Temu': [
            'a temu homepage with orange deal banners, category chips, flash sale cards, and product recommendations',
            'a temu search results page with dense product cards, discount labels, ratings, and shipping badges',
            'a temu product detail page with gallery, variant selectors, price, coupons, and add-to-cart controls',
        ],
        'Ebay': [
            'an ebay homepage with a large search bar, category navigation, daily deals, and product carousels',
            'an ebay search results page with auction and buy-it-now listings, filters, prices, and shipping info',
            'an ebay item page with photo gallery, condition, seller rating, price, watch button, and buy-it-now controls',
        ],
    },
    'Finance': {
        'YahooFinance': [
            'a yahoo finance stock quote page with a price chart, quote summary, key statistics, market news, and related tickers',
            'a yahoo finance search results page with stock tickers, company names, prices, market change percentages, and exchange labels',
            'a yahoo finance historical data page with date range controls, frequency dropdown, download button, and a table of open high low close prices',
            'a yahoo finance chart page with an interactive stock price chart, one-day and one-year range buttons, indicators menu, and volume bars',
            'a yahoo finance portfolio watchlist page with ticker rows, last price, daily change, market cap, and small sparkline charts',
        ],
        'MarketWatch': [
            'a marketwatch stock quote page with a price chart, analyst ratings, latest news headlines, and key market data',
            'a marketwatch markets overview page with major indexes, sector performance tiles, top movers, and market news',
            'a marketwatch watchlist page with stock rows, last prices, percentage changes, and compact intraday charts',
        ],
        'TradingView': [
            'a tradingview chart page with a candlestick chart, ticker search bar, watchlist sidebar, drawing toolbar, and volume panel',
            'a tradingview markets screener with sortable ticker rows, sector filters, price change columns, and sparkline charts',
            'a tradingview symbol overview page with a large price chart, technical rating summary, and market news cards',
        ],
    },
    'ConsumerTech': {
        'Samsung': [
            'a samsung.com smartphone product page with a hero device image, color selector, storage options, price, and buy button',
            'a samsung.com product listing page with phone cards, filters, comparison controls, and promotional banners',
            'a samsung support page with a device search field, troubleshooting cards, warranty links, and support topics',
            'a samsung account or orders page with navigation tabs, product registration cards, and service request controls',
        ],
    },
    'Reference': {
        'Wikipedia': [
            'a wikipedia article page with a large title, table of contents, infobox, citations, and blue links',
            'a wikipedia search results page listing article titles, snippets, and language links',
            'a wikipedia category page with subcategory lists, page lists, and navigation boxes',
        ],
        'Fandom': [
            'a fandom wiki article page with an infobox, character image, section headings, and a right rail of related pages',
            'a fandom search results page with wiki cards, article snippets, and community navigation',
        ],
        'StackOverflow': [
            'a stack overflow question page with votes, accepted answer, code blocks, tags, and a right sidebar',
            'a stack overflow search results page with question titles, vote counts, answer counts, and tags',
        ],
    },
    'News': {
        'Yahoo': [
            'a yahoo homepage with top news stories, finance widgets, mail shortcut, and trending links',
            'a yahoo news article page with headline, byline, body text, related stories, and ad slots',
        ],
        'YahooJapan': [
            'a yahoo japan portal homepage with news columns, weather, search bar, shopping links, and login area',
            'a yahoo japan news page with Japanese headlines, article list, ranking module, and category tabs',
        ],
        'NYTimes': [
            'a new york times homepage with article columns, section navigation, headline cards, and subscription button',
            'a new york times article page with a large headline, byline, photo, article body, and related links',
        ],
        'Globo': [
            'a globo.com news homepage with colorful section cards, headlines, video thumbnails, and navigation tabs',
            'a globo.com article page with a headline, media image, body paragraphs, and related news cards',
        ],
        'Dzen': [
            'a dzen.ru content feed with article cards, video thumbnails, recommendations, and topic chips',
            'a dzen.ru article page with author info, article body, side recommendations, and reaction controls',
        ],
        'Weather': [
            'a weather.com forecast page with current temperature, hourly forecast cards, radar map, and severe weather alerts',
            'a weather.com ten-day forecast page with daily rows, precipitation percentages, and temperature ranges',
        ],
    },
    'Productivity': {
        'Airtable': [
            'an airtable grid view with colored cell rows, column headers, and a left table sidebar',
            'an airtable kanban board with stacked record cards arranged in labeled status columns',
            'an airtable calendar view showing records plotted across a monthly date grid',
            'an airtable base with a toolbar of view tabs and filter controls above a spreadsheet table',
        ],
        'Asana': [
            'an asana project list view with task rows, assignee avatars, and due-date columns',
            'an asana board with task cards in to-do, in-progress, and done columns plus a left sidebar',
            'an asana timeline view with horizontal task bars and dependency lines across a gantt chart',
            'an asana task detail panel sliding in beside a task list with subtasks and comments',
        ],
        'Bitbucket': [
            'a bitbucket repository source view with a file tree, branch selector, and clone button',
            'a bitbucket pull request page with a side-by-side code diff and a right-hand activity feed',
            'a bitbucket pipelines page listing build runs with green and red status indicators',
            'a bitbucket dashboard with a left navigation sidebar and a list of recent repositories',
        ],
        'FreshDesk': [
            'a freshdesk ticket queue in table view with priority, status, and channel columns',
            'a freshdesk ticket detail page showing the conversation thread and a right properties panel',
            'a freshdesk agent dashboard with ticket-count scorecards, sla trends, and bar charts',
            'a freshdesk inbox list of support tickets with sender names, subjects, and status badges',
        ],
        'GitHub': [
            'a github repository page with the file list, branch dropdown, and a rendered readme',
            'a github pull request with a diff view of added and removed code lines and review comments',
            'a github issues tab listing open issues with labels, assignees, and milestone tags',
            'a github actions page showing workflow runs with green checkmarks and a left job sidebar',
        ],
        'Microsoft': [
            'a microsoft.com product page with a top navigation bar, hero section, product cards, and account menu',
            'a microsoft support page with a search box, help topic cards, and troubleshooting article list',
            'a microsoft cloud dashboard page with service cards, usage charts, and a left navigation sidebar',
        ],
        'Canva': [
            'a canva home dashboard with template search, design thumbnails, recent projects, and a left navigation rail',
            'a canva editor with a design canvas, left template panel, top toolbar, and page thumbnails',
            'a canva template search results page with filter chips and grid of design templates',
        ],
        'OneNote': [
            'a onenote web window with a notebook navigation pane listing sections and pages on the left',
            'a onenote page with a free-form canvas of typed notes and a formatting ribbon on top',
            'a onenote interface with colored section tabs and a page list beside an open note',
            'a onenote notebook showing nested sections and subpages next to a checklist of notes',
        ],
        'Optimizely': [
            'an optimizely experiments dashboard listing a/b tests with status badges and conversion metrics',
            'an optimizely results page with variation comparison charts and confidence interval graphs',
            'an optimizely experiment editor with a variations panel and a webpage preview area',
            'an optimizely overview with a left navigation sidebar and a table of running experiments',
        ],
    },
    'Media': {
        'Coursera': [
            'a coursera course landing page with the title, ratings, instructor info, and an enroll button',
            'a coursera catalog grid of course cards with thumbnails, titles, and partner university logos',
            'a coursera video lesson with the player on the left and the module syllabus on the right',
            'a coursera learner dashboard showing enrolled courses with progress bars and weekly deadlines',
        ],
        'Headspace': [
            'a headspace home screen with warm rounded illustrations and recommended meditation session cards',
            'a headspace meditation player with a large circular breathing animation and minimal play controls',
            'a headspace sleep section with a dark navy background, soft stars, and sleepcast cards',
            'a headspace category grid of guided sessions sorted by duration with calm pastel illustrations',
        ],
        'Health': [
            'an apple health summary page with three colored activity rings and pinned metric cards',
            'a health app step-count screen with a bar chart of daily steps and distance totals',
            'a health dashboard showing a heart-rate line graph with resting and workout ranges',
            'a health sleep tab with stacked bars of sleep stages and time-in-bed trends',
        ],
        'Spotify': [
            'a spotify web player with the library sidebar, a playlist tracklist, and the bottom playback bar',
            'a spotify album page with large cover art, track numbers, and a green play button',
            'a spotify now-playing view showing album art, song details, and the right-side panel',
            'a spotify search page with genre tiles in colorful blocks and a top search field',
        ],
        'YouTube': [
            'a youtube home page with a grid of video thumbnails, titles, and channel avatars',
            'a youtube watch page with the player, video title, and recommended videos on the right',
            'a youtube channel page with the banner, avatar, tabs, and rows of uploaded video thumbnails',
            'a youtube shorts feed with a vertical full-screen video and side like and comment buttons',
        ],
        'Netflix': [
            'a netflix browse page with a dark hero banner, profile avatar, category rows, and movie thumbnails',
            'a netflix title detail overlay with trailer preview, play button, maturity rating, episodes, and recommendations',
            'a netflix search results page with rows of movies and shows matching the query',
        ],
        'Twitch': [
            'a twitch browse page with live stream cards, category filters, viewer counts, and left followed channels sidebar',
            'a twitch stream page with video player, live chat, stream title, channel info, and follow button',
            'a twitch category page listing live channels with thumbnails, tags, and viewer counts',
        ],
        'Bilibili': [
            'a bilibili homepage with video recommendation cards, category navigation, ranking list, and search bar',
            'a bilibili video watch page with player, danmaku controls, title, uploader info, and recommended videos',
            'a bilibili search results page with video cards, filters, view counts, and uploader names',
        ],
        'Pinterest': [
            'a pinterest home feed with masonry image pins, save buttons, topic chips, and a top search bar',
            'a pinterest search results page with image pins, filters, and related search chips',
            'a pinterest pin detail page with a large image, title, save button, comments, and related pins',
        ],
    },
    'Communication': {
        'Facebook': [
            'a facebook news feed with post cards, profile photos, and a left navigation sidebar',
            'a facebook profile page with a cover photo, avatar, and a timeline of posts',
            'a facebook groups page showing member posts and a recommendations panel',
            'a messenger window with a conversation list and colored chat bubbles',
        ],
        'Instagram': [
            'an instagram home feed with story circles, post cards, like/comment controls, and right-side suggestions',
            'an instagram profile page with avatar, bio, follower counts, story highlights, and photo grid',
            'an instagram explore page with a dense grid of reels and image posts plus a search field',
        ],
        'Reddit': [
            'a reddit home feed with subreddit posts, vote arrows, comment counts, and a right sidebar',
            'a reddit subreddit page with post list, sort tabs, community sidebar, and create post button',
            'a reddit comment thread page with nested comments, award icons, and vote controls',
        ],
        'X': [
            'an x.com timeline page with a left navigation rail, post composer, feed posts, and trends sidebar',
            'an x.com profile page with banner, avatar, posts tab, follower counts, and timeline posts',
            'an x.com search results page with tabs for top/latest/users and a scrolling list of posts',
        ],
        'TikTok': [
            'a tiktok web feed with a vertical video player, creator info, like/comment/share controls, and comments panel',
            'a tiktok search results page with video cards, user results, and filter tabs',
            'a tiktok creator profile page with avatar, follower counts, bio, and grid of videos',
        ],
        'LinkedIn': [
            'a linkedin feed page with post cards, profile summary sidebar, news panel, and navigation bar',
            'a linkedin jobs search page with job cards, filters, company names, and apply buttons',
            'a linkedin profile page with banner, experience sections, skills, and contact buttons',
        ],
        'VK': [
            'a vk.com news feed with post cards, left navigation menu, stories row, and chat sidebar',
            'a vk.com profile page with avatar, wall posts, friends module, and media thumbnails',
        ],
        'Medium': [
            'a medium article with a large headline, an author byline, and a centered single-column body',
            'a medium homepage feed listing story cards with titles, thumbnails, and tags',
            'a medium long-form blog post with an inline image and a highlighted pull quote',
            'a medium reading page with minimalist typography and ample white margins',
        ],
        'Microsoft Teams': [
            'a microsoft teams channel with a posts thread and a left teams sidebar',
            'a teams one-on-one chat pane with message bubbles and a compose box',
            'a teams video meeting showing a grid of participant tiles and call controls',
            'a teams interface with a left rail of icons, a channel list, and a message area',
        ],
        'Outlook': [
            'an outlook web inbox with a folder list, a message list, and a reading pane',
            'an outlook calendar in week view with a grid of colored events',
            'an outlook compose window with to, subject, and a rich-text body',
            'an outlook focused inbox showing email rows with sender, subject, and preview text',
        ],
        'Quora': [
            'a quora question page with the question title and stacked answers below',
            'a quora answer showing author credentials, body text, and an upvote button',
            'a quora home feed listing questions and answer cards with a left sidebar',
            'a quora q-and-a page with a bold question heading and a long answer with images',
        ],
        'Signal': [
            'a signal desktop window with a conversation list on the left and a chat on the right',
            'a signal private chat with message bubbles, timestamps, and a text input bar',
            'a signal chat list showing contact names, message previews, and unread badges',
            'a signal secure conversation with date separators and a compose field',
        ],
        'Slack': [
            'a slack workspace with a channel sidebar and a message thread',
            'a slack channel showing messages with avatars, names, and emoji reactions',
            'a slack thread panel open beside the main channel message list',
            'a slack huddle audio-call overlay with participant tiles in a workspace',
        ],
        'Zoom': [
            'a zoom meeting in gallery view with a grid of participant video tiles',
            'a zoom meeting with a large speaker view and a bottom toolbar of controls',
            'a zoom waiting-room screen telling the user the host will let them in soon',
            'a zoom call showing a screen share with a strip of participant thumbnails',
        ],
        'WhatsApp': [
            'a whatsapp web chat page with a conversation list, selected chat thread, message bubbles, and compose box',
            'a whatsapp web group chat with participant names, media previews, emoji button, and attachment controls',
        ],
        'Telegram': [
            'a telegram web chat page with chat list, selected conversation, message bubbles, and composer controls',
            'a telegram channel page with posts, reaction counts, pinned message, and right-side info panel',
        ],
        'Discord': [
            'a discord web server with channel list, message thread, member sidebar, and voice controls',
            'a discord direct message page with conversation list, chat messages, and attachment controls',
        ],
        'LiveMail': [
            'a live.com outlook mailbox page with folder sidebar, message list, reading pane, and top command bar',
            'a live.com calendar page with month grid, event cards, and Microsoft account controls',
        ],
        'MailRu': [
            'a mail.ru inbox page with folder sidebar, email rows, preview pane, and compose button',
            'a mail.ru portal homepage with search bar, mail widget, news headlines, and service icons',
        ],
    },
}

# Generic, brand-agnostic pages (kept from the original pool) so browsers still
# occasionally show non-catalog content.
WEB_GENERIC_CONTENTS = [
    'a ChatGPT conversation page with a left sidebar of past chats',
    'an arXiv research paper PDF in the built-in viewer with a page-thumbnail sidebar',
    'a Wikipedia article with section headings, an infobox, and hyperlinks',
    'a Google search results page listing blue links and snippets',
    'the Google new-tab page with a centered search box and shortcut tiles',
    'a Stack Overflow question page with an accepted answer and code blocks',
    'a documentation site with a left navigation sidebar and syntax-highlighted code blocks',
    'a news article with a headline, byline, and body paragraphs',
    'the iCloud web landing page with colorful Apple app icons and a sign-in button',
]


# Canonical landing URLs so the address bar / page brand stay mutually
# consistent. Sites absent here fall back to None (the describer then uses a
# plausible domain).
WEB_SITE_URLS = {
    'Google': 'https://www.google.com/',
    'Bing': 'https://www.bing.com/',
    'DuckDuckGo': 'https://duckduckgo.com/',
    'Yandex': 'https://yandex.com/',
    'Baidu': 'https://www.baidu.com/',
    'Naver': 'https://www.naver.com/',
    'ChatGPT': 'https://chatgpt.com/',
    'Gemini': 'https://gemini.google.com/',
    'Claude': 'https://claude.ai/new',
    'Skyscanner': 'https://www.skyscanner.com/',
    'AliExpress': 'https://www.aliexpress.com/',
    'JD': 'https://www.jd.com/',
    'Revolut': 'https://www.revolut.com/',
    'Shopee': 'https://shopee.com/',
    'Shopify': 'https://www.shopify.com/',
    'Walmart': 'https://www.walmart.com/',
    'Amazon': 'https://www.amazon.com/',
    'Temu': 'https://www.temu.com/',
    'Ebay': 'https://www.ebay.com/',
    'YahooFinance': 'https://finance.yahoo.com/',
    'MarketWatch': 'https://www.marketwatch.com/',
    'TradingView': 'https://www.tradingview.com/',
    'Samsung': 'https://www.samsung.com/',
    'Wikipedia': 'https://www.wikipedia.org/',
    'Fandom': 'https://www.fandom.com/',
    'StackOverflow': 'https://stackoverflow.com/',
    'Yahoo': 'https://www.yahoo.com/',
    'YahooJapan': 'https://www.yahoo.co.jp/',
    'NYTimes': 'https://www.nytimes.com/',
    'Globo': 'https://www.globo.com/',
    'Dzen': 'https://dzen.ru/',
    'Weather': 'https://weather.com/',
    'Airtable': 'https://www.airtable.com/',
    'Asana': 'https://www.asana.com/',
    'Bitbucket': 'https://bitbucket.org/',
    'FreshDesk': 'https://www.freshdesk.com/',
    'GitHub': 'https://github.com/',
    'Microsoft': 'https://www.microsoft.com/',
    'Canva': 'https://www.canva.com/',
    'OneNote': 'https://www.onenote.com/',
    'Optimizely': 'https://www.optimizely.com/',
    'Coursera': 'https://www.coursera.org/',
    'Headspace': 'https://www.headspace.com/',
    'Health': 'https://health.university.edu/dashboard',
    'Spotify': 'https://open.spotify.com/',
    'YouTube': 'https://www.youtube.com/',
    'Netflix': 'https://www.netflix.com/',
    'Twitch': 'https://www.twitch.tv/',
    'Bilibili': 'https://www.bilibili.com/',
    'Pinterest': 'https://www.pinterest.com/',
    'Facebook': 'https://www.facebook.com/',
    'Instagram': 'https://www.instagram.com/',
    'Reddit': 'https://www.reddit.com/',
    'X': 'https://x.com/',
    'TikTok': 'https://www.tiktok.com/',
    'LinkedIn': 'https://www.linkedin.com/',
    'VK': 'https://vk.com/',
    'Medium': 'https://medium.com/',
    'Microsoft Teams': 'https://teams.microsoft.com/',
    'Outlook': 'https://outlook.live.com/',
    'Quora': 'https://www.quora.com/',
    'Signal': 'https://web.signal.org/',
    'Slack': 'https://slack.com/',
    'Zoom': 'https://app.zoom.us/',
    'WhatsApp': 'https://web.whatsapp.com/',
    'Telegram': 'https://web.telegram.org/',
    'Discord': 'https://discord.com/',
    'LiveMail': 'https://outlook.live.com/mail/0/',
    'MailRu': 'https://mail.ru/',
}
