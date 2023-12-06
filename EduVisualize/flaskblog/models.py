from datetime import datetime
from flaskblog import db, login_manager
from flask_login import UserMixin


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.png')
    password = db.Column(db.String(60), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    classes = db.relationship('Classes', backref='teacher_classes', lazy=True)

    @property
    def is_teacher(self):
        return self.user_type == 'teacher'
    
    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.image_file}')"


class Classes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_name = db.Column(db.String(100), nullable=False)  
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    joincode = db.Column(db.String(6), unique=True, nullable=False)
    students = db.relationship('User', back_populates='classes')
    teacher = db.relationship('User', back_populates='classes')
    posts = db.relationship('Post', backref='class_posts', lazy=True)
    


class Members(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)  
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    class_name = db.Column(db.String(100), nullable=False)  
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('User', foreign_keys=[student_id])

    def __repr__(self):
        return f"StudentClass('{self.student_id}', '{self.class_id}')"

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100),unique=True,nullable=False)
    content = db.Column(db.String(1000), nullable=False)
    video = db.Column(db.String(20), nullable=False)
    posted_by = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False) 
    timestamps = db.Column(db.String)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='post', lazy=True)
    
    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"
    
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author = db.relationship('User', backref='comments')
    
    def __repr__(self):
        return f"Comment('{self.text}', '{self.date_posted}')"

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(20), nullable=False)
    student_name = db.Column(db.String(20), nullable=False)
    post_id = db.Column(db.Integer, nullable=False)
    part_number = db.Column(db.Integer) 
    selected_options = db.Column(db.String(200), nullable=True)
    correct_choice = db.Column(db.Integer)  
    wrong_choice = db.Column(db.Integer) 

    def __repr__(self):
        return f"Response('{self.class_id}', '{self.teacher_name}', '{self.post_id}', '{self.student_name}', '{self.selected_options}')"

class VideoQA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    title = db.Column(db.String(100),nullable=False)
    part_number = db.Column(db.Integer, nullable=False)
    questions = db.Column(db.String(2000))
    options = db.Column(db.String(2000))
    answers = db.Column(db.String(2000))
    def __repr__(self):
        return f"VideoTranscription('{self.post_id}', '{self.part_number}')"


class LastWatchedTime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_name = db.Column(db.String(20), nullable=False)
    post_id = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.Float)
