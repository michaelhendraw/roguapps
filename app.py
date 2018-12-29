from __future__ import unicode_literals

import os
import sys

import model
import constant

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
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent
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
        
        print("HERE signature:",signature)
        print("HERE request body:",body)
        
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    conn = model.Conn()

    text = event.message.text
    print("HERE text:",text)

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
            query_select = "SELECT * FROM student WHERE code = %s AND dob = %s LIMIT 1"
            conn.query(query_select, (text))
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
                session['line_code'] = row["line_code"]
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
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=event.message.text)
            )

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
