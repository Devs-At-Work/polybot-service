import telebot
from loguru import logger
import os
import requests
from collections import Counter
# import openai
import ffmpeg

YOLO_URL = f'http://yolo5-service:8081'


class Bot:

    def __init__(self, token):
        self.bot = telebot.TeleBot(token, threaded=False)
        self.bot.set_update_listener(self._bot_internal_handler)

        self.current_msg = None

    def _bot_internal_handler(self, messages):
        """Bot internal messages handler"""
        for message in messages:
            self.current_msg = message
            self.handle_message(message)

    
    def start(self):
        """Start polling msgs from users, this function never returns"""
        logger.info(f'{self.__class__.__name__} is up and listening to new messages....')
        logger.info(f'Telegram Bot information\n\n{self.bot.get_me()}')

        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            self.send_text('Welcome to detect-me. You can detect images in this bot.\nThe supported extensions are .png, .jpg and .jpeg')

        self.bot.infinity_polling()

    def send_text(self, text):
        self.bot.send_message(self.current_msg.chat.id, text)

    def send_text_with_quote(self, text, message_id):
        self.bot.send_message(self.current_msg.chat.id, text, reply_to_message_id=message_id)

    def is_current_msg_photo(self):
        return self.current_msg.content_type == 'photo'
    
    def is_current_msg_video(self):
        return self.current_msg.content_type == 'video'
    
# download photo from user
    def download_user_photo(self, quality=2):
        """
        Downloads the photos that sent to the Bot to `photos` directory (should be existed)
        :param quality: integer representing the file quality. Allowed values are [0, 1, 2]
        :return:
        """
        if not self.is_current_msg_photo():
            raise RuntimeError(
                f'Message content of type \'photo\' expected, but got {self.current_msg.content_type}')

        file_info = self.bot.get_file(self.current_msg.photo[quality].file_id)
        data = self.bot.download_file(file_info.file_path)
        folder_name = file_info.file_path.split('/')[0]

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        with open(file_info.file_path, 'wb') as photo:
            photo.write(data)

        return file_info.file_path
# download video from user
    def download_user_video(self, quality=2):
        """
        Downloads the photos that sent to the Bot to `photos` directory (should be existed)
        :param quality: integer representing the file quality. Allowed values are [0, 1, 2]
        :return:
        """
        if not self.is_current_msg_video():
            raise RuntimeError(
                f'Message content of type \'video\' expected, but got {self.current_msg.content_type}')

        file_info = self.bot.get_file(self.current_msg.video.file_id)
        data = self.bot.download_file(file_info.file_path)
        folder_name = file_info.file_path.split('/')[0]

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        with open(file_info.file_path, 'wb') as photo:
            photo.write(data)

        return file_info.file_path
    

    def handle_message(self, message):
        """Bot Main message handler"""
        logger.info(f'Incoming message: {message}')
        self.send_text(f'Your original message: {message.text}')


class QuoteBot(Bot):
    def handle_message(self, message):
        logger.info(f'Incoming message: {message}')

        if message.text != 'Please don\'t quote me':
            self.send_text_with_quote(message.text, message_id=message.message_id)



# class ChatGPTBot(Bot):
#     def handle_message(self, message):
#         logger.info(f'Incoming message: {message}')

#         # Generate a response
#         completion = openai.ChatCompletion.create(
#             model="gpt-3.5-turbo",
#             messages=[{"role": "user", "content": message.text}],
#             max_tokens=1024,
#             n=1,
#             stop=None,
#             temperature=0.7, )

#         response = completion.choices[0].message.content
#         self.send_text(response)

class ObjectDetectionBot(Bot):
    def handle_message(self, message):
        logger.info(f'Incoming message: {message}')

        if self.is_current_msg_video():
            video_path = self.download_user_video()

            if os.path.exists('frames'):
                os.rmdir('frames')

            os.mkdir('frames')

            output_file = 'frames/output_%04d.jpg'
            framerate = '1'
            ffmpeg.input(video_path).output(output_file, r=framerate).run()

        elif self.is_current_msg_photo():
            photo_path = self.download_user_photo()

            # Send the photo to the YOLO service for object detection
            res = requests.post(f'{YOLO_URL}/predict', files={
                'file': (photo_path, open(photo_path, 'rb'), 'image/png')
            })

            if res.status_code == 200:
                detections = res.json()
                logger.info(f'response from detect service with {detections}')

                # calc summary
                element_counts = Counter([l['class'] for l in detections])
                summary = 'Objects Detected:\n'
                for element, count in element_counts.items():
                    summary += f"{element}: {count}\n"

                self.send_text(summary)

                self.send_text('Thank you for using detect-me👀!')

                # self.send_thank_you_button()

            else:
                self.send_text('Failed to perform object detection. Please try again later.')

        else:
            self.send_text('Please send a photo for object detection.')

    # def send_thank_you_button(self):
    #     markup = telebot.types.ReplyKeyboardMarkup(row_width=1)
    #     itembtn = telebot.types.KeyboardButton('Thank You 👀')
    #     markup.add(itembtn)
    #     self.bot.send_message(self.current_msg.chat.id, 'Thank you for using detect-me!', reply_markup=markup)


if __name__ == '__main__':
    with open('.telegramToken') as f:
        _token = f.read()
    
    print(_token)
    my_bot = ObjectDetectionBot(_token)
    my_bot.start()
    
