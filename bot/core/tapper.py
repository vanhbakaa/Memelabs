import asyncio
import traceback
from itertools import cycle
from time import time
from urllib.parse import unquote
import aiohttp
import requests
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.types import InputBotAppShortName
from pyrogram.raw.functions.messages import RequestAppWebView
from bot.core.agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from random import randint
import random
from datetime import datetime, timezone
import os
from bot.utils.ps import check_base_url
import base64

def generate_ws_key():
    random_bytes = os.urandom(16)
    ws_key = base64.b64encode(random_bytes).decode('utf-8')
    return ws_key

end_point = "https://api.memeslab.xyz/"
api_login = f"{end_point}auth/login"
user_api = f"{end_point}auth/verify-token"
task_list = f"{end_point}claims/task-group/list"
bonus_api = f"{end_point}claims/info"
claim_api = f"{end_point}claims/process"
priority_tasks_api = f"{end_point}claims/task-group/priority-tasks"
memes_api = f"{end_point}meme?page=1&limit=50"
user_memes_api = f"{end_point}users/memes?page=1&limit=10"
api_buy_meme = f"{end_point}meme/"
task_in_group_api = f"{end_point}claims/task/list"
start_task = f"{end_point}claims/task/start"
mine_api = f"{end_point}mine"
claim_ticker_api = f"{end_point}claims/ticker"

class Tapper:
    def __init__(self, tg_client: Client, multi_thread: bool):
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.first_name = ''
        self.last_name = ''
        self.user_id = ''
        self.auth_token = ""
        self.multi_thread = multi_thread
        self.access_token = None
        self.balance = 0
        self.my_ref = "2YFTB2"

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if settings.REF_LINK == '':
            ref_param = "2YFTB2"
        else:
            ref_param = settings.REF_LINK.split('=')[1]
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict
        actual = random.choices([self.my_ref, "UG1LIX", ref_param], weights=[20, 10, 70], k=1)

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('MemesLabBot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"<light-yellow>{self.session_name}</light-yellow> | FloodWait {fl}")
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Sleep {fls}s")

                    await asyncio.sleep(fls + 3)

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotAppShortName(bot_id=peer, short_name="MemesLab"),
                platform='android',
                write_allowed=True,
                start_param=actual[0]
            ))

            auth_url = web_view.url
            tg_web_data = unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: "
                         f"{error}")
            await asyncio.sleep(delay=3)

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://ipinfo.io/json', timeout=aiohttp.ClientTimeout(20))
            response.raise_for_status()

            response_json = await response.json()
            ip = response_json.get('ip', 'NO')
            country = response_json.get('country', 'NO')

            logger.info(f"{self.session_name} |🟩 Logging in with proxy IP {ip} and country {country}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

    async def login(self, http_client: aiohttp.ClientSession):
        try:
            login = await http_client.post(f"{api_login}?{self.auth_token}")
            if login.status == 201:
                res = await login.json()
                # print(res)
                self.access_token = res['api_token']
                logger.success(f"{self.session_name} | <green>Successfully logged in!</green>")
                return True
            else:
                print(await login.text())
                logger.warning(f"{self.session_name} | <yellow>Failed to login: {login.status}</yellow>")
                return False
        except Exception as e:
            traceback.print_exc()
            logger.error(f"{self.session_name} | Unknown error while trying to login: {e}")
            return False

    async def get_user_info(self, http_client: aiohttp.ClientSession):
        try:
            user = await http_client.get(user_api)
            await asyncio.sleep(random.uniform(0.1,0.3))
            user = await http_client.get(user_api)
            if user.status == 200:
                res = await user.json()
                return res
            else:
                logger.warning(f"{self.session_name} | <yellow>Failed to get user info: {user.status}</yellow>")
                return None
        except Exception as e:
            logger.error(f"{self.session_name} | Unknown error while trying to get user info: {e}")
            return None

    async def handle_websocket(self, http_client: aiohttp.ClientSession, proxy, stop_event):
        uri = "wss://socket.memeslab.xyz/socket.io/?EIO=4&transport=websocket"
        headerss = {
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en,en-US;q=0.9,vi;q=0.8",
            "Cache-Control": "no-cache",
            "Host": "socket.memeslab.xyz",
            "Origin": "https://game.memeslab.xyz",
            "Pragma": "no-cache",
            "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
            "Sec-WebSocket-Key": f"{generate_ws_key()}",
            "Sec-WebSocket-Version": "13",
            "Upgrade": "websocket",
            "User-Agent": f"{http_client.headers['User-Agent']}"
        }

        async with aiohttp.ClientSession(headers=headerss) as session:
            async with session.ws_connect(uri, proxy=proxy) as websocket:
                logger.success(f"{self.session_name} | Connected to WebSocket server!")

                # Listen for messages
                while not stop_event.is_set():
                    try:
                        msg = await websocket.receive(timeout=1)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            # print(f"Received message: {msg.data}")
                            if msg.data.startswith("0{"):
                                payload = "40{" + '"token":' +f'"{self.access_token}"' + "}"
                                await websocket.send_str(payload)
                                # print(f"sent payload data: {payload}")

                            if msg.data == "2":
                                await websocket.send_str("3")
                                # print("Sent message: 3")
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            logger.warning(f"{self.session_name} | Connection closed by server")
                            break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.warning(f"{self.session_name} | Error in WebSocket connection")
                            break

                    except asyncio.TimeoutError:
                        pass
        logger.info(f"{self.session_name} | Closing ws connection...")
        await websocket.close()

    async def get_ref(self, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Getting ref info...")
            res = await http_client.get("https://api.memeslab.xyz/users/referrals?undefined")
            if res.status == 200:
                return True
            else:
                return None
        except:
            return None

    async def get_tasks(self, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Getting tasks list...")
            res = await http_client.get(task_list)
            if res.status == 200:
                data = await res.json()
                return data['data']
            else:
                return None
        except:
            return None

    async def get_bonus(self, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Getting bonus info...")
            res = await http_client.get(bonus_api)
            if res.status == 200:
                data = await res.json()
                return data
            else:
                return None
        except:
            return None

    async def claim(self, http_client: aiohttp.ClientSession, name, dayrw: int | None):
        try:
            logger.info(f"{self.session_name} | claiming {name}...")
            if dayrw is None:
                payload = {
                    "type": f"{name}"
                }
            else:
                payload = {
                    "type": f"{name}",
                    "day": int(dayrw)
                }
            res = await http_client.post(claim_api, json=payload)
            if res.status == 201:
                logger.success(f"{self.session_name} | <green>Successfully claimed <cyan>{name}</cyan></green>")
                return True
            else:
                return None
        except:
            return None

    async def get_priority_tasks(self,  http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Getting priority tasks...")
            res = await http_client.get(priority_tasks_api)
            if res.status == 200:
                return True
            else:
                return None
        except:
            return None

    async def get_memes(self,  http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Getting memes...")
            res = await http_client.get(memes_api)
            if res.status == 200:
                data = await res.json()
                return data['data']
            else:
                return None
        except:
            return None

    async def get_user_memes(self,  http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Getting user memes...")
            res = await http_client.get(user_memes_api)
            if res.status == 200:
                data = await res.json()
                return data
            else:
                return None
        except:
            return None

    async def buy_random_memes(self, http_client: aiohttp.ClientSession, memes):
        meme_to_buy = random.choice(memes)
        try:
            logger.info(f"{self.session_name} | Buying {meme_to_buy['key']} meme...")
            res = await http_client.post(f"{api_buy_meme}{meme_to_buy['key']}", json={})
            if res.status == 201:
                data = await res.json()
                logger.success(f"{self.session_name} | <green>Successfully bought <yellow>{meme_to_buy['key']}</yellow> meme!</green>")
                return data
            else:
                return None
        except:
            return None

    async def get_tasks_in_group(self, groupId, groupName, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Getting task list in <cyan>{groupName}</cyan> ...")
            res = await http_client.get(f"{task_in_group_api}?taskGroupId={groupId}")
            if res.status == 200:
                data = await res.json()
                return data['data']
            else:
                return None
        except:
            return None

    async def start_task(self, key, name, http_client: aiohttp.ClientSession):
        try:
            payload = {
                "key": key
            }
            logger.info(f"{self.session_name} | Starting task <cyan>{name}</cyan> ...")
            res = await http_client.post(start_task, json=payload)
            if res.status == 201:
                data = await res.json()
                logger.success(f"{self.session_name} | <green>Successfully started task: <cyan>{name}</cyan></green>")
                return data
            else:
                return None
        except:
            return None

    async def claim_task(self, key, name, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | claiming task: <cyan>{name}</cyan>...")
            payload = {
                "type": f"TASK",
                "key": key
            }
            res = await http_client.post(claim_api, json=payload)
            if res.status == 201:
                logger.success(f"{self.session_name} | <green>Successfully claimed task: <cyan>{name}</cyan></green>")
                return True
            else:
                return None
        except:
            return None

    async def get_mine(self, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Getting mine data...")
            res = await http_client.get(mine_api)
            if res.status == 200:
                data = await res.json()
                return data['data']
            else:
                return None
        except:
            return None

    async def upgrade(self, card, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Attempt to upgrade: <cyan>{card['name']}</cyan>...")
            payload = {
                "mineItemId": card['_id']
            }
            res = await http_client.post(mine_api, json=payload)
            if res.status == 201:
                data = await res.json()
                logger.success(f"{self.session_name} | <green>Successfully upgraded: <cyan>{card['name']}</cyan> to lvl: <red>{data['userLevel']}</red></green>")
                return True
            else:
                return None
        except:
            traceback.print_exc()
            return None

    async def claim_cipher(self, text, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Attempt to claim cipher...")
            payload = {
                "text": text
            }
            res = await http_client.post(claim_ticker_api, json=payload)
            if res.status == 201:
                data = await res.json()
                logger.success(f"{self.session_name} | <green>Successfully claimed daily cipher, reward: <cyan>{data['rewards']}</cyan></green>")
                return True
            else:
                return None
        except:
            return None
    async def main_task(self, http_client: aiohttp.ClientSession, stop_event):
        try:
            user = await self.get_user_info(http_client)
            if user is None:
                stop_event.set()
                return

            new_account = False
            self.balance = int(user['balance'])
            user_info = f"""
            ===<cyan>{self.session_name}</cyan>===
            Balance: <light-green>{user['balance']}</light-green>
            Daily streak: <red>{user['dailyRewardsDays']}</red>
            Referred User count: <yellow>{user['referredUserCount']}</yellow>
            Total fight won: <light-green>{user['totalFightWon']}</light-green>
            """
            logger.info(f"{user_info}")

            check = await self.get_ref(http_client)
            if check is None:
                logger.warning(f"{self.session_name} | <yellow>Something went wrong while getting ref info, aborting...</yellow>")
                stop_event.set()
                return

            tasks = await self.get_tasks(http_client)
            if tasks is None:
                logger.warning(f"{self.session_name} | <yellow>Something went wrong while getting tasks list, aborting...</yellow>")
                stop_event.set()
                return

            bonus_info = await self.get_bonus(http_client)
            # print(bonus_info)
            if bonus_info is None:
                logger.warning(f"{self.session_name} | <yellow>Something went wrong while getting bonus info, aborting...</yellow>")
                stop_event.set()
                return

            if bonus_info['welcomeBonusRewarded'] is False:
                c = await self.claim(http_client, "WELCOME", None)
                if c is None:
                    logger.warning(
                        f"{self.session_name} | <yellow>Something went wrong while getting claiming bonus, aborting...</yellow>")
                    stop_event.set()
                    return
                new_account = True

            daily_rw = bonus_info['daiy'].keys()
            if "dailyRewardsUnlockedAt" not in daily_rw:
                dayrw = bonus_info['daiy']['daysRewarded']
                await self.claim(http_client, "DAILY_REWARDS", dayrw)
                bonus_info = await self.get_bonus(http_client)
                self.balance = bonus_info['balance']
                logger.info(f"{self.session_name} | Balance: <cyan>{self.balance}</cyan>")

            if bonus_info['mine']['accumulatedMinedReward'] > 0:
                a = await self.claim(http_client, "MINE", None)
                if a:
                    logger.success(f"{self.session_name} | <green>Successfully claimed <cyan>{bonus_info['mine']['accumulatedMinedReward']}</cyan> from mine!</green>")
                bonus_info = await self.get_bonus(http_client)
                self.balance = bonus_info['balance']
                logger.info(f"{self.session_name} | Balance: <cyan>{self.balance}</cyan>")

            priority_tasks = await self.get_priority_tasks(http_client)
            if priority_tasks is None:
                logger.warning(
                    f"{self.session_name} | <yellow>Something went wrong while getting priority tasks, aborting...</yellow>")
                stop_event.set()
                return

            memes = await self.get_memes(http_client)
            if memes is None:
                logger.warning(
                    f"{self.session_name} | <yellow>Something went wrong while getting memes, aborting...</yellow>")
                stop_event.set()
                return

            user_memes = await self.get_user_memes(http_client)
            if user_memes is None:
                logger.warning(
                    f"{self.session_name} | <yellow>Something went wrong while getting user memes, aborting...</yellow>")
                stop_event.set()
                return

            if new_account or user_memes['primaryMeme'] is None:
                bought_meme = await self.buy_random_memes(http_client, memes)
                if bought_meme is None:
                    logger.warning(
                        f"{self.session_name} | <yellow>Something went wrong while buying meme, aborting...</yellow>")
                    stop_event.set()
                    return
                user_memes = await self.get_user_memes(http_client)

            logger.info(f"{self.session_name} | Primary meme: <cyan>{user_memes['primaryMeme']['name']}</cyan>")

            if settings.AUTO_CIPHER:
                timestamp_str = bonus_info['ticker']['dailyTickerRewardsUnlockedAt']
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if timestamp > now:
                    logger.info(f"{self.session_name} | Not time to claim daily cipher!")
                else:
                    cipher = requests.get("https://raw.githubusercontent.com/vanhbakaa/nothing/refs/heads/main/memelabs")
                    text = cipher.text.strip()
                    claim = await self.claim_cipher(text, http_client)
                    if claim is None:
                        logger.warning(f"{self.session_name} | <yellow>Failed to claim cipher!</yellow>")

            if settings.AUTO_TASK:
                tasks = await self.get_tasks(http_client)
                if tasks is None:
                    logger.warning(
                        f"{self.session_name} | <yellow>Something went wrong while getting tasks list, aborting...</yellow>")
                    stop_event.set()
                    return
                for taskGroup in tasks:
                    taskInGroupList = await self.get_tasks_in_group(taskGroup['_id'], taskGroup['name'], http_client)
                    if taskInGroupList is None:
                        continue
                    for task in taskInGroupList:
                        if task['type'] == "WalletExchangeTask" or task['type'] == "TelegramChannelTask" or task['type'] == "ReferralTask" or task['type'] == "TelegramGroupTask":
                            continue
                        if task['isActive']:
                            if task['isCompleted'] is False:
                                do_task = await self.start_task(task['key'], task['name'], http_client)
                                if do_task is None:
                                    logger.warning(f"{self.session_name} | <yellow>Failed to start task: <red>{task['name']}</red></yellow>")
                                    continue
                                await asyncio.sleep(random.randint(2, 5))
                            elif task['isCompleted'] and task['isRewarded'] is False:
                                claim_taskss = await self.claim_task(task['key'], task['name'], http_client)
                                if claim_taskss is None:
                                    logger.warning(f"{self.session_name} | <yellow>Failed to claim task: <red>{task['name']}</red></yellow>")
                                    continue
                                await asyncio.sleep(random.randint(2, 5))

            if settings.AUTO_UPGRADE:
                mine_data = await self.get_mine(http_client)
                if mine_data:
                    can_upgrade = True
                    upgrade_others = []
                    while can_upgrade:
                        mine_data = await self.get_mine(http_client)
                        if mine_data is None:
                            break
                        bonus_info = await self.get_bonus(http_client)
                        self.balance = int(bonus_info['balance'])
                        logger.info(f"{self.session_name} | Balance: <cyan>{self.balance}</cyan>")
                        avaiable_card = []
                        upgrade_others = []
                        for card in mine_data:
                            if card['userLevel'] >= card['maxLevel']:
                                continue
                            if card['userLevel'] == 0:
                                user_lvl = str(card['userLevel']+1)
                            else:
                                user_lvl = str(card['userLevel'])
                            if int(card["levelToAmountMap"][user_lvl]) <= self.balance:
                                if "levelToRewardPerSecondMap" in card['config'].keys():
                                    profit_per_hour = card['config']['levelToRewardPerSecondMap'][user_lvl]*3600
                                    profit = card["levelToAmountMap"][user_lvl]/profit_per_hour
                                    avaiable_card.append({profit: card})
                                else:
                                    upgrade_others.append(card)
                        if len(avaiable_card) == 0:
                            can_upgrade = False
                            logger.info(f"{self.session_name} | Nothing to upgrade!")
                        else:
                            avaiable_card.sort(key=lambda x: next(iter(x)))
                            first_element = avaiable_card[0]
                            card_data = list(first_element.values())[0]
                            a = await self.upgrade(card_data, http_client)
                            if a is None:
                                logger.warning(f"{self.session_name} | Failed to upgrade {card_data['name']}")
                                can_upgrade = False
                            await asyncio.sleep(random.randint(3, 8))

                    for card in upgrade_others:
                        await self.upgrade(card, http_client)
                        bonus_info = await self.get_bonus(http_client)
                        self.balance = bonus_info['balance']
                        logger.info(f"{self.session_name} | Balance: <cyan>{self.balance}</cyan>")
                        await asyncio.sleep(random.randint(3, 8))


                else:
                    logger.warning(f"{self.session_name} | <yellow>Failed to get mine data!</yellow>")


            stop_event.set()

        except Exception as e:
            traceback.print_exc()
            logger.error(f"{self.session_name} | <red>Unknown error: {e}</red>")
            stop_event.set()
            return
    async def run(self, proxy: str | None) -> None:
        access_token_created_time = 0
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            proxy_check = await self.check_proxy(http_client=http_client, proxy=proxy)
            if proxy_check:
                logger.info(f"{self.session_name} | bind with proxy ip: {proxy}")

        token_live_time = randint(5000, 7000)
        while True:
            can_run = True
            try:
                if check_base_url() is False:
                    can_run = False
                    if settings.ADVANCED_ANTI_DETECTION:
                        logger.warning(
                            "<yellow>Detected index js file change. Contact me to check if it's safe to continue: https://t.me/vanhbakaaa</yellow>")
                    else:
                        logger.warning(
                            "<yellow>Detected api change! Stopped the bot for safety. Contact me here to update the bot: https://t.me/vanhbakaaa</yellow>")

                if can_run:
                    if time() - access_token_created_time >= token_live_time:
                        tg_web_data = await self.get_tg_web_data(proxy=proxy)
                        self.auth_token = tg_web_data
                        access_token_created_time = time()
                        token_live_time = randint(5000, 7000)

                    a = await self.login(http_client)

                    if a:
                        http_client.headers['Authorization'] = f"Bearer {self.access_token}"
                        stop_event = asyncio.Event()
                        await asyncio.gather(
                            self.main_task(http_client, stop_event),
                            self.handle_websocket(http_client,proxy,stop_event)
                        )

                if self.multi_thread:
                    sleep_ = randint(settings.DELAY_EACH_ROUND[0], settings.DELAY_EACH_ROUND[1])
                    logger.info(f"{self.session_name} | Sleep {sleep_} seconds...")
                    await asyncio.sleep(sleep_)
                else:
                    await http_client.close()
                    break

            except InvalidSession as error:
                raise error

            except Exception as error:
                #traceback.print_exc()
                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=randint(60, 120))

async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        sleep_ = randint(1, 15)
        logger.info(f"{tg_client.name} | start after {sleep_}s")
        await asyncio.sleep(sleep_)
        await Tapper(tg_client=tg_client, multi_thread=True).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")

async def run_tapper1(tg_clients: list[Client], proxies):
    proxies_cycle = cycle(proxies) if proxies else None
    while True:
        for tg_client in tg_clients:
            try:
                await Tapper(tg_client=tg_client, multi_thread=False).run(next(proxies_cycle) if proxies_cycle else None)
            except InvalidSession:
                logger.error(f"{tg_client.name} | Invalid Session")

            sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
            logger.info(f"Sleep {sleep_}s...")
            await asyncio.sleep(sleep_)

        sleep_ = randint(settings.DELAY_EACH_ROUND[0], settings.DELAY_EACH_ROUND[1])
        logger.info(f"<red>Sleep {sleep_}s...</red>")
        await asyncio.sleep(sleep_)
