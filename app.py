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
    PostbackAction, DatetimePickerAction,
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
    conn = model.Conn()

    line_user_id = event.source.user_id
    text = event.message.text

    session_bytes = redis.get(line_user_id)
    session = {}
    if session_bytes is not None:
        session = json.loads(session_bytes.decode("utf-8"))

    print('\n\n\nHERE, request event:', event)
    print("\n\n\nHERE, session:", session)

    if session == {}:
        print("\n\n\nHERE # USER PERTAMA KALI BUKA")
        redis.set(line_user_id,json.dumps({'status':'login'}))

        remove_rich_menu(line_user_id)
        
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
        if 'login' in session['status']:
            print("\n\n\nHERE # PROSES LOGIN")
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
                    else:
                        print("\n\n\nHERE # LOGIN BERHASIL")

                        # create rich menu
                        rich_menu = create_rich_menu(line_user_id)

                        line_bot_api.link_rich_menu_to_user(line_user_id, rich_menu['home'])
                        redis.set(line_user_id,json.dumps({'user_id':row['id'],'code':row['code'],'name':row['name'],'class_id':row['class_id'],'status':'home','rich_menu':rich_menu}))
                        
                        line_bot_api.reply_message(
                            event.reply_token,[
                                TextMessage(
                                    text=constant.WELCOME_HOME % (row['name']),
                                )
                            ]
                        )

                else:
                    print("\n\n\nHERE # VALIDASI LOGIN GAGAL")
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

@handler.add(PostbackEvent)
def handle_postback(event):
    conn = model.Conn()

    line_user_id = event.source.user_id

    session_bytes = redis.get(line_user_id)
    session = {}
    if session_bytes is not None:
        session = json.loads(session_bytes.decode("utf-8"))

    postback = {}
    postbacks = event.postback.data.split('&')
    for p in postbacks:
        ps = p.split('=')
        postback[ps[0]] = ps[1]

    print('\n\n\nHERE, request event:', event)
    print("\n\n\nHERE, postback:", postback)

    if 'login' in session['status']: # BELUM LOGIN
        print("\n\n\n# session: login, action: -, rich menu: -")

        remove_rich_menu(line_user_id)
        
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
    else: # SUDAH LOGIN
        # MATERIAL
        if 'material' == postback['action']:
            print("\n\n\n# session: home, action: material, rich menu: material")

            line_bot_api.link_rich_menu_to_user(line_user_id, session['rich_menu']['material'])

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
                    contents.append(
                        BubbleContainer(
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
                                        action=PostbackAction(
                                            label=row['name'],
                                            text=row['name'],
                                            data='action=material_topic&subject_id='+str(row['id'])
                                        )
                                    ),
                                
                                ]
                            )
                        )
                    )
                
                flex_message = FlexSendMessage(
                    alt_text='Carousel Mapel',
                    contents=CarouselContainer(
                        contents=contents
                    )
                )
                line_bot_api.reply_message(event.reply_token, flex_message)
        elif 'material_topic' == postback['action']:
            print("\n\n\n# session: home, action: material_topic, rich menu: material")
            
            line_bot_api.link_rich_menu_to_user(line_user_id, session['rich_menu']['material'])

            flex_message = show_material_topic(event, conn, session, postback)

            line_bot_api.reply_message(event.reply_token, flex_message)
        elif 'material_learn' == postback['action']:
            print("\n\n\n# session: home, action: material_learn, rich menu: material_learn")

            line_bot_api.link_rich_menu_to_user(line_user_id, session['rich_menu']['material_learn'])
            
            seq = 1
            if 'sequence' in postback:
                seq = int(postback['sequence'])

            seq_next = seq+1
            
            # get next material by topic_id
            query_select_material_next = 'SELECT * FROM material WHERE topic_id = %s AND sequence = %s'
            conn.query(query_select_material_next, (str(postback['topic_id']), seq_next))
            row_material_next = conn.cursor.fetchone()

            # get material by topic_id
            query_select_material = 'SELECT * FROM material WHERE topic_id = %s AND sequence = %s'
            conn.query(query_select_material, (str(postback['topic_id']), seq))
            row_material = conn.cursor.fetchone()

            flex_messages = []
            if row_material_next is None:
                flex_message = FlexSendMessage(
                    alt_text='Carousel Belajar',
                    contents=BubbleContainer(
                        direction='ltr',
                        header=BoxComponent(
                            layout='vertical',
                            contents=[
                                    TextComponent(
                                    text=str(row_material['name']),
                                    margin='md',
                                    size='xl',
                                    align='center',
                                    gravity='center',
                                    weight='bold',
                                    wrap=True
                                ),
                            ]
                        ),
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                TextComponent(
                                    text=str(row_material['description']),
                                    align='start',
                                    gravity='center',
                                    wrap=True
                                )
                            ]
                        )
                    )
                )
                flex_messages.append(flex_message)
            else:
                flex_message = FlexSendMessage(
                    alt_text='Carousel Belajar',
                    contents=BubbleContainer(
                        direction='ltr',
                        header=BoxComponent(
                            layout='vertical',
                            contents=[
                                    TextComponent(
                                    text=str(row_material['name']),
                                    margin='md',
                                    size='xl',
                                    align='center',
                                    gravity='center',
                                    weight='bold',
                                    wrap=True
                                ),
                            ]
                        ),
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                TextComponent(
                                    text=str(row_material['description']),
                                    align='start',
                                    gravity='center',
                                    wrap=True
                                ),
                                # the different is here in button
                                ButtonComponent(
                                    action=PostbackAction(
                                        label='Lanjut',
                                        text='Lanjut',
                                        data='action=material_learn&subject_id='+str(postback['subject_id'])+'&topic_id='+str(postback['topic_id'])+'&sequence='+str(seq_next)
                                    ),
                                    margin='xxl',
                                    style='primary'
                                )
                            ]
                        )
                    )
                )
                flex_messages.append(flex_message)

            if row_material_next is None:
                flex_message_material_topic = show_material_topic(event, conn, session, postback)
                flex_messages.append(flex_message_material_topic)

            line_bot_api.reply_message(event.reply_token, flex_messages)
        elif 'material_quiz' == postback['action']:
            print("\n\n\n# session: home, action: material_quiz, rich menu: material_quiz")

            line_bot_api.link_rich_menu_to_user(line_user_id, session['rich_menu']['material_quiz'])

            flex_messages = []
            
            seq = 1
            if 'sequence' in postback:
                seq = int(postback['sequence'])

            seq_next = seq+1

            # check answer before
            if 'quiz_detail_id' in postback:
                feedback_answer = ''
                if postback['answer'] != postback['correct_answer']: # invalid answer
                    feedback_answer = constant.QUIZ_INCORRECT_ANSWER % (postback['correct_answer'])
                else:
                    feedback_answer = constant.QUIZ_CORRECT_ANSWER

                flex_message = FlexSendMessage(
                    alt_text='Carousel Latihan Soal',
                    contents=BubbleContainer(
                        direction='ltr',
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                TextComponent(
                                    text=feedback_answer,
                                    margin='md',
                                    size='md',
                                    align='center',
                                    gravity='center',
                                    weight='bold',
                                    wrap=True
                                ),
                            ]
                        )
                    )
                )
                flex_messages.append(flex_message)

                # get next quiz by material_id
                query_select_question_next = 'SELECT * FROM quiz_detail WHERE material_id IN (SELECT id FROM material WHERE topic_id = %s AND sequence = %s)'
                conn.query(query_select_question_next, (str(postback['topic_id']), seq_next))
                row_question_next = conn.cursor.fetchone()
                
                if row_question_next is None:
                    flex_message_material_topic = show_material_topic(event, conn, session, postback)
                    flex_messages.append(flex_message_material_topic)
                
                line_bot_api.reply_message(event.reply_token, flex_messages)

            # get quiz by material_id
            query_select_question = 'SELECT * FROM quiz_detail WHERE material_id IN (SELECT id FROM material WHERE topic_id = %s AND sequence = %s)'
            conn.query(query_select_question, (str(postback['topic_id']), seq))
            row_question = conn.cursor.fetchone()

            if row_question is None: # quiz is empty
                line_bot_api.reply_message(
                    event.reply_token,[
                        TextMessage(
                            text=constant.QUIZ_EMPTY
                        )
                    ]
                )
            else:
                # get quiz_answer by quiz_detail_id
                query_select_answer = 'SELECT * FROM quiz_answer WHERE quiz_detail_id = %s ORDER BY random()'
                conn.query(query_select_answer, (row_question['id'],))
                rows_answer = conn.cursor.fetchall()

                answers = []
                answers_button = []
                options = ['A', 'B', 'C', 'D', 'E']
                o = 0
                for row in rows_answer:
                    answers.append(options[o]+'. '+row['answer'])
                    answers_button.append(
                        ButtonComponent(
                            action=PostbackAction(
                                label=options[o],
                                text=options[o],
                                data='action=material_quiz&subject_id='+str(postback['subject_id'])+'&topic_id='+str(postback['topic_id'])+'&sequence='+str(seq_next)+'&quiz_detail_id='+str(row_question['id'])+'&correct_answer='+str(row_question['correct_answer'])+'&answer='+str(row['answer'])
                            ),
                            flex=1,
                            margin='sm',
                            style='primary'
                        )
                    )
                    o+=1

                flex_message = FlexSendMessage(
                    alt_text='Carousel Latihan Soal',
                    contents=BubbleContainer(
                        direction='ltr',
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                    TextComponent(
                                        text='Pertanyaan '+str(seq),
                                        margin='md',
                                        size='lg',
                                        align='center',
                                        gravity='center',
                                        weight='bold',
                                        wrap=True
                                    ),
                                    TextComponent(
                                        text=row_question['question'],
                                        margin='md',
                                        align='start',
                                        wrap=True
                                    ),
                                    TextComponent(
                                        text='\n'.join(str(x) for x in answers) ,
                                        margin='sm',
                                        wrap=True
                                    ),
                            ]
                        ),
                        footer=BoxComponent(
                            layout='horizontal',
                            contents=[
                                BoxComponent(
                                    layout='horizontal',
                                    contents=answers_button
                                )
                            ]
                        )
                    )
                )
                flex_messages.append(flex_message)

                line_bot_api.reply_message(event.reply_token, flex_messages)
        elif 'material_discussion' == postback['action']:
            print("\n\n\n# session: home, action: material_discussion, rich menu: material_discussion")

            line_bot_api.link_rich_menu_to_user(line_user_id, session['rich_menu']['material_discussion'])
        # FINAL QUIZ
        elif 'final_quiz' == postback['action']:
            print("\n\n\n# session: home, action: final_quiz, rich menu: final_quiz")
            
            line_bot_api.link_rich_menu_to_user(line_user_id, session['rich_menu']['final_quiz'])
        # HOME
        else:
            print("\n\n\n# session: home, action: -, rich menu: home")

            line_bot_api.link_rich_menu_to_user(line_user_id, session['rich_menu']['home'])

            line_bot_api.reply_message(
                event.reply_token,[
                    TextMessage(
                        text=constant.WELCOME_HOME % (session['name']),
                    )
                ]
            )
    
# --------------------------------------------------------

@app.route('/test_db/<s>/<qdi>/<ca>/<a>', methods=['GET'])
def test_db(s,qdi,ca,a):
    conn = model.Conn()

    postback = {'action': 'material_learn', 'subject_id': '2', 'topic_id': '3' , 'sequence': s}
    if qdi != 0:
        postback = {'action': 'material_learn', 'subject_id': '2', 'topic_id': '3' , 'sequence': s, 'quiz_detail_id': qdi, 'correct_answer': ca, 'answer': a}

    # START CODE HERE
    flex_message = []

    print("flex_message final:", flex_messages)
    return 'OK'

@app.route('/test_template', methods=['GET'])
def test_template():
    conn = model.Conn()

    # get all subject by class_id
    query_select_subject = 'SELECT * FROM subject WHERE id = %s'
    conn.query(query_select_subject, '2')
    row_subject = conn.cursor.fetchone()

    # get all topic by subject_id
    query_select_topic = 'SELECT * FROM topic WHERE subject_id = %s'
    conn.query(query_select_topic, '1')
    rows_topic = conn.cursor.fetchall()
    if rows_topic == None: # topic is empty
        line_bot_api.reply_message(
            event.reply_token,[
                TextMessage(
                    text=constant.TOPIC_EMPTY
                )
            ]
        )
    else: # topic exist
        contents = []
        for row in rows_topic:
            contents.append(
                BubbleContainer(
                    direction='ltr',
                    body=BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text=str(row['name']),
                                margin='md',
                                size='xl',
                                align='center',
                                gravity='center',
                                weight='bold'
                            ),
                            ButtonComponent(
                                action=PostbackAction(
                                    label='Belajar',
                                    text='Belajar',
                                    data='action=material_learn&subject_id='+str(row_subject['id'])+'&topic_id='+str(row['id'])
                                )
                            ),
                            ButtonComponent(
                                action=PostbackAction(
                                    label='Diskusi',
                                    text='Diskusi',
                                    data='action=material_discussion&subject_id='+str(row_subject['id'])+'&topic_id='+str(row['id'])
                                )
                            ),
                            ButtonComponent(
                                action=PostbackAction(
                                    label='Latihan Soal',
                                    text='Latihan Soal',
                                    data='action=material_quiz&subject_id='+str(row_subject['id'])+'&topic_id='+str(row['id'])
                                )
                            )
                        ]
                    )
                )
            )
            
        
        flex_message = FlexSendMessage(
            alt_text='Carousel Topik',
            contents=CarouselContainer(
                contents=contents
            )
        )

        print('HERE, contents:', contents)
        print('HERE, flex_message:', flex_message)
    
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

# doc: https://github.com/line/line-bot-sdk-python/blob/master/README.rst
def create_rich_menu(line_user_id):
    rich_menu = {}

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
                action=PostbackAction(
                    label='Materi',
                    text='Materi',
                    data='action=material'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=1290,
                    y=44,
                    width=1174,
                    height=760
                ),
                action=PostbackAction(
                    label='Latihan UN',
                    text='Latihan UN',
                    data='action=final_quiz'
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
                action=PostbackAction(
                    label='Kembali',
                    text='Kembali',
                    data='action=home'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=651,
                    y=32,
                    width=1817,
                    height=788
                ),
                action=PostbackAction(
                    label='Latihan UN',
                    text='Latihan UN',
                    data='action=final_quiz'
                )
            ),
        ]
    )
    rich_menu['material'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_MATERIAL, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['material'], 'image/png', f)

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
                action=PostbackAction(
                    label='Kembali',
                    text='Kembali',
                    data='action=home'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=651,
                    y=32,
                    width=1817,
                    height=788
                ),
                action=PostbackAction(
                    label='Materi',
                    text='Materi',
                    data='action=material'
                )
            ),
        ]
    )
    rich_menu['final_quiz'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_FINAL_QUIZ, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['final_quiz'], 'image/png', f)

    return rich_menu

def create_rich_menu_material_topic(line_user_id, subject_id, topic_id):
    rich_menu = {}

    # material_learn
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
                action=PostbackAction(
                    label='Kembali',
                    text='Kembali',
                    data='action=material'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=655,
                    y=36,
                    width=880,
                    height=780
                ),
                action=PostbackAction(
                    label='Latihan Soal',
                    text='Latihan Soal',
                    data='action=material_quiz&subject_id='+subject_id+'&topic_id='+topic_id
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=1584,
                    y=36,
                    width=880,
                    height=784
                ),
                action=PostbackAction(
                    label='Diskusi',
                    text='Diskusi',
                    data='action=material_discussion&subject_id='+subject_id+'&topic_id='+topic_id
                )
            ),
        ]
    )
    rich_menu['material_learn'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_MATERIAL_LEARN, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['material_learn'], 'image/png', f)

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
                action=PostbackAction(
                    label='Kembali',
                    text='Kembali',
                    data='action=material'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=655,
                    y=36,
                    width=880,
                    height=780
                ),
                action=PostbackAction(
                    label='Belajar',
                    text='Belajar',
                    data='action=material_learn&subject_id='+subject_id+'&topic_id='+topic_id
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=1584,
                    y=36,
                    width=880,
                    height=784
                ),
                action=PostbackAction(
                    label='Diskusi',
                    text='Diskusi',
                    data='action=material_discussion&subject_id='+subject_id+'&topic_id='+topic_id
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
                action=PostbackAction(
                    label='Kembali',
                    text='Kembali',
                    data='action=material'
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=655,
                    y=36,
                    width=880,
                    height=780
                ),
                action=PostbackAction(
                    label='Belajar',
                    text='Belajar',
                    data='action=material_learn&subject_id='+subject_id+'&topic_id='+topic_id
                )
            ),
            RichMenuArea(
                bounds=RichMenuBounds(
                    x=1584,
                    y=36,
                    width=880,
                    height=784
                ),
                action=PostbackAction(
                    label='Latihan Soal',
                    text='Latihan Soal',
                    data='action=material_quiz&subject_id='+subject_id+'&topic_id='+topic_id
                )
            ),
        ]
    )
    rich_menu['material_discussion'] = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    with open(constant.RICH_MENU_MATERIAL_DISCUSSION, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu['material_discussion'], 'image/png', f)

    return rich_menu

def remove_rich_menu(line_user_id):
    line_bot_api.unlink_rich_menu_from_user(line_user_id)

# --------------------------------------------------------

def show_material_topic(event, conn, session, postback):
    # update rich menu, create rich menu material
    rich_menu = session['rich_menu']
    rich_menu_add = create_rich_menu_material_topic(line_user_id, postback['subject_id'], postback['topic_id'])
    rich_menu.update(rich_menu_add)
    redis.set(line_user_id,json.dumps({'user_id':session['user_id'],'code':session['code'],'name':session['name'],'class_id':session['class_id'],'status':'home','rich_menu':rich_menu}))

    # get all subject by class_id
    query_select_subject = 'SELECT * FROM subject WHERE id = %s'
    conn.query(query_select_subject, (postback['subject_id'],))
    row_subject = conn.cursor.fetchone()

    # get all topic by subject_id
    query_select_topic = 'SELECT * FROM topic WHERE subject_id = %s'
    conn.query(query_select_topic, (postback['subject_id'],))
    rows_topic = conn.cursor.fetchall()
    if rows_topic == None: # topic is empty
        line_bot_api.reply_message(
            event.reply_token,[
                TextMessage(
                    text=constant.TOPIC_EMPTY
                )
            ]
        )
    else: # topic exist
        contents = []
        for row in rows_topic:
            contents.append(
                BubbleContainer(
                    direction='ltr',
                    body=BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text=str(row['name']),
                                margin='md',
                                size='xl',
                                align='center',
                                gravity='center',
                                weight='bold'
                            ),
                            ButtonComponent(
                                action=PostbackAction(
                                    label='Belajar',
                                    text='Belajar',
                                    data='action=material_learn&subject_id='+str(row_subject['id'])+'&topic_id='+str(row['id'])
                                )
                            ),
                            ButtonComponent(
                                action=PostbackAction(
                                    label='Latihan Soal',
                                    text='Latihan Soal',
                                    data='action=material_quiz&subject_id='+str(row_subject['id'])+'&topic_id='+str(row['id'])
                                )
                            ),
                            ButtonComponent(
                                action=PostbackAction(
                                    label='Diskusi',
                                    text='Diskusi',
                                    data='action=material_discussion&subject_id='+str(row_subject['id'])+'&topic_id='+str(row['id'])
                                )
                            )
                        ]
                    )
                )
            )
            
        
        flex_message = FlexSendMessage(
            alt_text='Carousel Topik',
            contents=CarouselContainer(
                contents=contents
            )
        )

        return flex_message

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)