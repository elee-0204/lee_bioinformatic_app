from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app, send_file
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from guess_language import guess_language
from app import db
from app.main.forms import EditProfileForm, EmptyForm, PostForm, SearchForm
from app.models import User, Post, Notification
from app.translate import translate
from app.main import bp
from app.processing import allowed_file
from werkzeug.utils import secure_filename
import os
import shutil
import time
from io import BytesIO
import zipfile
from app.s3_demo import list_files_s3, download_file_s3, upload_file_s3
import boto3
# from rq.job import Job
import subprocess

UPLOAD_FOLDER = "uploads"
BUCKET = "leelab"

@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        language = guess_language(form.post.data)
        if language == 'UNKNOWN' or len(language) > 5:
            language = ''
        post = Post(body=form.post.data, author=current_user,
                    language=language)
        db.session.add(post)
        db.session.commit()
        flash(_('Your post is now live!'))
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type=int)
    posts = current_user.followed_posts().paginate(
        page, current_app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('main.index', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.index', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title=_('Home'), form=form,
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url)


@bp.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('main.explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title=_('Explore'),
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url)


@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, current_app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('main.user', username=user.username,
                       page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.user', username=user.username,
                       page=posts.prev_num) if posts.has_prev else None
    form = EmptyForm()
    return render_template('user.html', user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url, form=form)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title=_('Edit Profile'),
                           form=form)


@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash(_('User %(username)s not found.', username=username))
            return redirect(url_for('main.index'))
        if user == current_user:
            flash(_('You cannot follow yourself!'))
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(_('You are following %(username)s!', username=username))
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash(_('User %(username)s not found.', username=username))
            return redirect(url_for('main.index'))
        if user == current_user:
            flash(_('You cannot unfollow yourself!'))
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(_('You are not following %(username)s.', username=username))
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    return jsonify({'text': translate(request.form['text'],
                                      request.form['source_language'],
                                      request.form['dest_language'])})


@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('main.explore'))
    page = request.args.get('page', 1, type=int)
    posts, total = Post.search(g.search_form.q.data, page,
                               current_app.config['POSTS_PER_PAGE'])
    next_url = url_for('main.search', q=g.search_form.q.data, page=page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('main.search', q=g.search_form.q.data, page=page - 1) \
        if page > 1 else None
    return render_template('search.html', title=_('Search'), posts=posts,
                           next_url=next_url, prev_url=prev_url)


# Upload API
@bp.route('/uploadfile', methods=['GET'])
@login_required
def upload_form():
    return render_template('upload_file.html')

@bp.route('/uploadfile', methods=['POST'])
def upload_file():
    if request.method == "POST":
            # check if the post request has the file part
            if 'files[]' not in request.files:
                flash('No file attached in request')
                return redirect('main.upload_form')  
            files = request.files.getlist('files[]')
            filenames = []
            # if user does not select file, browser also
            # submit a empty part without filename
            # shutil.rmtree(current_app.config['UPLOAD_FOLDER'])
            # os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok = True) 
            s3 = boto3.resource('s3')
            bucket_to_delete = s3.Bucket('leelab')
            bucket_to_delete.objects.all().delete()
            for file in files:
                if file.filename == '':
                    flash('No file selected')
                    return redirect('main.upload_form')  
                if not allowed_file(file.filename):
                    flash('Allowed file types are txt only')
                    return redirect('main.upload_form')  
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(filename)
                    filenames.append(filename)
                    upload_file_s3(filename, BUCKET)
            flash("File(s) uploaded successfully")
            #send file name as parameter to downlad
            #return render_template('print_file.html', filenames=filenames)
            return redirect(url_for('main.print_file', filenames=filenames))


    

# Process API
@bp.route('/contents/<filenames>', methods = ['GET'])
@login_required
def print_file(filenames):
    text = dict()
    s3_client=boto3.resource('s3')
    bucket = s3_client.Bucket('leelab')
    files_in_s3 = bucket.objects.all() 
    files = []
    # filenames = list_files_s3("leelab")
    for obj in files_in_s3:
        key = obj.key
        # key = filenames[0]
        body = obj.get()['Body'].read().decode(encoding="utf-8",errors="ignore")
        text[key] = body
        files.append(key)
    return render_template('print_file.html', text=text, files=files)


@bp.route('/process_files/thisisatest')
@login_required
def process_files_1():
    # if current_user.get_task_in_progress('process_files'):
    #     flash(_('A process task is currently in progress')) 
    # else:
    shutil.rmtree(current_app.config['DOWNLOAD_FOLDER'])
    os.makedirs(current_app.config['DOWNLOAD_FOLDER'], exist_ok = True) 
    current_user.launch_task('process_files', _('Processing files...'), "one")
    db.session.commit()
    # file_count = len(files)
    time.sleep(5)
    # return redirect(url_for('main.loading'))
    return redirect(url_for('main.processing'))


@bp.route('/process_files/thisisnotatest')
@login_required
def process_files_2():
    shutil.rmtree(current_app.config['DOWNLOAD_FOLDER'])
    os.makedirs(current_app.config['DOWNLOAD_FOLDER'], exist_ok = True) 
    current_user.launch_task('process_files', _('Processing files...'), "two")
    db.session.commit()
    time.sleep(5)
    return redirect(url_for('main.processing'))

# @bp.route('/processing', methods=['GET'])
# @login_required
# def processing():
#     files = os.listdir(current_app.config['UPLOAD_FOLDER'])
#     return render_template('loading.html', filenames=files)

        
@bp.route('/processing')
@login_required
def processing():
    # running_task = current_user.get_task_in_progress('process_files')
    # task_id = running_task.id
    # job = Job.fetch(task_id, connection=current_app.redis)
    # job_status = job.get_status()
    # if job_status in ['queued', 'started', 'deferred', 'failed']:
    #     return redirect(url_for('main.processing'))
    # elif job_status == 'finished':
    if current_user.is_authenticated:
        running_tasks = current_user.get_tasks_in_progress()
        tasks_progress=[]
        if running_tasks:
            for task in running_tasks:
                tasks_progress.append(task.get_progress())
        for task_progress in tasks_progress:
            if task_progress<100:
                time.sleep(3)
                return redirect(url_for('main.processing'))
        filenames = list_files_s3('leelab')
        return redirect(url_for('main.download_file', filenames=filenames))
    

# Download API
@bp.route("/download_file/<filenames>", methods = ['GET'])
@login_required
def download_file(filenames):
    contents = dict()
    files = []
    # if current_user.get_task_in_progress('process_files'):
    #     flash(_('A process task is currently in progress')) 
    #     return render_template('download.html', text=contents, filenames=files, refresh=True)
    # else:
    s3_client=boto3.resource('s3')
    bucket = s3_client.Bucket('leelab-processed')
    files_in_s3 = bucket.objects.all()  
    for obj in files_in_s3:
        key = obj.key
        body = obj.get()['Body'].read().decode(encoding="utf-8",errors="ignore")
        contents[key] = body
        files.append(key)
        output = download_file_s3(key, "leelab-processed")
    return render_template('download.html', text=contents, filenames=files, refresh=False)
    # contents = dict()
    # filenames = os.listdir("downloads")
    # filenames = list_files_s3("leelab")
    # for file in filenames:
    #     saved_file = os.path.join("downloads", file)
    #     with open(saved_file, 'r') as f:        
    #         contents[file] = f.read()
    # return render_template('download.html', text=contents, filenames=filenames)


@bp.route('/return-files/<file>', methods=['GET'])
def return_files(file):
    if request.method == 'GET':
        # output = download_file_s3(file, "leelab-processed")
        output = os.path.join(current_app.config['DOWNLOAD_FOLDER'], file)
        return send_file(output, as_attachment=True)
    # path = f"downloads/{file}"
    # download_file_s3(file, "leelab", path)
    # return send_from_directory("downloads", file, as_attachment=True)
    # download_file_s3("whatsup.txt", "leelab")
    # downloadDirectoryFroms3("leelab","uploads")
    # return send_file(output, as_attachment=True)
    # return send_from_directory('downloads', "whatsup.txt", as_attachment=True)
    # return send_from_directory(current_app.config['DOWNLOAD_FOLDER'], "whatsup.txt", as_attachment=True)

    
@bp.route('/zipped_data')
def zipped_data():
    timestr = time.strftime("%Y%m%d-%H%M%S")
    fileName = "my_modified_files.zip".format(timestr)
    memory_file = BytesIO()
    file_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'])
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
          for root, dirs, files in os.walk(file_path):
                    for file in files:
                              zipf.write(os.path.join(root, file))
    memory_file.seek(0)
    return send_file(memory_file,
                      attachment_filename=fileName,
                      as_attachment=True)


@bp.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type=float)
    notifications = current_user.notifications.filter(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    return jsonify([{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications])


@bp.route('/figure_maker', methods=['GET'])
@login_required
def make_figure():
    return render_template('figure_maker.html')

@bp.route('/figure_maker', methods=['POST'])
def data_upload():
    if request.method == "POST":
            # check if the post request has the file part
            if 'files[]' not in request.files:
                flash('No file attached in request')
                return redirect('main.make_figure')  
            files = request.files.getlist('files[]')
            filenames = []
            # if user does not select file, browser also
            # submit a empty part without filename
            # shutil.rmtree(current_app.config['UPLOAD_FOLDER'])
            # os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok = True) 
            s3 = boto3.resource('s3')
            bucket_to_delete = s3.Bucket('leelab')
            bucket_to_delete.objects.all().delete()
            for file in files:
                if file.filename == '':
                    flash('No file selected')
                    return redirect('main.make_figure')  
                if not allowed_file(file.filename):
                    flash('Allowed file types are txt only')
                    return redirect('main.make_figure')    
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(filename)
                    filenames.append(filename)
                    upload_file_s3(filename, BUCKET)
            flash("File(s) uploaded successfully")
            #send file name as parameter to graph
            return redirect(url_for('main.graph_figure', filenames=filenames))



@bp.route('/graph_figure/<filenames>', methods=['GET'])
@login_required
def graph_figure(filenames):
    shutil.rmtree(current_app.config['DOWNLOAD_FOLDER'])
    os.makedirs(current_app.config['DOWNLOAD_FOLDER'], exist_ok = True) 
    current_user.launch_task('graph_figures', _('Graphing figures...'))
    db.session.commit()
    time.sleep(5)
    return redirect(url_for('main.job_processing'))

  
@bp.route('/figure_processing/')
@login_required
def job_processing():
    if current_user.is_authenticated:
        running_tasks = current_user.get_tasks_in_progress()
        tasks_progress=[]
        if running_tasks:
            for task in running_tasks:
                tasks_progress.append(task.get_progress())
        for task_progress in tasks_progress:
            if task_progress<100:
                time.sleep(3)
                return redirect(url_for('main.job_processing'))
        filenames = list_files_s3('leelab')
        return redirect(url_for('main.figure_result', filenames=filenames))
    
    
@bp.route('/final_graphs/<filenames>', methods=['GET'])
@login_required
def figure_result(filenames): 
    filenames=list_files_s3("leelab-processed")
    return render_template('graph_render.html', filenames=filenames)
    
    
    # try:
    #     filenames = list_files_s3("leelab")
    #     s3 = boto3.resource('s3')
    #     bucket_to_delete = s3.Bucket("leelab-processed")
    #     bucket_to_delete.objects.all().delete()
    #     command ='Rscript'
    #     # path2script ='path/to your script/max.R'
    #     app_file_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    #     path2script = os.path.join(app_file_path, "Violin_Plot_Maker.R")
    #     for filename in filenames:
    #         # Variable number of args in a list
    #         myfile = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    #         filepath = os.path.join(current_app.config['DOWNLOAD_FOLDER'], "graphs.pdf")
    #         args = [myfile, filepath]
    #         # Build subprocess command
    #         cmd = [command, path2script] + args
    #         # check_output will run the command and store to result
    #         subprocess.check_output(cmd, universal_newlines=True)
    #         # subprocess.check_output(cmd,shell=True,stderr=subprocess.STDOUT)
    #         # subprocess.check_call(cmd, shell=False)
    #         object_url = 'https://leelab-processed.s3.us-east-2.amazonaws.com/' + filename
            
            
    #     return render_template('graph_render.html', file_url=object_url)
    # except subprocess.CalledProcessError as e:
    #     raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
    
    
    #     total_files = len(filenames)
    #     for filename in filenames:
    #         path_uploaded_files = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    #         # folder_to_save = os.path.join(UPLOAD_FOLDER, filename)
    #         file = download_file_s3(filename, "leelab")
            
    #         render_figure(filename)
            
    #         upload_processed_files(output_path, "leelab-processed", filename)

# def process_files(type):
#     try:
#         _set_task_progress(0)
#         i = 0
#         # shutil.rmtree(current_app.config['DOWNLOAD_FOLDER'])
#         # os.makedirs(current_app.config['DOWNLOAD_FOLDER'], exist_ok = True) 
#         filenames = list_files_s3("leelab")
#         total_files = len(filenames)
#         s3 = boto3.resource('s3')
#         bucket_to_delete = s3.Bucket("leelab-processed")
#         bucket_to_delete.objects.all().delete()
#         for filename in filenames:
#             output_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], filename)
#             # folder_to_save = os.path.join(UPLOAD_FOLDER, filename)
#             file = download_file_s3(filename, "leelab")
#             render_figure(filename)
#             upload_processed_files(output_path, "leelab-processed", filename)
#             i += 1
#             _set_task_progress(100 * (i // total_files)) 
#     except:
#         _set_task_progress(100)
#         app.logger.error('Unhandled exception', exc_info=sys.exc_info())

