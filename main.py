import tkinter as tk
from tkinter import filedialog, BooleanVar
import vk_api
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
import asyncio
import os
import sys
import textwrap
import json

class VKtoTelegram:
    def __init__(self):
        self.vk_token = ""
        self.tg_token = ""
        self.tg_chat_id = ""
        self.vk_group_id = ""

    async def start(self):
        try:
            # Получаем введенные значения
            self.vk_token = self.vk_token_entry.get()
            # выделяем токен из ссылки
            self.vk_token = self.vk_token[self.vk_token.find("vk1.a."):self.vk_token.find("vk1.a.")+220]
            self.tg_token = self.tg_token_entry.get()
            self.tg_chat_id = self.tg_chat_id_entry.get()
            self.vk_group_id = self.vk_group_id_entry.get()
            if self.num_posts_entry.get() != "":
                need_posts_count = int(self.num_posts_entry.get())
            else:
                need_posts_count = None

            if self.vk_token != "" and self.tg_token != "" and self.tg_chat_id != "" and self.vk_group_id != "":
                self.root.withdraw()
            else:
                return

            # сохраняем настройки в файл
            settings = {
                'vk_token': self.vk_token,
                'tg_token': self.tg_token,
                'tg_chat_id': self.tg_chat_id,
                'vk_group_id': self.vk_group_id,
                'interval': self.time_interval_scale.get(),
                'num_posts': need_posts_count,
                'skip_first_post': self.skip_first_post_var.get()
            }
            with open('settings.json', 'w') as file:
                json.dump(settings, file)


            # Создаем экземпляр бота Telegram
            bot = Bot(token=self.tg_token)
            dp = Dispatcher(bot)

            # Авторизуемся в VK
            vk_session = vk_api.VkApi(token=self.vk_token)
            vk = vk_session.get_api()

            # Список всех постов
            all_posts = []

            # Обходим группу и получаем посты
            offset = 0

            # Получение количества постов на стене группы
            response = vk.wall.get(owner_id=f"-{self.vk_group_id}", count=0)
            post_count = response['count']
            print(f"В сообществе всего {post_count} постов")
            print("Начинаю сбор постов из группы...")
            while True:
                wall = vk.wall.get(owner_id=f"-{self.vk_group_id}", count=100, offset=offset)
                post_count = wall["count"]
                
                # Если нет постов, выходим из цикла
                if need_posts_count != None:
                    if len(all_posts) >= need_posts_count:
                        print("Посты собраны")
                        break
                if not wall["items"]:
                    print("Посты собраны")
                    break

                all_posts.extend(wall["items"])
                offset += 100
                print(f"Шаг: {offset}")

            # если нужно пропускать первый пост
            if self.skip_first_post_var.get() and len(all_posts) > 1:
                # срезаем первый пост
                all_posts = all_posts[1:]

            # делаем срез
            if need_posts_count != None:
                if len(all_posts) > need_posts_count:
                    all_posts = all_posts[:need_posts_count]


            print(f"Начинаю публикацию постов ({len(all_posts)})")
            counter = 1
            # Постим каждый пост в Telegram, начиная с конца списка
            for post in reversed(all_posts):

                # print(f"{post}\n\n\n") # ДЛЯ ОТЛАДКИ
                try:
                    text = post["text"]
                    # проверяем, репост-ли это, или публикация
                    if "copy_history" in post:
                        for attachments_search in post.get("copy_history", []):
                            if "attachments" in attachments_search:
                                attachments = attachments_search.get("attachments", [])

                        if len(post["copy_history"]) > 0:
                            if "text" in post["copy_history"][0]:
                                if post["copy_history"][0]["text"]:
                                    text += f'\n{post["copy_history"][0]["text"]}'
                    else:
                        attachments = post.get("attachments", [])
                    # print(attachments)
                    media = []
                    # Создаем сообщение с медиафайлами и текстом
                    message = text

                    for attachment in attachments:
                        if attachment["type"] == "photo":
                            sizes = attachment["photo"]["sizes"]
                            photo_url = sizes[-1]["url"]
                            media.append(types.InputMediaPhoto(media=photo_url))

                        elif attachment["type"] == "video":
                            video_url = f'https://vk.com/video_ext.php?oid={attachment["video"]["owner_id"]}&id={attachment["video"]["id"]}&hash={post["hash"]}'
                            text += f'\n📺{video_url} {attachment["video"]["title"]}'
                            # Поиск превью с максимальным разрешением
                            max_resolution = 0
                            for key in attachment["video"]:
                                if key.startswith('photo_'):
                                    resolution = int(key.split('_')[1])
                                    if resolution > max_resolution:
                                        max_resolution = resolution
                                        max_resolution_url = attachment["video"][f"photo_{resolution}"]
                            if max_resolution_url:
                                media.append(types.InputMediaPhoto(media=max_resolution_url))
                        elif attachment["type"] == "audio":
                            audio_name = f'\n🎵 {attachment["audio"]["artist"]} - {attachment["audio"]["title"]}'
                            text += f"{audio_name}"
                        # elif attachment
                        elif attachment["type"] == "link":
                            try:
                                index = 0
                                max_width = 0
                                for img in attachment["link"]["photo"]["sizes"]:
                                    if img["width"] > max_width:
                                        max_width = img["width"]
                                        photo_url = attachment["link"]["photo"]["sizes"][index]["url"]
                                    index += 1

                                media.append(types.InputMediaPhoto(media=photo_url))
                            except:
                                print("Не обнаружено прикреплённого изображения!")
                            link_url = attachment["link"]["url"]
                            if link_url not in text:
                                text += f"\n{link_url}"

                    if not text and media == []:
                        print("Не обнаружено контента в посте...")
                        continue
                    first_msg = True
                    # Разбиваем сообщение на несколько частей
                    message_parts = textwrap.wrap(text, width=1024, replace_whitespace=False)
                    # Если не обнаружено текстового сообщения
                    if message_parts == []:
                        await bot.send_media_group(chat_id=self.tg_chat_id, media=media)

                    for part in message_parts:
                        if first_msg == True and media != []:
                            # Отправляем все медиа-объекты в одном сообщении
                            media[0].caption = part
                            await bot.send_media_group(chat_id=self.tg_chat_id, media=media)
                            first_msg = False
                        else:
                            await bot.send_message(chat_id=self.tg_chat_id, text=part, parse_mode="HTML")
                        await asyncio.sleep(3)  # Добавляем небольшую задержку между отправкой частей сообщения

                    # Добавляем задержку
                    print(f"Опубликовано: {counter}/{len(all_posts)}")
                    counter+=1
                    await asyncio.sleep(self.time_interval_scale.get())
                except Exception as error:
                    print(f"Не удалось опубликовать пост! {error}\nПропускаем...")
        except Exception as error:
            print(f"Возникла ошибка: {error}")
        finally:
            self.root.deiconify()

    def load_settings(self):
        try:
            with open('settings.json', 'r') as file:
                settings = json.load(file)
                self.vk_token_entry.insert(0, settings['vk_token'])
                self.tg_token_entry.insert(0, settings['tg_token'])
                self.tg_chat_id_entry.insert(0, settings['tg_chat_id'])
                self.vk_group_id_entry.insert(0, settings['vk_group_id'])
                self.time_interval_scale.set(settings['interval'])
                self.num_posts_entry.insert(0, settings['num_posts'])
                self.skip_first_post_var.set(settings['skip_first_post'])
        except Exception as error:
            print(error)

    def run(self):
        # Создаем графический интерфейс с помощью tkinter
        self.root = tk.Tk()
        self.root.title("VK2TG Poster")
        self.root.geometry("400x400")

        #пытаюсь установить иконку
        try:
            try:
                base_path = sys._MEIPASS
            except Exception:
                base_path = os.path.abspath(".")
            self.root.wm_iconbitmap(os.path.join(base_path, "icon.ico"))
        except:
            print("Не удалось установить иконку приложения")

        # Label для токена ВК
        vk_token_label = tk.Label(self.root, text="Токен ВК")
        vk_token_label.pack(fill="both")
        self.vk_token_entry = tk.Entry(self.root)
        self.vk_token_entry.pack(fill="both", padx=3)

        # Label для токена ТГ
        tg_token_label = tk.Label(self.root, text="Токен ТГ")
        tg_token_label.pack(fill="both")
        self.tg_token_entry = tk.Entry(self.root)
        self.tg_token_entry.pack(fill="both", padx=3)

        # Label для id бота ТГ
        tg_chat_id_label = tk.Label(self.root, text="id бота ТГ")
        tg_chat_id_label.pack(fill="both")
        self.tg_chat_id_entry = tk.Entry(self.root)
        self.tg_chat_id_entry.pack(fill="both", padx=3)

        # Label для id группы ВК
        vk_group_id_label = tk.Label(self.root, text="id группы ВК")
        vk_group_id_label.pack(fill="both")
        self.vk_group_id_entry = tk.Entry(self.root)
        self.vk_group_id_entry.pack(fill="both", padx=3)

        # Scale для интервалов времени
        time_interval_label = tk.Label(self.root, text="Интервалы времени между публикациями (секунды)")
        time_interval_label.pack(fill="both")
        self.time_interval_scale = tk.Scale(self.root, from_=5, to=3600, orient="horizontal")
        self.time_interval_scale.pack(fill="both")

        # Entry для количества постов
        num_posts_label = tk.Label(self.root, text="Сколько постов нужно опубликовать\nесли не указано - будут опубликованы ВСЕ посты")
        num_posts_label.pack(fill="both")
        self.num_posts_entry = tk.Entry(self.root)
        self.num_posts_entry.pack(fill="both", padx=3)

        # Checkbox для пропуска первого поста
        self.skip_first_post_var = tk.BooleanVar(value=True)
        self.skip_first_post_checkbox = tk.Checkbutton(self.root, text="Пропускать первый пост", variable=self.skip_first_post_var)
        self.skip_first_post_checkbox.pack(fill="both")


        # Кнопка старта
        self.start_button = tk.Button(self.root, text="СТАРТ", bg="lightgreen", height=2, command=lambda: asyncio.run(self.start()))
        self.start_button.pack(fill="both", side="bottom", padx=3, pady=3)

        # загружаем настройки из файла
        self.load_settings()

        # Запускаем графический интерфейс
        self.root.mainloop()



# Создаем экземпляр класса и запускаем программу
vk_to_tg = VKtoTelegram()
vk_to_tg.run()
