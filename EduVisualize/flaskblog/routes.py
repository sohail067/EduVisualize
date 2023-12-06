import os
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort, session, jsonify
from flaskblog import app, db, bcrypt
from flaskblog.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, AddClassForm, JoinClassForm
from flaskblog.models import User, Post, Classes, Members, Comment, Response, VideoQA, LastWatchedTime
from flask_login import login_user, current_user, logout_user, login_required
from flaskblog.transcription import extract_audio_segment,transcribe_audio
from flaskblog.qa_gen import query_chat_gpt
import json
import time
import random
import string
from sqlalchemy.orm import joinedload

@app.route("/")
def main():
    if not 'visited' in session:
        session['visited'] = True
        return redirect(url_for('loading'))
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/loading')
def loading():
    return render_template('loading.html')

@app.route("/home")
def home():
    user_classes = Classes.query.join(Members).filter(Members.student_id == current_user.id).all()
    return render_template('home.html', user_classes=user_classes)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data,password=hashed_password,
                    user_type=form.user_type.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))

def save_picture(form_picture, username):
    picture_fn = username + '.jpg'
    picture_path = os.path.join(
        app.root_path, 'static/profile_pics', picture_fn)
    output_size = (125, 125)
    i = Image.open(form_picture)
    if i.mode != 'RGB':
        i = i.convert('RGB')
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn

@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data, form.username.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',image_file=image_file, form=form)

@app.route("/about")
def about():
    return render_template('about.html', title='About')

# teacher module
@app.route("/create_class", methods=['GET', 'POST'])
@login_required
def create_class():
    form = AddClassForm()
    if form.validate_on_submit():
        class_name = form.class_name.data
        existing_class = Classes.query.filter_by(name=class_name).first()
        if existing_class:
            flash('A class with the same name already exists. Please choose a different name.', 'danger')
        else:
            new_class = Classes(name=class_name, teacher_id=current_user.id, teacher_name=current_user.username)
            join_code = generate_unique_join_code()
            new_class.joincode = join_code
            db.session.add(new_class)
            db.session.commit()
            new_student_class = Members(class_name=class_name, class_id=new_class.id,
                                        student_id=current_user.id, student_name=current_user.username)
            db.session.add(new_student_class)
            db.session.commit()
            flash('Your class has been created!', 'success')
            return redirect(url_for('home'))
    return render_template('create_class.html', title='Create Class', form=form)

def generate_unique_join_code():
    while True:
        join_code = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=6))
        existing_class = Classes.query.filter_by(joincode=join_code).first()
        if not existing_class:
            return join_code

@app.route("/class/<int:class_id>", methods=['GET', 'POST'])
@login_required
def class_posts(class_id):

    selected_class = Classes.query.get_or_404(class_id)
    posts = (Post.query.options(joinedload(Post.comments)).filter_by(class_id=class_id).all())
    total_posts = len(posts)
    return render_template('class_posts.html', selected_class=selected_class, posts=posts, total_posts=total_posts)

@app.route('/delete_class/<int:class_id>', methods=['GET', 'POST'])
@login_required
def delete_class(class_id):
    aclass = Classes.query.get_or_404(class_id)
    for post in aclass.posts:
        Comment.query.filter_by(post_id=post.id).delete()
        Response.query.filter_by(post_id=post.id).delete()
        VideoQA.query.filter_by(post_id=post.id).delete()
        LastWatchedTime.query.filter_by(post_id=post.id).delete()
    Members.query.filter_by(class_id = class_id).delete()
    db.session.delete(aclass)
    db.session.commit()
    flash('The class has been deleted!', 'success')
    return redirect(url_for('home'))  

@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('class_posts', class_id=post.class_id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return render_template('create_post.html', title='Update Post',form=form, legend='Update Post')

@app.route('/delete_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    Comment.query.filter_by(post_id=post_id).delete()
    Response.query.filter_by(post_id=post_id).delete()
    VideoQA.query.filter_by(post_id=post_id).delete()
    LastWatchedTime.query.filter_by(post_id=post_id).delete()
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('class_posts', class_id=post.class_id))

@app.route("/participants/<int:class_id>")
@login_required
def participants(class_id):
    teacher_classes = Classes.query.filter_by(teacher_id=current_user.id).all()
    class_students = {}
    for teacher_class in teacher_classes:
        class_students[int(teacher_class.id)] = {'class_name': teacher_class.name, 'students': []} 
        students = Members.query.filter_by(class_id=teacher_class.id).all()
        for student in students:
            student_info = {'student_id': student.student_id,
                            'student_name': User.query.get(student.student_id).username,}
            class_students[teacher_class.id]['students'].append(student_info)  
    return render_template('participants.html', class_id=class_id, class_students=class_students)


# video management module
@app.route("/post/new/<int:class_id>", methods=['GET', 'POST'])
@login_required
def new_post(class_id):
    form = PostForm()
    transcriptions = []
    selected_timestamps = []
    if form.validate_on_submit():
        video_file = None
        transcription = None
        if form.video.data:
            video_file = save_video(form.video.data, form.title.data)
            video_path = os.path.join(app.root_path, 'static/post_videos', video_file)
            audio_path = os.path.join(app.root_path, 'static', 'audio.wav')
            timestamps_str = form.timestamps.data
            if timestamps_str:
                selected_timestamps = [int(ts.strip()) for ts in timestamps_str.split(',')]
            start_time = 0
            end_time = 0

            for timestamp in selected_timestamps:
                end_time = timestamp
                extract_audio_segment(video_path, audio_path, start_time, end_time)
                transcription = transcribe_audio(audio_path)
                transcriptions.append(transcription)
                start_time = end_time
            print(transcriptions)
            # transcription_parts = split_text_into_equal_parts(transcription, len(selected_timestamps))
            save_transcription(transcriptions, form.title.data)
            # print(transcription_parts)
        class_id = class_id if class_id else request.form.get('class_id')
        post = Post( title=form.title.data,content=form.content.data,posted_by=current_user.username,
                    user_id=current_user.id,video=video_file,class_id=class_id,timestamps=timestamps_str)
        db.session.add(post)
        db.session.commit()
        p = Post.query.filter_by(title=form.title.data).first()
        prompting(transcriptions, form.title.data, p.id, class_id)
        flash('Your post has been created!', 'success')
        return redirect(url_for('class_posts', class_id=class_id))
    return render_template('create_post.html', title='New Post', form=form, legend='New Post',selected_timestamps=selected_timestamps,class_id = class_id)

def save_video(form_video, title):
    _, f_ext = os.path.splitext(form_video.filename)
    video_fn = f"{title}{f_ext}"
    video_path = os.path.join(app.root_path, 'static/post_videos', video_fn)
    form_video.save(video_path)
    return video_fn

def save_transcription(transcription, title):
    transcript_fn = title + '.txt'
    transcript_path = os.path.join(
        app.root_path, 'static/transcripts', transcript_fn)
    with open(transcript_path, 'w') as transcript_file:
        transcript_file.writelines('\n'.join(transcription))

def split_text_into_equal_parts(transcription, num_parts):
    content = transcription
    part_length = len(content) // num_parts
    parts = [content[i * part_length: (i + 1) * part_length] for i in range(num_parts)]
    return parts

def prompting(transcription_parts, title, post_id, class_id):
    count = 0
    prompt_count = 0
    for part in transcription_parts:
        qprompt = "Instruction:i)Do not use any single or double quotations words or sentences while making questions and options ii)format:'1.question, a)option1, b)option2, c)option3, d)option4 iii)generate questions and options such that each option length should not exceed more than 5 words,it should be between 1 to 5 words.follow these instructions and  Make 3 meaningful MCQ questions with 4 options on "
        aprompt = " answer these questions,Instruction:Just provide correct answer of the respective question  '1. a)answer, 2. c)answer, 3. d)answer and so on'.(replace answer with actual answer)remember given format must be followed"
        input_prompt = "\n".join(part)
        prompt_count += 1
        if prompt_count >= 3:
            delay_prompt()
            prompt_count = 0
        response_1 = query_chat_gpt(qprompt + input_prompt)
        prompt_count += 1
        if prompt_count >= 3:
            delay_prompt()
            prompt_count = 0
        response_2 = query_chat_gpt(response_1 + aprompt)
        lines = response_1.split("\n")
        # print(lines, "\n\n")
        questions = []
        found_first = False
        for line in lines:
            if found_first:
                questions.append(line)
            elif line.startswith("1"):
                found_first = True
                questions.append(line)
        if questions == []:
            questions = lines
        qs = [questions[i] for i in range(len(questions)) if i % 6 == 0]
        ops = []
        for i in range(1, len(questions)):
            if (i % 6 != 0) and (i % 6 != 5):
                ops.append(questions[i])
        answers = response_2.split("\n")
        # print(qs,"\n",ops,"\n",answers)
        questions_json = json.dumps(qs)
        options_json = json.dumps(ops)
        answers_json = json.dumps(answers)
        count += 1
        video_qa = VideoQA(class_id=class_id, post_id=post_id, title=title, part_number=count, questions=questions_json,answers=answers_json,options=options_json)
        db.session.add(video_qa)
        db.session.commit()

def delay_prompt():
    start_time = time.time()
    current_number = 1
    while current_number <= 40:
        elapsed_time = time.time() - start_time
        if elapsed_time >= 1:
            # print(current_number, end=" ")
            current_number += 1
            start_time = time.time()

@app.route('/store_video_timestamp/<int:class_id>/<int:post_id>', methods=['POST'])
def store_video_timestamp(class_id, post_id):
    if request.method == 'POST':
        try:
            data = request.get_json()
            timestamp = data.get('timestamp')
            # print("timestamp---", timestamp)
            watchTime = LastWatchedTime.query.filter_by(class_id=class_id, post_id=post_id, 
                                                        user_id=current_user.id).first()
            if watchTime is None:
                lwt = LastWatchedTime(class_id=class_id, post_id=post_id, user_id=current_user.id,user_name=current_user.username,timestamp=timestamp)
                db.session.add(lwt)
                db.session.commit()
            else:
                watchTime.timestamp = timestamp  
                db.session.commit()
            response_data = {
                'message': 'Video timestamp has been recorded!',
                'status': 'success'
            }
            return jsonify(response_data), 200
        except Exception as e:
            print("Error:", str(e))
            return jsonify({'error': 'Internal server error'}),

#QA_management module
@app.route("/class/<int:class_id>/<int:post_id>", methods=['GET', 'POST'])
@login_required
def selected_post(class_id, post_id):
    selected_class = Classes.query.get_or_404(class_id)
    posts = (Post.query.options(joinedload(Post.comments)).filter_by(class_id=class_id).all())
    for post in posts:
        post.comments.sort(key=lambda comment: comment.date_posted, reverse=True)
    questions = []
    options = []
    answers = []
    post = Post.query.get_or_404(post_id)
    videoqas = VideoQA.query.filter_by(post_id=post_id).all()
    questions_content = None
    options_content = None
    answers_content = None
    if videoqas:
        for videoqa in videoqas:
            questions_content = json.loads((videoqa.questions))
            print(questions_content[1])
            for x in range(3):
                questions.append(questions_content[x].replace('"', '`'))
            options_content = json.loads(videoqa.options)
            for x in range(12):
                options.append(options_content[x].replace('"', '`').replace('.', ''))
            answers_content = json.loads(videoqa.answers)
            for x in range(3):
                answers.append(answers_content[x].replace('"', '`').replace('.', ''))
        # print("q: ",questions,"\nop: ",options,"\na: ",answers)
    watchTime = LastWatchedTime.query.filter_by(class_id=class_id, post_id=post_id, user_id=current_user.id).first()
    if watchTime is None:
        timestamp = 0
    else:
        timestamp = watchTime.timestamp
    intervals = Post.query.filter_by(class_id=class_id, id=post_id).first()
    #print(intervals.timestamps)
    intervals_length = intervals.timestamps.count(',') + 1
    #print(intervals_length)
    resp = response_exists(post_id, current_user.username,intervals_length)

    return render_template('post.html', selected_class=selected_class, post=post, questions=questions, answers=answers, options=options, timestamp=timestamp, response_exists=resp,intervals = intervals.timestamps, intervals_length = intervals_length)

def response_exists(post_id, student_name,intervals_length):
    exist = []
    verify = []
    for i in range(intervals_length):
        responses = Response.query.filter_by(post_id=post_id, student_name=student_name, part_number=(i+1)).all()
        #print(responses)
        if responses is not None:
            for response in responses:
                exist.append(response.part_number)
        verify.append(i+1)
    #print(exist)
    verified = all(item in exist for item in verify)
    if verified:
        return True
    else:
        return False

# student module
@app.route('/join_class', methods=['POST'])
@login_required
def join_class():
    form = JoinClassForm()
    if form.validate_on_submit():
        join_code = form.join_code.data
        joined_class = Classes.query.filter_by(joincode=join_code).first()
        if joined_class:
            existing_student_class = Members.query.filter_by(class_id=joined_class.id,
                                                             student_id=current_user.id).first()
            if existing_student_class:
                flash('You are already in this class.', 'info')
            else:
                student_class = Members(student_id=current_user.id, class_id=joined_class.id,
                                        class_name=joined_class.name, student_name=current_user.username)
                db.session.add(student_class)
                db.session.commit()
                flash('You have successfully joined the class!', 'success')
                return redirect(url_for('home'))
        else:
            flash('Invalid join code. Please try again.', 'danger')
    return render_template('join_class.html', form=form)

@app.route("/add_comment/<int:post_id>", methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    text = request.form.get('text')
    if not text:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('class_posts', class_id=post.class_id))
    comment = Comment(text=text, user_id=current_user.id, post=post)
    db.session.add(comment)
    db.session.commit()
    flash('Your comment has been added.', 'success')
    return redirect(url_for('selected_post', class_id=post.class_id, post_id=post_id))

@app.route("/dashboard")
@login_required
def dashboard():
    joined_classes = Members.query.filter_by(student_id=current_user.id).all()
    class_data = {}
    for joined_class in joined_classes:
        class_name = joined_class.class_name
        class_id = joined_class.class_id
        responses = Response.query.filter_by(
            student_name=current_user.username, class_id=class_id).all()
        post_data = {}
        for response in responses:
            post_id = response.post_id
            post_title = Post.query.get(post_id).title
            correct_choice = response.correct_choice
            part_number = response.part_number
            if post_id not in post_data:
                post_data[post_id] = {'title': post_title, 'parts': {}}
            if part_number not in post_data[post_id]['parts']:
                post_data[post_id]['parts'][part_number] = {
                    'correct_choice': correct_choice, 'total_responses': 1}
            else:
                post_data[post_id]['parts'][part_number]['correct_choice'] += correct_choice
                post_data[post_id]['parts'][part_number]['total_responses'] += 1
        for post_id, post_info in post_data.items():
            for part_number, part_data in post_info['parts'].items():
                total_responses = part_data['total_responses']
                correct_responses = part_data['correct_choice']
                correctness_rate = (correct_responses / (total_responses * 3)) * 100
                part_data['correctness_rate'] = round(correctness_rate,2)
        class_data[class_name] = {'post_data': post_data}
    return render_template('dashboard.html', class_data=class_data)


#feedback module
@app.route('/store_responses/<int:class_id>/<int:post_id>', methods=['POST'])
@login_required
def store_responses(class_id, post_id):
    if request.method == 'POST':
        try:
            data = request.get_json()
            part_number = data.get('part_number')
            selected_answers = data.get('selected_answers')
            correct_choice = data.get('correctCount')
            wrong_choice = 3 - correct_choice
            post = Post.query.filter_by(id=post_id).first()
            res = interval_response_exists(
                post_id, current_user.username, part_number)
            if res is False:
                response = Response(class_id=class_id,post_id=post_id,title=post.title,student_name=current_user.username,part_number=part_number,
                                    selected_options=selected_answers,correct_choice=correct_choice,wrong_choice=wrong_choice)
                db.session.add(response)
                db.session.commit()
            response_data = {
                'message': 'Your answers have been recorded!',
                'status': 'success'
            }
            return jsonify(response_data), 200
        except Exception as e:
            print("Error:", str(e))
            return jsonify({'error': 'Internal server error'}),

def interval_response_exists(post_id, student_name, partNumber):
    response = Response.query.filter_by(post_id=post_id, student_name=student_name, part_number=partNumber).all()
    value = 0
    for r in response:
        if r.correct_choice == 3:
            value = 1
            break
        else:
            value = 0
    if value == 1:
        return True
    else:
        return False

@app.route("/class/<int:class_id>/responses", methods=['GET'])
@login_required
def responses(class_id):
    responses = Response.query.filter_by(class_id=class_id).all()
    student_names = set(response.student_name for response in responses)
    return render_template('responses.html', student_names=student_names, class_id=class_id)


@app.route("/class/<int:class_id>/feedback/<student_name>", methods=['GET'])
@login_required
def view_feedback(class_id, student_name):
    feedback_messages = {}
    feedback_messages = generate_feedback_messages_for_student(class_id, student_name)
    video_info = fetch_video_info(class_id, student_name)
    return render_template('feedback.html', student_name=student_name, feedback_messages=feedback_messages, video_info=video_info)
def generate_feedback_messages_for_student(class_id, student_name):
    feedback_messages_dict = {}  # New dictionary to store feedback messages based on post_id
    responses = Response.query.filter_by(class_id=class_id, student_name=student_name).all()
    grouped_responses = {}

    for response in responses:
        key = (response.post_id, response.part_number)
        if key not in grouped_responses:
            grouped_responses[key] = []
        grouped_responses[key].append(response)

    for (post_id, part_number), responses in grouped_responses.items():
        correct_responses = 0
        message = f"{student_name} did not achieve 3 out of 3 correct responses in any part"

        for i, response in enumerate(responses[:3]):
            if response.correct_choice == 3:
                correct_responses += 1
                message = f"Part Number {part_number} : got all correct in attempt : {i + 1}"
                break
            elif i >= 2:
                message = f"Part Number {part_number} : Your student did not achieve a perfect score in the first three attempts. It's advisable to provide additional support for their studies as they have not yet answered all questions correctly even after watching the posted video."
                break

        # Store the feedback message in the dictionary based on post_id
        if post_id not in feedback_messages_dict:
            feedback_messages_dict[post_id] = []
        feedback_messages_dict[post_id].append(message)

    return feedback_messages_dict


def fetch_video_info(class_id, student_name):
    video_info = []
    responses = Response.query.filter_by(class_id=class_id, student_name=student_name).all()
    video_data = {}

    
    max_part_number = max(response.part_number for response in responses)
    print(max_part_number)
    for response in responses:
        if response.post_id not in video_data:
            video_data[response.post_id] = {
                'post_id': response.post_id,
                'video_title': response.title,
                'parts': [i + 1 for i in range(max_part_number)],
                'attempts': [0] * max_part_number,
                'correct_choices': [0] * max_part_number,
            }
        part_index = response.part_number - 1
        video_data[response.post_id]['attempts'][part_index] += 1
        video_data[response.post_id]['correct_choices'][part_index] = max(
            video_data[response.post_id]['correct_choices'][part_index],
            response.correct_choice
        )
    
    video_info = list(video_data.values())
    print(video_info)
    return video_info

