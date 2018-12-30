from __future__ import unicode_literals

import json
import os
import sys

import constant
import model
import util

from argparse import ArgumentParser
from flask import session, Flask, request, abort, redirect, url_for, escape
from linebot import (
    LineBotApi, WebhookHandler, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageAction, MessageTemplateAction,
    ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URIAction, URITemplateAction,
    PostbackTemplateAction, DatetimePickerAction,
    CameraAction, CameraRollAction, LocationAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage, FileMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
    FlexSendMessage, CarouselContainer, BubbleContainer, ImageComponent, BoxComponent,
    TextComponent, SpacerComponent, IconComponent, ButtonComponent,
    SeparatorComponent, QuickReply, QuickReplyButton
)

app = Flask(__name__)
app.secret_key = 'ROGUAPP1'

# get LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN from the environment variable

LINE_CHANNEL_SECRET = constant.LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN = constant.LINE_CHANNEL_ACCESS_TOKEN
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

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    conn = model.Conn()

    print("HERE request event:", event)

    line_user_id = event.source.user_id
    text = event.message.text

    # create session for first user
    if line_user_id not in session:
        session[line_user_id] = []

    print("HERE session before:", session)
    
    if 'user_id' not in session[line_user_id]:
        if 'status' not in session[line_user_id]:
            session[line_user_id]['status'].append("login")
            print("HERE session after:", session)

            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextMessage(
                        text=constant.WELCOME_APP
                    ),
                    TextMessage(
                        text=constant.LOGIN
                    )
                ]
            )
        else:
            text = text.replace(' ', '')
            texts = text.split("-")

            if len(texts) != 2:
                print("HERE session after:", session)

                line_bot_api.reply_message(
                    event.reply_token,
                    [
                        TextMessage(
                            text=constant.LOGIN_VALIDATION_FAIL
                        ),
                        TextMessage(
                            text=constant.LOGIN
                        )
                    ]
                )
            else:
                code = texts[0]
                dob = texts[1]
                if util.validate_date(dob,"%d%m%Y"):
                    query_select = "SELECT * FROM student WHERE code = %s AND dob = %s LIMIT 1"
                    conn.query(query_select, (code, util.convert_date(dob,"%d%m%Y","%Y-%m-%d")))
                    row = conn.cursor.fetchone()
                    if row == None:
                        print("HERE session after:",session)

                        line_bot_api.reply_message(
                            event.reply_token,
                            [
                                TextMessage(
                                    text=constant.LOGIN_FAIL
                                ),
                                TextMessage(
                                    text=constant.LOGIN
                                )
                            ]
                        )
                    else:
                        session[line_user_id]['user_id'].append(row["id"])
                        session[line_user_id]['code'].append(row["code"])
                        session[line_user_id]['name'].append(row["name"])
                        session[line_user_id]['class_id'].append(row["class_id"])
                        session[line_user_id]['status'].append("home")
                        print("HERE session after:",session)
                        
                        line_bot_api.reply_message(
                            event.reply_token,
                            [
                                TextMessage(
                                    text=constant.WELCOME_HOME % (session[line_user_id]['name']),
                                )
                            ]
                        )
                else:
                    print("HERE session after:",session)

                    line_bot_api.reply_message(
                        event.reply_token,
                        [
                            TextMessage(
                                text=constant.LOGIN_VALIDATION_FAIL
                            ),
                            TextMessage(
                                text=constant.LOGIN
                            )
                        ]
                    )
    else:
        if 'home' in session[line_user_id]['status']:
            print("HERE, home")

            print("LAST HERE, append from db")

            carousel = CarouselContainer(
                contents=[
                    BubbleContainer(
                        direction='ltr',
                        hero=ImageComponent(
                            url="https://cdn.brilio.net/news/2016/01/11/36479/finlandia-siap-hapus-pelajaran-matematika-fisika-kapan-indonesia-160111y.jpg",
                            size="full",
                            aspect_ratio="20:13",
                            aspect_mode="cover",
                            action=PostbackTemplateAction(
                                uri='http://example.com',
                                label='label'
                            )
                        ),
                        body=BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    type="text",
                                    text="Matematika",
                                    size="xl",
                                    align="center",
                                    weight="bold"
                                )
                            ]
                        )
                    ),
                    BubbleContainer(
                        direction='ltr',
                        hero=ImageComponent(
                            url="https://cdn.sindonews.net/dyn/620/content/2017/10/06/144/1246048/menuju-bahasa-internasional-bahasa-indonesia-diajarkan-di-45-negara-IoZ.jpg",
                            size="full",
                            aspect_ratio="20:13",
                            aspect_mode="cover",
                            action=URIAction(
                                uri='http://example.com',
                                label='label'
                            )
                        ),
                        body=BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    type="text",
                                    text="Bahasa Indonesia",
                                    size="xl",
                                    align="center",
                                    weight="bold"
                                )
                            ]
                        )
                    )
                ]
            )
            flex_message = FlexSendMessage(alt_text="Carousel Mapel", contents=carousel)
            line_bot_api.reply_message(event.reply_token, flex_message)        
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=event.message.text))

@app.route("/test_db", methods=['GET'])
def test_db():
    conn = model.Conn()
    
    query_select = "SELECT * FROM student"    
    conn.query(query_select, '')
    rows = conn.cursor.fetchall()

    for row in rows:
        print("HERE Email = ", row["email"])
        print("HERE Name = ", row["name"], "\n")

    return 'OK'

@app.route("/test_template", methods=['GET'])
def test_template():
    carousel = ""
    flex_message = FlexSendMessage(alt_text="Flex Message", contents=carousel)
    print("HERE, flex_message:", flex_message)
    
    return 'OK'

@app.route('/test_session')
def test_session():
    line_user_id = 123
    
    if line_user_id not in session:
        print("if 263")
        session[line_user_id] = {}
    
    print("session 1:", session)        
    
    if 'user_id' not in session[line_user_id]:
        print("if")
    else:
        print("else")
        
    print("session 2:", session)
    
    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)