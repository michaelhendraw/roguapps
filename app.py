from __future__ import unicode_literals

import os
import sys

import model

from argparse import ArgumentParser
from flask import Flask, request, abort, session, redirect, url_for, escape
from linebot import (
    LineBotApi, WebhookHandler, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageTemplateAction,
    ButtonsTemplate, URITemplateAction, PostbackTemplateAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent
)

app = Flask(__name__)
app.secret_key = 'ROGUAPPS'

# get LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN from the environment variable

LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', None)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if LINE_CHANNEL_SECRET is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if LINE_CHANNEL_ACCESS_TOKEN is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
parser = WebhookParser(LINE_CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        events = parser.parse(body, signature)
        user_id = events.pop().source.user_id
        print("user_id line:", user_id)
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# @app.after_request
# def after_request(response):
#     return response

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    if 'user_id' not in session:
        flex_template = [
            {
                "type": "flex",
                "altText": "Flex Message",
                "contents": {
                    "type": "bubble",
                    "direction": "ltr",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "image",
                                "url": "https://image.myanimelist.net/ui/MHaOlBrkklS2yN3DPEI1ddb2Rqt4zhkv87ApMNn9H2w",
                                "align": "center",
                                "gravity": "center",
                                "size": "full",
                                "aspectRatio": "20:13",
                                "aspectMode": "fit"
                            },
                            {
                                "type": "text",
                                "text": "Hai ! Selamat datang di Rogu. Silahkan masukkan NIS Kamu untuk melanjutkan belajar !",
                                "align": "center",
                                "gravity": "center",
                                "wrap": "true"
                            }
                        ]
                    }
                }
            }
        ]
        template_message = TemplateSendMessage(
            alt_text='Flex Message',
            template=flex_template
        )
        line_bot_api.reply_message(event.reply_token,template_message)
    else:
        user_id = session['user_id']
        name = session['name']

        text = event.message.text
        session = getattr(g, 'session', None)
        print("handle")
        print(session)

        if text == 'profile':
            if isinstance(event.source, SourceUser):
                profile = line_bot_api.get_profile(event.source.user_id)
                line_bot_api.reply_message(
                    event.reply_token, [
                        TextSendMessage(
                            text='Display name: ' + profile.display_name
                        ),
                        TextSendMessage(
                            text='Status message: ' + profile.status_message
                        )
                    ]
                )
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextMessage(text="Bot can't use profile API without user ID"))
        elif text == 'bye':
            if isinstance(event.source, SourceGroup):
                line_bot_api.reply_message(
                    event.reply_token, TextMessage(text='Leaving group'))
                line_bot_api.leave_group(event.source.group_id)
            elif isinstance(event.source, SourceRoom):
                line_bot_api.reply_message(
                    event.reply_token, TextMessage(text='Leaving group'))
                line_bot_api.leave_room(event.source.room_id)
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextMessage(text="Bot can't leave from 1:1 chat"))
        elif text == 'confirm':
            confirm_template = ConfirmTemplate(text='Do it?', actions=[
                MessageTemplateAction(label='Yes', text='Yes!'),
                MessageTemplateAction(label='No', text='No!'),
            ])
            template_message = TemplateSendMessage(
                alt_text='Confirm alt text', template=confirm_template)
            line_bot_api.reply_message(event.reply_token, template_message)
        elif text == 'buttons':
            buttons_template = ButtonsTemplate(
                title='My buttons sample', text='Hello, my buttons', actions=[
                    URITemplateAction(
                        label='Go to line.me', uri='https://line.me'),
                    PostbackTemplateAction(label='ping', data='ping'),
                    PostbackTemplateAction(
                        label='ping with text', data='ping',
                        text='ping'),
                    MessageTemplateAction(label='Translate Rice', text='米')
                ])
            template_message = TemplateSendMessage(
                alt_text='Buttons alt text', template=buttons_template)
            line_bot_api.reply_message(event.reply_token, template_message)
        elif text == 'carousel':
            carousel_template = CarouselTemplate(columns=[
                CarouselColumn(text='hoge1', title='fuga1', actions=[
                    URITemplateAction(
                        label='Go to line.me', uri='https://line.me'),
                    PostbackTemplateAction(label='ping', data='ping')
                ]),
                CarouselColumn(text='hoge2', title='fuga2', actions=[
                    PostbackTemplateAction(
                        label='ping with text', data='ping',
                        text='ping'),
                    MessageTemplateAction(label='Translate Rice', text='米')
                ]),
            ])
            template_message = TemplateSendMessage(
                alt_text='Buttons alt text', template=carousel_template)
            line_bot_api.reply_message(event.reply_token, template_message)
        elif text == 'imagemap':
            pass
        else:
            session['status'] = event.message.text
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=event.message.text))

@app.route("/test_db", methods=['GET'])
def test_db():
    conn = model.Conn()
    
    query_select = "SELECT * FROM student"    
    conn.query(query_select, '')
    rows = conn.cursor.fetchall()

    for row in rows:
        print("Email = ", row["email"])
        print("Name = ", row["name"], "\n")

    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
