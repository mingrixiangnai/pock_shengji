from astrbot.api.all import *
import random
import requests
import os
import time
import shutil
import yaml

@register("astrbot_plugin_pock_shengji", "mingrixiangnai", "戳一戳升级版", "1.0", "https://github.com/mingrixiangnai/pock_shengji")
class PokeMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_poke_timestamps = {}
        
        # 第一步：初始化所有配置属性的默认值
        # 这样即使配置文件读取失败，也能确保有合理的默认值
        self.poke_responses = [
            "别戳啦，再戳就高潮啦~！<(－︿－)>",
            "屁股都开花了还戳，我操你妈！",
            "别戳啦~！小豆豆好痒，感觉要长勾八了~",
            "哎呀，别戳啦，出淫水啦<(－︿－)>",
            "哎呀，还戳呀，逼都被戳烂了啦（＃￣～￣＃）",
            "别戳我啦，你要做什么！都喷水啦！！(ノω<。)ノ))☆"
        ]
        self.emoji_url_mapping = {
            "咬": "https://api.lolimi.cn/API/face_suck/api.php",
            "捣": "https://api.lolimi.cn/API/face_pound/api.php",
            "玩": "https://api.lolimi.cn/API/face_play/api.php",
            "拍": "https://api.lolimi.cn/API/face_pat/api.php",
            "丢": "https://api.lolimi.cn/API/diu/api.php",
            "撕": "https://api.lolimi.cn/API/si/api.php",
            "爬": "https://api.lolimi.cn/API/pa/api.php"
        }
        self.random_emoji_trigger_probability = 0.5
        self.feature_switches = {
            "poke_response_enabled": True,
            "poke_back_enabled": True,
            "emoji_trigger_enabled": True,
            "local_image_enabled": True
        }
        self.poke_back_probability = 0.5
        self.super_poke_probability = 0.1
        self.local_image_probability = 0.6
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.gif']  # 支持的图片格式

        # 配置文件路径
        config_dir = os.path.join("data", "plugins", "astrbot_plugin_pock")
        config_path = os.path.join(config_dir, "config.yml")

        # 第二步：创建默认配置文件（如果不存在）
        if not os.path.exists(config_path):
            self._create_default_config(config_path)
        
        # 第三步：尝试加载配置文件
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
                
            # 安全更新配置项，确保即使部分配置缺失也能正常工作
            self.poke_responses = config_data.get('poke_responses', self.poke_responses)
            self.emoji_url_mapping = config_data.get('emoji_url_mapping', self.emoji_url_mapping)
            self.random_emoji_trigger_probability = config_data.get(
                'random_emoji_trigger_probability', 
                self.random_emoji_trigger_probability
            )
            # 功能开关配置
            self.feature_switches = {
                **self.feature_switches,  # 默认值
                **config_data.get('feature_switches', {})  # 自定义值
            }
            self.poke_back_probability = config_data.get(
                'poke_back_probability', 
                self.poke_back_probability
            )
            self.super_poke_probability = config_data.get(
                'super_poke_probability', 
                self.super_poke_probability
            )
            self.local_image_probability = config_data.get(
                'local_image_probability', 
                self.local_image_probability
            )
        except Exception as e:
            # 即使配置文件加载失败，也不会影响程序运行
            # 设置合理的默认值
            print(f"配置文件加载失败，使用默认配置: {str(e)}")

        # 第四步：初始化图片目录
        self._init_image_directory()

    def _create_default_config(self, config_path):
        """创建包含所有配置项的默认配置文件"""
        default_config = {
            "poke_responses": self.poke_responses,
            "emoji_url_mapping": self.emoji_url_mapping,
            "random_emoji_trigger_probability": self.random_emoji_trigger_probability,
            "feature_switches": self.feature_switches,
            "poke_back_probability": self.poke_back_probability,
            "super_poke_probability": self.super_poke_probability,
            "local_image_probability": self.local_image_probability
        }
        config_dir = os.path.dirname(config_path)
        os.makedirs(config_dir, exist_ok=True)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            print(f"创建默认配置文件失败: {str(e)}")

    def _init_image_directory(self):
        """创建图片存储目录（如果不存在）"""
        self.image_dir = os.path.join("data", "plugins", "astrbot_plugin_pock", "poke_monitor")
        os.makedirs(self.image_dir, exist_ok=True)
        
    def _get_random_image(self):
        """从图片目录随机获取一个有效图片路径"""
        try:
            # 获取所有图片文件并过滤非图片文件
            all_files = [
                f for f in os.listdir(self.image_dir)
                if os.path.splitext(f)[1].lower() in self.image_extensions
                and os.path.isfile(os.path.join(self.image_dir, f))
            ]
            
            if not all_files:
                return None
                
            selected_file = random.choice(all_files)
            return os.path.join(self.image_dir, selected_file)
        except Exception as e:
            return None

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        message_obj = event.message_obj
        raw_message = message_obj.raw_message
        is_super = False

        # 戳一戳事件处理
        if raw_message.get('post_type') == 'notice' and \
                raw_message.get('notice_type') == 'notify' and \
                raw_message.get('sub_type') == 'poke':
            bot_id = raw_message.get('self_id')
            sender_id = raw_message.get('user_id')
            target_id = raw_message.get('target_id')

            now = time.time()
            three_minutes_ago = now - 3 * 60

            # 清理旧记录（保持最近3分钟内的戳一戳记录）
            if sender_id in self.user_poke_timestamps:
                self.user_poke_timestamps[sender_id] = [
                    t for t in self.user_poke_timestamps[sender_id] if t > three_minutes_ago
                ]

            if bot_id and sender_id and target_id:
                # 用户戳机器人时的处理
                if str(target_id) == str(bot_id):
                    # 记录戳一戳
                    if sender_id not in self.user_poke_timestamps:
                        self.user_poke_timestamps[sender_id] = []
                    self.user_poke_timestamps[sender_id].append(now)
                    
                    # 本地图片回复功能
                    if (self.feature_switches.get('local_image_enabled', True) and 
                        random.random() < self.local_image_probability):
                        
                        image_path = self._get_random_image()
                        
                        if image_path and os.path.exists(image_path):
                            try:
                                yield event.image_result(image_path)
                            except Exception as e:
                                yield event.plain_result("图片发送失败啦~ (；´д｀)ゞ")
                        else:
                            # 没有图片时改为文本回复
                            yield event.plain_result("傻逼，没有图片发送 (´・ω・`)")
                    
                    # 文本回复功能
                    if self.feature_switches.get('poke_response_enabled', True):
                        poke_count = len(self.user_poke_timestamps[sender_id])
                        if poke_count < 4:
                            response = self.poke_responses[poke_count - 1] if poke_count <= len(self.poke_responses) else self.poke_responses[-1]
                            yield event.plain_result(response)

                    # 戳回功能
                    if self.feature_switches.get('poke_back_enabled', True) and random.random() < self.poke_back_probability:
                        if random.random() < self.super_poke_probability:
                            poke_times = 10
                            yield event.plain_result("操你妈你再戳一次？（｀へ´）")
                            is_super = True
                        else:
                            poke_times = 1
                            yield event.plain_result("戳你的屁股<)。(>")

                        # 发送戳一戳
                        if event.get_platform_name() == "aiocqhttp":
                            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                            assert isinstance(event, AiocqhttpMessageEvent)
                            client = event.bot
                            group_id = raw_message.get('group_id')
                            payloads = {"user_id": sender_id}
                            if group_id:
                                payloads["group_id"] = group_id
                            for _ in range(poke_times):
                                try:
                                    await client.api.call_action('send_poke', **payloads)
                                except Exception as e:
                                    pass

                # 用户戳其他人的处理
                elif str(sender_id) != str(bot_id):
                    # 随机触发表情包
                    if self.feature_switches.get('emoji_trigger_enabled', True) and random.random() < self.random_emoji_trigger_probability:
                        available_actions = list(self.emoji_url_mapping.keys())
                        selected_action = random.choice(available_actions)

                        url = self.emoji_url_mapping.get(selected_action)
                        params = {'QQ': target_id}

                        # 硬编码请求配置
                        timeout = 10
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                response = requests.get(url, params=params, timeout=timeout)
                                if response.status_code == 200:
                                    save_dir = os.path.join("data", "plugins", "astrbot_plugin_pock", "poke_monitor")
                                    os.makedirs(save_dir, exist_ok=True)

                                    filename = f"{selected_action}_{target_id}_{int(time.time())}.gif"
                                    image_path = os.path.join(save_dir, filename)

                                    with open(image_path, "wb") as f:
                                        f.write(response.content)
                                    yield event.image_result(image_path)

                                    # 发送后删除临时图片
                                    if os.path.exists(image_path):
                                        try:
                                            os.remove(image_path)
                                        except Exception as e:
                                            pass
                                    break
                                else:
                                    yield event.plain_result(f"表情包请求失败，状态码：{response.status_code}")
                                    break
                            except requests.exceptions.ReadTimeout:
                                retry_count += 1
                                if retry_count == max_retries:
                                    yield event.plain_result(f"表情包处理出错：多次请求超时，无法获取数据。")
                            except Exception as e:
                                yield event.plain_result(f"表情包处理出错：{str(e)}")
                                break