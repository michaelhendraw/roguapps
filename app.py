from __future__ import unicode_literals

import json
import os
import sys

import constant
import model
import redis
import util

from argparse import ArgumentParser
from flask import Flask, request, abort, redirect, url_for, escape
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
app.secret_key = 'ROGUAPP12'

redis=redis.from_url(constant.REDISCLOUD_URL)

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
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    global rich_menu

    conn = model.Conn()

    print('HERE, request event:', event)

    line_user_id = event.source.user_id
    text = event.message.text

    session_bytes = redis.get(line_user_id)
    session = {}
    if session_bytes is not None:
        session = json.loads(session_bytes.decode("utf-8"))

    print("HERE, session:", session)

    if session == {}: # USER PERTAMA KALI BUKA
        redis.set(line_user_id,json.dumps({'status':'login'}))
        
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
    else:
        if 'login' in session['status']: # PROSES LOGIN
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
                        redis.set(line_user_id,json.dumps({'user_id':row['id'],'code':row['code'],'name':row['name'],'class_id':row['class_id'],'status':'home'}))

                        # create rich menu
                        create_rich_menu(line_user_id)
                        
                        line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['home'])
                        
                        line_bot_api.reply_message(
                            event.reply_token,[
                                TextMessage(
                                    text=constant.WELCOME_HOME % (row['name']),
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
        elif 'home' in session['status']:
            if event.message.text is 'material':
                redis.set(line_user_id,json.dumps({'user_id':session['user_id'],'code':session['code'],'name':session['name'],'class_id':session['class_id'],'status':'material'}))

                line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['material'])

                # get all subject by class_id
                query_select = 'SELECT * FROM subject WHERE id IN (SELECT subject_id FROM class_subject WHERE class_id = %s)'
                conn.query(query_select, (session['class_id'],))
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
                                            text='material',
                                            data='case=material&subject_id='+str(row['id'])
                                        )
                                    ),
                                    ButtonComponent(
                                        action=PostbackTemplateAction(
                                            label='Latihan UN',
                                            text='final_quiz',
                                            data='case=final_quiz&subject_id='+str(row['id'])
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
            elif event.message.text is 'final_quiz':
                redis.set(line_user_id,json.dumps({'user_id':session['user_id'],'code':session['code'],'name':session['name'],'class_id':session['class_id'],'status':'final_quiz'}))
                
                line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['final_quiz'])
            else:
                line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['home'])
                line_bot_api.reply_message(
                    event.reply_token,[
                        TextMessage(
                            text=constant.WELCOME_HOME % (session['name']),
                        )
                    ]
                )
        elif 'material' in session['status']:
            redis.set(line_user_id,json.dumps({'user_id':session['user_id'],'code':session['code'],'name':session['name'],'class_id':session['class_id'],'status':'material'}))
        
            if event.message.text is  'material_topic':
                line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['material_topic'])
            elif event.message.text is 'material_quiz':
                line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['material_quiz'])
            elif event.message.text is 'material_discussion':
                line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['material_discussion'])
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
                                text='material',
                                data='case=material&subject_id='+str(row['id'])
                            )
                        ),
                        ButtonComponent(
                            action=PostbackTemplateAction(
                                label='Latihan UN',
                                text='final_quiz',
                                data='case=final_quiz&subject_id='+str(row['id'])
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

    print('HERE, line_user_id:', line_user_id)
    print('session 1:', session)

    # if line_user_id not in session:
    if session.get(line_user_id) == None:
        print('HERE, create new session 1')
        session[line_user_id] = {
            'user_id':'',
            'code':'',
            'name':'',
            'class_id':'',
            'status':''
        }
    
    print('session 2:', session)

    if session.get(line_user_id) == None:
        print('HERE, create new session 2')

    print('session 3:', session)

    return 'OK'

@app.route('/test_getredis/<key>')
def test_getredis(key):
    # keys = "1"
    data = redis.get(key)
    if data is None:
        return '-'
    else:
        return json.loads(data.decode("utf-8"))

@app.route('/test_setredis/<key>/<val>')
def test_setredis(key,val):
    # key = "1"
    # val = {'id':2,'name':'hussain'}
    redis.set(key,json.dumps(val))
    return 'set:' + key

@app.route('/test_redis')
def test_redis():
    line_user_id = '124'

    session_bytes = redis.get(line_user_id)
    session = {}
    if session_bytes is not None:
        session = json.loads(session_bytes.decode("utf-8"))

    print("HERE, session_bytes:", session_bytes)
    print("HERE, session:", session)

    if session == {}:
        print("# BELUM LOGIN")
        redis.set(line_user_id,json.dumps({'status':'login'}))
    else:
        if 'login' in session['status']:
            print("# PROSES LOGIN")
            redis.set(line_user_id,json.dumps({'status':'home'}))
        elif 'home' in session['status']:
            print("# HOME :)")
            redis.set(line_user_id,json.dumps({'status':'unknown'}))
        else:
            print("# UNKNOWN")
              
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
        name='Home',
        chat_bar_text='Home',
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
                    text='material',
                    data='case=material'
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
                    text='final_quiz',
                    data='case=final_quiz'
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
        name='Materi',
        chat_bar_text='Materi',
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
                    text='home',
                    data='case=home'
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
                    text='final_quiz',
                    data='case=final_quiz'
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
        name='Belajar',
        chat_bar_text='Belajar',
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
                    text='material',
                    data='case=material'
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
                    text='material_quiz',
                    data='case=material_quiz'
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
                    text='material_discussion',
                    data='case=material_discussion'
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
        name='Latihan Soal',
        chat_bar_text='Latihan Soal',
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
                    text='material',
                    data='case=material'
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
                    text='material_topic',
                    data='case=material_topic'
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
                    text='material_discussion',
                    data='case=material_discussion'
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
        name='Diskusi',
        chat_bar_text='Diskusi',
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
                    text='material',
                    data='case=material'
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
                    text='material_topic',
                    data='case=material_topic'
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
                    text='material_quiz',
                    data='case=material_quiz'
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
        name='Latihan UN',
        chat_bar_text='Latihan UN',
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
                    text='home',
                    data='case=home'
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
                    text='material',
                    data='case=material'
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