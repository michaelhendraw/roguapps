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
    TemplateSendMessage, ConfirmTemplate, MessageTemplateAction,
    ButtonsTemplate, URITemplateAction, PostbackTemplateAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
    FlexSendMessage, FlexContainer, BubbleContainer, BoxComponent, TextComponent
)

app = Flask(__name__)
app.secret_key = 'ROGUAPPS'

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
        events = parser.parse(body, signature)
        line_user_id = events.pop().source.user_id
        session['line_user_id'] = line_user_id
        
        print("HERE request body:",body)
        
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    conn = model.Conn()

    text = event.message.text

    print("HERE session before:",session)
    
    if 'user_id' not in session:
        if 'status' not in session:
            session['status'] = "login"
            print("HERE session after:",session)

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
                        session['user_id'] = row["id"]
                        session['code'] = row["code"]
                        session['name'] = row["name"]
                        session['class_id'] = row["class_id"]

                        session['status'] = "home"
                        print("HERE session after:",session)
                        
                        line_bot_api.reply_message(
                            event.reply_token,
                            [
                                TextMessage(
                                    text=constant.WELCOME_HOME % (session['name']),
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
        if 'status' in session and session['status'] == "home":
            print("HERE, home")

            # flex_message = FlexSendMessage(
            #     altText="Flex Message", 
            #     contents=FlexContainer(
            #         type="carousel",
            #         contents=[
            #             BubbleContainer(
            #                 type="bubble",
            #                 hero=ImageMessage(
            #                     type="image",
            #                     url="https://cdn.brilio.net/news/2016/01/11/36479/finlandia-siap-hapus-pelajaran-matematika-fisika-kapan-indonesia-160111y.jpg",
            #                     size="full",
            #                     aspectRatio="20:13",
            #                     aspectMode="cover"
            #                 ),
            #                 body=BoxComponent(
            #                     type="box",
            #                     layout="vertical",
            #                     action=MessageTemplateAction(
            #                         type="message",
            #                         label="Matematika",
            #                         text="Matematika"
            #                     ),
            #                     contents=[
            #                         TextComponent(
            #                             type="text",
            #                             text="Matematika",
            #                             size="xl",
            #                             align="center",
            #                             weight="bold"
            #                         )
            #                     ]
            #                 )
            #             ),
            #             # "https://cdn.sindonews.net/dyn/620/content/2017/10/06/144/1246048/menuju-bahasa-internasional-bahasa-indonesia-diajarkan-di-45-negara-IoZ.jpg"
            #             # "Bahasa Indonesia"
            #         ]
            #     )
            # )
            # line_bot_api.reply_message(event.reply_token, flex_message)

            flex_message = {
                "type": "flex",
                "altText": "Flex Message",
                "contents": {
                    "type": "carousel",
                    "contents": [
                        {
                            "type": "bubble",
                            "hero": {
                                "type": "image",
                                "url": "https://cdn.brilio.net/news/2016/01/11/36479/finlandia-siap-hapus-pelajaran-matematika-fisika-kapan-indonesia-160111y.jpg",
                                "size": "full",
                                "aspectRatio": "20:13",
                                "aspectMode": "cover"
                            },
                            "body": {
                                "type": "box",
                                "layout": "vertical",
                                "action": {
                                    "type": "message",
                                    "label": "Matematika",
                                    "text": "Matematika"
                                },
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "Matematika",
                                        "size": "xl",
                                        "align": "center",
                                        "weight": "bold"
                                    }
                                ]
                            }
                        },
                        {
                            "type": "bubble",
                            "hero": {
                                "type": "image",
                                "url": "https://cdn.sindonews.net/dyn/620/content/2017/10/06/144/1246048/menuju-bahasa-internasional-bahasa-indonesia-diajarkan-di-45-negara-IoZ.jpg",
                                "align": "center",
                                "gravity": "center",
                                "size": "full",
                                "aspectRatio": "20:13",
                                "aspectMode": "cover",
                                "action": {
                                    "type": "uri",
                                    "label": "Line",
                                    "uri": "https://linecorp.com/"
                                }
                            },
                            "body": {
                                "type": "box",
                                "layout": "vertical",
                                "action": {
                                    "type": "message",
                                    "label": "Bahasa Indonesia",
                                    "text": "Bahasa Indonesia"
                                },
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "Bahasa Indonesia",
                                        "size": "xl",
                                        "align": "center",
                                        "weight": "bold"
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
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

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
