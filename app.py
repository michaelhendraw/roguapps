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
    SeparatorComponent, QuickReply, QuickReplyButton,
    RichMenu, RichMenuSize, RichMenuArea, RichMenuBounds
)

app = Flask(__name__)
app.secret_key = 'ROGUAPP6'

rich_menu = {}

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

@app.route('/callback', methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)

    # handle webhook body
    try:
        print('HERE, session before:', session)
        handler.handle(body, signature)
        print('HERE, session after:', session)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    conn = model.Conn()

    print('HERE, request event:', event)

    line_user_id = event.source.user_id
    text = event.message.text

    # create session for first user
    if line_user_id not in session:
        session[line_user_id] = {
            'user_id':'',
            'code':'',
            'name':'',
            'class_id':'',
            'status':''
        }
    
    if not session[line_user_id]['user_id']: # BELUM LOGIN
        if not session[line_user_id]['status']: # BARU JOIN
            session[line_user_id]['status'] = 'login'
            
            line_bot_api.reply_message(
                event.reply_token,[
                    TextMessage(
                        text=constant.WELCOME_APP
                    ),
                    TextMessage(
                        text=constant.LOGIN
                    )
                ]
            )
        elif 'login' in session[line_user_id]['status']: # PROSES LOGIN
            text = text.replace(' ', '')
            texts = text.split('-')

            if len(texts) != 2: # VALIDASI LOGIN GAGAL
                line_bot_api.reply_message(
                    event.reply_token,[
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
                if util.validate_date(dob,'%d%m%Y'):
                    query_select = 'SELECT * FROM student WHERE code = %s AND dob = %s LIMIT 1'
                    conn.query(query_select, (code, util.convert_date(dob,'%d%m%Y','%Y-%m-%d')))
                    row = conn.cursor.fetchone()
                    if row == None: # LOGIN GAGAL
                        line_bot_api.reply_message(
                            event.reply_token,[
                                TextMessage(
                                    text=constant.LOGIN_FAIL
                                ),
                                TextMessage(
                                    text=constant.LOGIN
                                )
                            ]
                        )
                    else: # LOGIN BERHASIL
                        session[line_user_id]['user_id'] = row['id']
                        session[line_user_id]['code'] = row['code']
                        session[line_user_id]['name'] = row['name']
                        session[line_user_id]['class_id'] = row['class_id']
                        session[line_user_id]['status'] = 'home'

                        # create rich menu
                        create_rich_menu(line_user_id)
                        
                        line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['home'])
                        
                        line_bot_api.reply_message(
                            event.reply_token,[
                                TextMessage(
                                    text=constant.WELCOME_HOME % (session[line_user_id]['name']),
                                )
                            ]
                        )

                else:  # VALIDASI LOGIN GAGAL
                    line_bot_api.reply_message(
                        event.reply_token,[
                            TextMessage(
                                text=constant.LOGIN_VALIDATION_FAIL
                            ),
                            TextMessage(
                                text=constant.LOGIN
                            )
                        ]
                    )
    else: # sudah login
        if 'home' in session[line_user_id]['status']: # home
            line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['home'])
                        
            line_bot_api.reply_message(
                event.reply_token,[
                    TextMessage(
                        text=constant.WELCOME_HOME % (session[line_user_id]['name']),
                    )
                ]
            )
        elif 'material' in session[line_user_id]['status']: # material
            line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['material'])

            # get all subject by class_id
            query_select = 'SELECT * FROM subject WHERE id IN (SELECT subject_id FROM class_subject WHERE class_id = %s)'
            conn.query(query_select, (session[line_user_id]['class_id'],))
            rows = conn.cursor.fetchall()
            if rows == None: # subject is empty
                line_bot_api.reply_message(
                    event.reply_token,[
                        TextMessage(
                            text=constant.SUBJECT_EMPTY
                        )
                    ]
                )
            else: # subject exist
                contents = []
                for row in rows:
                    contents.append(BubbleContainer(
                        direction='ltr',
                        hero=ImageComponent(
                            url=row['image'],
                            size='full',
                            aspect_ratio='20:13',
                            aspect_mode='cover'
                        ),
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                ButtonComponent(
                                    action=PostbackTemplateAction(
                                        label='Materi',
                                        text='Materi',
                                        data='subject='+str(row['id'])+'&type=materi'
                                    )
                                ),
                                ButtonComponent(
                                    action=PostbackTemplateAction(
                                        label='Latihan UN',
                                        text='Latihan UN',
                                        data='subject='+str(row['id'])+'&type=latihan_un'
                                    )
                                ),
                            ]
                        )
                    ))
                
                flex_message = FlexSendMessage(
                    alt_text='Carousel Mapel',
                    contents=CarouselContainer(
                        contents=contents
                    )
                )
                line_bot_api.reply_message(event.reply_token, flex_message)            
        elif 'material_topic' in session[line_user_id]['status']: # material_topic
            line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['material_topic'])
        elif 'material_quiz' in session[line_user_id]['status']: # material_quiz
            line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['material_quiz'])
        elif 'material_discussion' in session[line_user_id]['status']: # material_discussion
            line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['material_discussion'])
        elif 'final_quiz' in session[line_user_id]['status']: # final_quiz
            line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['final_quiz'])
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=event.message.text))

# --------------------------------------------------------

@app.route('/test_db', methods=['GET'])
def test_db():
    conn = model.Conn()
    
    query_select = 'SELECT * FROM student'    
    conn.query(query_select, '')
    rows = conn.cursor.fetchall()

    for row in rows:
        print('HERE, Email = ', row['email'])
        print('HERE, Name = ', row['name'], '\n')

    return 'OK'

@app.route('/test_template', methods=['GET'])
def test_template():
    conn = model.Conn()

    query_select = 'SELECT * FROM subject WHERE id IN (SELECT subject_id FROM class_subject WHERE class_id = %s)'
    conn.query(query_select, (1,))
    rows = conn.cursor.fetchall()
    if rows == None: # subject is empty
        line_bot_api.reply_message(
            event.reply_token,[
                TextMessage(
                    text=constant.SUBJECT_EMPTY
                )
            ]
        )
    else: # subject exist
        contents = []
        for row in rows:
            contents.append(BubbleContainer(
                direction='ltr',
                hero=ImageComponent(
                    url=row['image'],
                    size='full',
                    aspect_ratio='20:13',
                    aspect_mode='cover'
                ),
                body=BoxComponent(
                    layout='vertical',
                    contents=[
                        ButtonComponent(
                            action=PostbackTemplateAction(
                                label='Materi',
                                text='Materi',
                                data='subject='+str(row['id'])+'&type=materi'
                            )
                        ),
                        ButtonComponent(
                            action=PostbackTemplateAction(
                                label='Latihan UN',
                                text='Latihan UN',
                                data='subject='+str(row['id'])+'&type=latihan_un'
                            )
                        ),
                    ]
                )
            ))

        flex_message = FlexSendMessage(
            alt_text='Carousel Mapel',
            contents=CarouselContainer(
                contents=contents
            )
        )
    print('HERE, flex_message:', flex_message)
    
    return 'OK'

@app.route('/test_session')
def test_session():
    line_user_id = 123
    
    if line_user_id not in session:
        print('if 263')
        session[line_user_id] = {}
    
    print('session 1:', session)        
    
    if 'user_id' not in session[line_user_id]:
        print('if')
    else:
        print('else')
        
    print('session 2:', session)
    
    return 'OK'

# --------------------------------------------------------

def create_rich_menu(line_user_id):
    # doc: https://github.com/line/line-bot-sdk-python/blob/master/README.rst

    global rich_menu

    # home
    rich_menu_to_create = RichMenu(
        size=RichMenuSize(
            width=2500,
            height=843
        ),
        selected=False,
        name='Navigasi Home',
        chat_bar_text='Navigasi Home',
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=48,
                    y=36,
                    width=1190,
                    height=780
                ),
                action=PostbackTemplateAction(
                    label='Materi',
                    text='Materi',
                    data='type=material'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=1290,
                    y=44,
                    width=1174,
                    height=760
                ),
                action=PostbackTemplateAction(
                    label='Latihan UN',
                    text='Latihan UN',
                    data='type=final_quiz'
                )
            ),
        ]
    )
    rich_menu['home'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_HOME, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['home'], 'image/png', f)

    # material
    rich_menu_to_create = RichMenu(
        size=RichMenuSize(
            width=2500,
            height=843
        ),
        selected=False,
        name='Navigasi Material',
        chat_bar_text='Navigasi Material',
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=28,
                    y=32,
                    width=587,
                    height=784
                ),
                action=PostbackTemplateAction(
                    label='Kembali',
                    text='Kembali',
                    data='type=home'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=651,
                    y=32,
                    width=1817,
                    height=788
                ),
                action=PostbackTemplateAction(
                    label='Latihan UN',
                    text='Latihan UN',
                    data='type=final_quiz'
                )
            ),
        ]
    )
    rich_menu['material'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_MATERIAL, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['material'], 'image/png', f)

    # material_topic
    rich_menu_to_create = RichMenu(
        size=RichMenuSize(
            width=2500,
            height=843
        ),
        selected=False,
        name='Navigasi Material Topic',
        chat_bar_text='Navigasi Material Topic',
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=38,
                    y=40,
                    width=579,
                    height=776
                ),
                action=PostbackTemplateAction(
                    label='Kembali',
                    text='Kembali',
                    data='type=material'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=655,
                    y=36,
                    width=880,
                    height=780
                ),
                action=PostbackTemplateAction(
                    label='Latihan Soal',
                    text='Latihan Soal',
                    data='type=material_quiz'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=1584,
                    y=36,
                    width=880,
                    height=784
                ),
                action=PostbackTemplateAction(
                    label='Diskusi',
                    text='Diskusi',
                    data='type=material_quiz'
                )
            ),
        ]
    )
    rich_menu['material_topic'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_MATERIAL_TOPIC, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['material_topic'], 'image/png', f)

    # material_quiz
    rich_menu_to_create = RichMenu(
        size=RichMenuSize(
            width=2500,
            height=843
        ),
        selected=False,
        name='Navigasi Material Quiz',
        chat_bar_text='Navigasi Material Quiz',
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=38,
                    y=40,
                    width=579,
                    height=776
                ),
                action=PostbackTemplateAction(
                    label='Kembali',
                    text='Kembali',
                    data='type=material'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=655,
                    y=36,
                    width=880,
                    height=780
                ),
                action=PostbackTemplateAction(
                    label='Belajar',
                    text='Belajar',
                    data='type=material_topic'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=1584,
                    y=36,
                    width=880,
                    height=784
                ),
                action=PostbackTemplateAction(
                    label='Diskusi',
                    text='Diskusi',
                    data='type=material_discussion'
                )
            ),
        ]
    )
    rich_menu['material_quiz'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_MATERIAL_QUIZ, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['material_quiz'], 'image/png', f)
    
    # material_discussion
    rich_menu_to_create = RichMenu(
        size=RichMenuSize(
            width=2500,
            height=843
        ),
        selected=False,
        name='Navigasi Material Discussion',
        chat_bar_text='Navigasi Material Discussion',
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=38,
                    y=40,
                    width=579,
                    height=776
                ),
                action=PostbackTemplateAction(
                    label='Kembali',
                    text='Kembali',
                    data='type=material'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=655,
                    y=36,
                    width=880,
                    height=780
                ),
                action=PostbackTemplateAction(
                    label='Belajar',
                    text='Belajar',
                    data='type=material_topic'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=1584,
                    y=36,
                    width=880,
                    height=784
                ),
                action=PostbackTemplateAction(
                    label='Latihan Soal',
                    text='Latihan Soal',
                    data='type=material_quiz'
                )
            ),
        ]
    )
    rich_menu['material_discussion'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_MATERIAL_DISCUSSION, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['material_discussion'], 'image/png', f)

    # final_quiz
    rich_menu_to_create = RichMenu(
        size=RichMenuSize(
            width=2500,
            height=843
        ),
        selected=False,
        name='Navigasi Final Quiz',
        chat_bar_text='Navigasi Final Quiz',
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=28,
                    y=32,
                    width=587,
                    height=784
                ),
                action=PostbackTemplateAction(
                    label='Kembali',
                    text='Kembali',
                    data='type=home'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=651,
                    y=32,
                    width=1817,
                    height=788
                ),
                action=PostbackTemplateAction(
                    label='Materi',
                    text='Materi',
                    data='type=material'
                )
            ),
        ]
    )
    rich_menu['final_quiz'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_FINAL_QUIZ, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['final_quiz'], 'image/png', f)

    return

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)